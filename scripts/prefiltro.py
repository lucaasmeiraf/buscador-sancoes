#!/usr/bin/env python3
"""Pré-filtro por SELEÇÃO de trechos candidatos (determinístico, sem LLM).

Lê os arquivos coletados em data/raw/ (XML do DOU, TXT do DODF), carrega as redes
de palavras-chave de config/dicionario.md e seleciona os trechos que contêm ao
menos 1 termo de SANÇÃO e 1 termo de RODOVIA (ou órgão-âncora).

IMPORTANTE: isto é seleção, não extração. O trecho selecionado vai INTEIRO para o
LLM (prompts/rotina_sancoes.md), que é quem extrai os campos. Nenhum campo é
extraído aqui por regex.

Saída: data/candidatos.json — lista de trechos com fonte, link e hash (dedup).
Estado: data/vistos.json — hashes já processados em execuções anteriores.

Uso:
    python scripts/prefiltro.py             # varre data/raw/*/HOJE
    python scripts/prefiltro.py 2026-08-05  # data específica
"""

import hashlib
import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path
from xml.etree import ElementTree

RAIZ = Path(__file__).resolve().parent.parent
DICIONARIO = RAIZ / "config" / "dicionario.md"
DADOS = RAIZ / "data"
CANDIDATOS = DADOS / "candidatos.json"
VISTOS = DADOS / "vistos.json"


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

def blocos_dou(dia_str: str):
    """Itera as matérias dos XML do DOU: uma matéria = um bloco candidato inteiro."""
    for xml in (DADOS / "raw" / "dou" / dia_str).rglob("*.xml"):
        try:
            raiz = ElementTree.parse(xml).getroot()
        except ElementTree.ParseError:
            continue
        for artigo in raiz.iter("article"):
            texto = " ".join(artigo.itertext()).strip()
            if not texto:
                continue
            yield {
                "fonte": "DOU",
                "secao": xml.parent.name,          # DO1 / DO3
                "arquivo": xml.name,
                # Link público aproximado; o XML pode trazer urlTitle nos atributos.
                "link": artigo.get("pdfPage")
                or f"https://www.in.gov.br/leiturajornal?data={dia_str}",
                "texto": texto,
            }


def blocos_dodf(dia_str: str):
    """Itera blocos do texto extraído do DODF (janela de páginas do PDF)."""
    for txt in (DADOS / "raw" / "dodf" / dia_str).rglob("*.txt"):
        paginas = txt.read_text(encoding="utf-8").split("\n\n===PAGINA===\n\n")
        for i, pagina in enumerate(paginas, start=1):
            if not pagina.strip():
                continue
            yield {
                "fonte": "DODF",
                "secao": "",
                "arquivo": txt.with_suffix(".pdf").name,
                "link": f"https://dodf.df.gov.br (edição de {dia_str}, pág. {i})",
                "texto": pagina.strip(),
            }


# ---------------------------------------------------------------- pipeline

def main() -> int:
    dia = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    dia_str = dia.strftime("%Y-%m-%d")

    redes = carregar_dicionario()
    vistos: list[str] = json.loads(VISTOS.read_text(encoding="utf-8")) if VISTOS.exists() else []
    candidatos, descartados_dedup = [], 0

    for bloco in list(blocos_dou(dia_str)) + list(blocos_dodf(dia_str)):
        texto_norm = _normalizar(re.sub(r"\s+", " ", bloco["texto"]))
        hits_sancao = _casa(texto_norm, redes["sancao"])
        hits_rodovia = _casa(texto_norm, redes["rodovia"])
        # Critério de seleção: 1 termo de cada rede. Para afrouxar (só sanção),
        # troque a linha abaixo por: if not hits_sancao: continue
        if not (hits_sancao and hits_rodovia):
            continue

        h = hashlib.sha256(texto_norm.encode("utf-8")).hexdigest()
        if h in vistos:
            descartados_dedup += 1
            continue

        candidatos.append({
            "hash": h,
            "data_publicacao": dia_str,
            "fonte": bloco["fonte"],
            "secao": bloco["secao"],
            "arquivo": bloco["arquivo"],
            "link": bloco["link"],
            "termos_sancao": hits_sancao,
            "termos_rodovia": hits_rodovia,
            "texto": bloco["texto"],   # trecho INTEIRO — vai assim para o LLM
        })

    DADOS.mkdir(exist_ok=True)
    CANDIDATOS.write_text(
        json.dumps(candidatos, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[prefiltro] {len(candidatos)} candidatos -> {CANDIDATOS} "
          f"({descartados_dedup} descartados por dedup)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
