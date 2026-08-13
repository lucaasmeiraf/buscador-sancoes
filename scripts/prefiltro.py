#!/usr/bin/env python3
"""Pré-filtro por SELEÇÃO de trechos candidatos (determinístico, sem LLM).

Lê os arquivos coletados em data/raw/ (XML do DOU, TXT do DODF), carrega as redes
de palavras-chave de config/dicionario.md e seleciona os trechos que contêm ao
menos 1 termo de SANÇÃO e 1 termo de RODOVIA (ou órgão-âncora).

IMPORTANTE: isto é seleção, não extração. O trecho selecionado vai INTEIRO para o
LLM (prompts/rotina_sancoes.md), que é quem extrai os campos. Nenhum campo é
extraído aqui por regex.

Localização da publicação (link/página/edição) também NÃO é tarefa do LLM: é
montada aqui, a partir dos metadados oficiais de cada fonte, e viaja com o
trecho até a mensagem final. Ver `links_dou.py` e a nota sobre página no DODF.

O DODF tem duas origens possíveis, nesta ordem: o texto baixado localmente
(`data/raw/dodf/`) e, se não houver, os blocos já selecionados fora do sandbox
pelo GitHub Actions (`data/dodf/`, trazidos da branch `dados/dodf` — ver
docs/ISSUES.md §1). O modo `--exportar` é o lado do Actions dessa troca.

Saída: data/candidatos.json — lista de trechos com fonte, link e hash (dedup).
Estado: data/vistos.json — hashes já processados em execuções anteriores.

Uso:
    python scripts/prefiltro.py             # varre data/raw/*/HOJE
    python scripts/prefiltro.py 2026-08-05  # data específica
    python scripts/prefiltro.py 2026-08-05 --fonte dodf --exportar <arquivo>
"""

import argparse
import hashlib
import json
import os
import re
import textwrap
import unicodedata
from datetime import date
from pathlib import Path
from xml.etree import ElementTree

import links_dou

RAIZ = Path(__file__).resolve().parent.parent
DICIONARIO = RAIZ / "config" / "dicionario.md"
DADOS = RAIZ / "data"
CANDIDATOS = DADOS / "candidatos.json"
# Um arquivo por candidato, dimensionado para a ferramenta de leitura do agente.
CANDIDATOS_DIR = DADOS / "candidatos"
VISTOS = DADOS / "vistos.json"
# Contagens do dia (quanto foi examinado, por fonte) — insumo do rodapé de
# transparência da mensagem (passo 5 do SKILL.md). Determinístico de propósito:
# número que a cliente lê não pode ser estimativa do LLM.
ESTATISTICAS = DADOS / "estatisticas.json"
# Blocos do DODF selecionados fora do sandbox (branch `dados/dodf`).
DODF_EXTERNO = DADOS / "dodf"


# ---------------------------------------------------------------- dicionário

def _normalizar(texto: str) -> str:
    """minúsculas + sem acentos, para casar termos do dicionário."""
    nfkd = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def carregar_dicionario() -> dict[str, list[str]]:
    """Lê config/dicionario.md e devolve {'sancao': [...], 'rodovia': [...]}.

    Termos são as linhas "- ..." de cada seção "## Rede ...". Os órgãos-âncora
    entram na rede RODOVIA (ver dicionario.md).
    """
    redes: dict[str, list[str]] = {"sancao": [], "rodovia": []}
    rede_atual = None
    for linha in DICIONARIO.read_text(encoding="utf-8").splitlines():
        if linha.startswith("## "):
            titulo = _normalizar(linha)
            if "sancao" in titulo:
                rede_atual = "sancao"
            elif "rodovia" in titulo or "orgaos-ancora" in titulo or "orgaos" in titulo:
                rede_atual = "rodovia"
            else:
                rede_atual = None
        elif linha.startswith("- ") and rede_atual:
            redes[rede_atual].append(_normalizar(linha[2:].strip()))
    return redes


def _casa(texto_norm: str, termos: list[str]) -> list[str]:
    """Retorna os termos da rede presentes no texto (substring, já normalizado)."""
    return [t for t in termos if t in texto_norm]


# ---------------------------------------------------------------- fontes

def _texto_materia(article: ElementTree.Element) -> tuple[str, str]:
    """Devolve (texto para o LLM, texto do corpo para casar o link).

    O campo <Texto> do INLABS vem como CDATA contendo HTML (`<p class="...">`).
    Sem esta limpeza as tags iam literais para o LLM, gastando contexto e
    poluindo a extração.

    Os dois textos são diferentes de propósito: o primeiro acrescenta
    <Identifica>/<Ementa> como cabeçalho, enquanto o índice do `leiturajornal`
    guarda só o corpo — casar com o cabeçalho junto duplicaria o título e
    derrubaria o casamento (o corpo já começa pelo título).
    """
    corpo = article.find("body")
    if corpo is None:
        texto = " ".join(article.itertext()).strip()
        return texto, texto

    html = corpo.findtext("Texto") or ""
    html = re.sub(r"<\s*/?\s*(p|br|div|tr)\b[^>]*>", "\n", html, flags=re.I)
    body_texto = re.sub(r"[ \t]+", " ", re.sub(r"<[^>]+>", " ", html)).strip()

    cabecalho = [corpo.findtext(tag) or ""
                 for tag in ("Identifica", "Ementa", "Titulo", "SubTitulo")]
    partes = [p.strip() for p in [*cabecalho, body_texto] if p.strip()]
    return "\n".join(partes), body_texto


def blocos_dou(dia: date, dia_str: str):
    """Itera as matérias dos XML do DOU: uma matéria = um bloco candidato inteiro.

    Cada bloco leva a localização exata da publicação, extraída dos atributos do
    <article>: `numberPage` é a página impressa (idêntica à `pagina` do
    `pdfPage`) e `editionNumber` é o número da edição. O link preferencial é o
    da matéria; o de página é o fallback (ver links_dou.py).
    """
    indices: dict[str, dict] = {}   # cache de índice por seção, dentro da run
    for xml in (DADOS / "raw" / "dou" / dia_str).rglob("*.xml"):
        if xml.name.startswith("_"):
            continue               # arquivos de apoio (cache de urlTitle)
        try:
            raiz = ElementTree.parse(xml).getroot()
        except ElementTree.ParseError:
            continue
        for artigo in raiz.iter("article"):
            texto, corpo = _texto_materia(artigo)
            if not texto:
                continue
            pub_name = artigo.get("pubName") or xml.parent.name
            pagina = artigo.get("numberPage")
            link, direto = links_dou.resolver(dia, pub_name, pagina, corpo, indices)
            yield {
                "fonte": "DOU",
                "secao": pub_name,                 # DO1 / DO3 / DO1E...
                "arquivo": xml.name,
                "pagina": pagina,
                "edicao": artigo.get("editionNumber"),
                "orgao_publicador": artigo.get("artCategory"),  # hierarquia oficial
                "tipo_ato": artigo.get("artType"),
                "link": link,
                "link_tipo": "materia" if direto else "pagina",
                "link_pagina": links_dou.link_pagina(dia, pub_name, pagina),
                "texto": texto,
            }


def _pagina_impressa(pagina_texto: str, indice: int) -> int:
    """Página impressa do DODF: lê o rodapé "PÁGINA n", com o índice como reserva.

    Conferido na edição 144 de 06/08/2026: o rodapé aparece em 83 das 84 páginas
    (falta só na capa) e bate com o índice do PDF em todas. O rodapé é a fonte
    de verdade porque as edições extras têm numeração própria.
    """
    achados = re.findall(r"P[ÁA]GINA\s+(\d+)", pagina_texto, flags=re.I)
    return int(achados[-1]) if achados else indice


def blocos_dodf(dia_str: str):
    """Blocos do DODF, do texto local ou do que o Actions já selecionou.

    A rotina na nuvem não alcança o site (docs/ISSUES.md §1), então lá só existe
    o caminho externo; local e no runner do Actions só existe o primeiro.
    """
    if (DADOS / "raw" / "dodf" / dia_str).exists():
        yield from blocos_dodf_local(dia_str)
    else:
        yield from blocos_dodf_externos(dia_str)


def blocos_dodf_externos(dia_str: str):
    """Blocos vindos da branch `dados/dodf` (já selecionados pelo Actions).

    Ausência do arquivo significa "o DODF não foi coletado hoje" — a rotina
    segue com o DOU e avisa o operador (passo 1 do SKILL.md). Lista vazia é
    diferente: quer dizer que houve coleta e nada casou com o dicionário.
    """
    arquivo = DODF_EXTERNO / dia_str / "blocos.json"
    if not arquivo.exists():
        print(f"[prefiltro] sem blocos do DODF em {arquivo} — seguindo só com o DOU.")
        return
    yield from json.loads(arquivo.read_text(encoding="utf-8"))


def blocos_dodf_local(dia_str: str):
    """Itera blocos do texto extraído do DODF (uma página do PDF por bloco)."""
    pasta = DADOS / "raw" / "dodf" / dia_str
    meta = {}
    if (pasta / "_edicao.json").exists():
        meta = {m["arquivo"]: m for m in json.loads((pasta / "_edicao.json").read_text(encoding="utf-8"))}

    for txt in pasta.rglob("*.txt"):
        nome_pdf = txt.with_suffix(".pdf").name
        info = meta.get(nome_pdf, {})
        paginas = txt.read_text(encoding="utf-8").split("\n\n===PAGINA===\n\n")
        for i, pagina in enumerate(paginas, start=1):
            if not pagina.strip():
                continue
            impressa = _pagina_impressa(pagina, i)
            # `#page=` é entendido pelo visualizador de PDF do navegador — o
            # endpoint devolve Content-Disposition: inline, então o link abre
            # já na página certa em vez de baixar o diário inteiro.
            link = info.get("url")
            yield {
                "fonte": "DODF",
                "secao": info.get("edicao", ""),
                "arquivo": nome_pdf,
                "pagina": str(impressa),
                "edicao": info.get("edicao"),
                "orgao_publicador": None,
                "tipo_ato": None,
                "link": f"{link}#page={impressa}" if link else "https://dodf.df.gov.br",
                "link_tipo": "pdf_pagina" if link else "portal",
                "link_pagina": link or "https://dodf.df.gov.br",
                "texto": pagina.strip(),
            }


# ---------------------------------------------------------------- pipeline

def _selecionar(bloco: dict, redes: dict) -> tuple[str, list[str], list[str]] | None:
    """Aplica o critério de seleção a um bloco: 1 termo de cada rede.

    Devolve (texto normalizado, termos de sanção, termos de rodovia) ou None.
    Para afrouxar (só sanção), troque a condição por `if not hits_sancao`.
    """
    texto_norm = _normalizar(re.sub(r"\s+", " ", bloco["texto"]))
    hits_sancao = _casa(texto_norm, redes["sancao"])
    hits_rodovia = _casa(texto_norm, redes["rodovia"])
    if not (hits_sancao and hits_rodovia):
        return None
    return texto_norm, hits_sancao, hits_rodovia


def exportar_dodf(dia_str: str, destino: Path) -> int:
    """Grava os blocos do DODF que passam na seleção — lado Actions da troca.

    Sem hash e sem dedup de propósito: `data/vistos.json` é estado da rotina, e
    o runner do Actions vê uma cópia que pode estar desatualizada. A dedup
    acontece uma vez só, na rotina, quando estes blocos são reprocessados.
    """
    redes = carregar_dicionario()
    selecionados = [b for b in blocos_dodf_local(dia_str) if _selecionar(b, redes)]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(selecionados, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[prefiltro] {len(selecionados)} blocos do DODF de {dia_str} -> {destino}")
    return 0


def _gravar_individuais(candidatos: list[dict]) -> None:
    """Grava um arquivo de texto por candidato em data/candidatos/.

    Existe porque a run de 13/08/2026 travou tentando ler o candidatos.json
    inteiro (803KB) — acima do limite da ferramenta de leitura de arquivos do
    agente (256KB). O formato é texto plano com linhas curtas de propósito: a
    ferramenta também trunca linhas muito longas, o que mutilaria um JSON
    minificado. O agente lê estes arquivos um a um no passo 3 do SKILL.md;
    o candidatos.json continua sendo o artefato canônico para scripts.
    """
    if CANDIDATOS_DIR.exists():
        for antigo in CANDIDATOS_DIR.glob("*.txt"):
            antigo.unlink()
    CANDIDATOS_DIR.mkdir(parents=True, exist_ok=True)

    for i, c in enumerate(candidatos, start=1):
        texto = "\n".join(
            textwrap.fill(linha, width=1000) if len(linha) > 1000 else linha
            for linha in c["texto"].splitlines()
        )
        campos = [f"{campo}: {c.get(campo) or ''}"
                  for campo in ("hash", "fonte", "secao", "edicao", "pagina",
                                "data_publicacao", "orgao_publicador",
                                "tipo_ato", "link", "link_tipo", "link_pagina")]
        campos.append("termos_sancao: " + ", ".join(c["termos_sancao"]))
        campos.append("termos_rodovia: " + ", ".join(c["termos_rodovia"]))
        (CANDIDATOS_DIR / f"{i:03d}-{c['hash'][:8]}.txt").write_text(
            "\n".join(campos) + "\n\n--- TEXTO ---\n" + texto + "\n",
            encoding="utf-8",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", nargs="?", help="AAAA-MM-DD (padrão: hoje)")
    parser.add_argument("--fonte", choices=["todas", "dodf"], default="todas",
                        help="'dodf' só faz sentido com --exportar")
    parser.add_argument("--exportar", type=Path, metavar="ARQUIVO",
                        help="grava os blocos selecionados do DODF e sai")
    args = parser.parse_args()

    dia = date.fromisoformat(args.data) if args.data else date.today()
    dia_str = dia.strftime("%Y-%m-%d")

    if args.exportar:
        if args.fonte != "dodf":
            parser.error("--exportar exige --fonte dodf")
        return exportar_dodf(dia_str, args.exportar)

    redes = carregar_dicionario()
    vistos: list[str] = json.loads(VISTOS.read_text(encoding="utf-8")) if VISTOS.exists() else []
    candidatos, descartados_dedup = [], 0

    # Origem do DODF hoje: define como interpretar as contagens (blocos
    # externos já vêm selecionados — não são "páginas examinadas").
    if (DADOS / "raw" / "dodf" / dia_str).exists():
        dodf_origem = "local"
    elif (DODF_EXTERNO / dia_str / "blocos.json").exists():
        dodf_origem = "externa"
    else:
        dodf_origem = "ausente"

    examinados = {"DOU": 0, "DODF": 0}
    selecionados = {"DOU": 0, "DODF": 0}
    edicoes_dodf: set[str] = set()

    for bloco in list(blocos_dou(dia, dia_str)) + list(blocos_dodf(dia_str)):
        examinados[bloco["fonte"]] += 1
        if bloco["fonte"] == "DODF" and bloco.get("edicao"):
            edicoes_dodf.add(str(bloco["edicao"]))

        selecao = _selecionar(bloco, redes)
        if selecao is None:
            continue
        texto_norm, hits_sancao, hits_rodovia = selecao

        h = hashlib.sha256(texto_norm.encode("utf-8")).hexdigest()
        if h in vistos:
            descartados_dedup += 1
            continue

        selecionados[bloco["fonte"]] += 1
        candidatos.append({
            "hash": h,
            "data_publicacao": dia_str,
            "termos_sancao": hits_sancao,
            "termos_rodovia": hits_rodovia,
            **bloco,   # fonte, secao, arquivo, pagina, edicao, link, texto...
        })

    DADOS.mkdir(exist_ok=True)
    CANDIDATOS.write_text(
        json.dumps(candidatos, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _gravar_individuais(candidatos)
    ESTATISTICAS.write_text(json.dumps({
        "data": dia_str,
        "dou": {
            "materias_examinadas": examinados["DOU"],
            "candidatos": selecionados["DOU"],
        },
        "dodf": {
            "origem": dodf_origem,
            # Blocos externos já chegam selecionados: contar como "páginas
            # examinadas" inflaria a transparência com um número falso.
            "paginas_examinadas": examinados["DODF"] if dodf_origem == "local" else None,
            "edicoes": sorted(edicoes_dodf),
            "candidatos": selecionados["DODF"],
        },
        "descartados_dedup": descartados_dedup,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    diretos = sum(1 for c in candidatos if c["link_tipo"] == "materia")
    print(f"[prefiltro] {len(candidatos)} candidatos -> {CANDIDATOS} "
          f"e {CANDIDATOS_DIR}{os.sep}NNN-*.txt (um por trecho; "
          f"{descartados_dedup} descartados por dedup; "
          f"{diretos} com link direto da matéria)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
