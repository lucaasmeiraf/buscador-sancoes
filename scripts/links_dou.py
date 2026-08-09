#!/usr/bin/env python3
"""Links precisos para as matérias do DOU (Imprensa Nacional).

Motivo de existir: o lead só é útil se o link levar à matéria certa. O XML do
INLABS já traz a página impressa correta (`numberPage`, idêntica à `pagina` do
`pdfPage` — conferido em 774/774 matérias do DO1+DO3 de 07/08/2026), mas a
página ainda obriga a garimpar a matéria dentro dela.

O site do DOU expõe um link direto por matéria: `https://www.in.gov.br/web/dou/-/<urlTitle>`.
O `urlTitle` não está no XML, mas a página `leiturajornal` do dia embute um JSON
com `urlTitle` + `numberPage` + `content` de todas as matérias da seção. Este
módulo baixa esse JSON uma vez por dia/seção, indexa por (página, prefixo do
texto) e resolve o `urlTitle` de cada matéria do XML.

Tudo aqui é determinístico e best-effort: se a rede falhar ou a matéria não
casar, devolve o link de página (`leiturajornal?...&pagina=N`), que continua
apontando para a página impressa correta. O LLM nunca monta URL.

Uso direto (diagnóstico):
    python scripts/links_dou.py 2026-08-07 do3
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

import requests

BASE_LEITURA = "https://www.in.gov.br/leiturajornal"
BASE_MATERIA = "https://www.in.gov.br/web/dou/-/"
CACHE = Path(__file__).resolve().parent.parent / "data" / "raw" / "dou"

# O portal responde 403/HTML reduzido para clientes sem cara de navegador.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

# Comprimentos do prefixo usados no casamento, do mais específico ao mais
# tolerante. Medido no DO3 de 07/08/2026: 100 chars → 2422 casamentos exatos,
# 71 ambíguos e 51 sem match em 2544 matérias.
PREFIXOS = (100, 60)


def _normalizar(texto: str) -> str:
    """Texto comparável: sem tags, sem acento, minúsculo, espaço único."""
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def secao_url(pub_name: str) -> str:
    """`pubName` do XML (DO1, DO3, DO1E...) -> valor do parâmetro `secao`."""
    return (pub_name or "").strip().lower()


def link_pagina(dia: date, pub_name: str, pagina: str | int | None) -> str:
    """Link da PÁGINA impressa no leitor oficial — o fallback, sempre válido.

    O `leiturajornal` espera a data em DD-MM-AAAA (não AAAA-MM-DD) e a seção em
    minúsculas; errar qualquer um dos dois devolve a edição errada ou nenhuma.
    """
    url = f"{BASE_LEITURA}?data={dia.strftime('%d-%m-%Y')}&secao={secao_url(pub_name)}"
    return f"{url}&pagina={pagina}" if pagina else url


def link_materia(url_title: str) -> str:
    """Link direto da matéria — abre só ela, sem garimpo na página."""
    return f"{BASE_MATERIA}{url_title}"


# ------------------------------------------------------------------ índice

def _baixar_indice(dia: date, secao: str) -> list[dict]:
    """Baixa o JSON de matérias que o `leiturajornal` embute na própria página."""
    resp = requests.get(
        BASE_LEITURA,
        params={"data": dia.strftime("%d-%m-%Y"), "secao": secao},
        headers=HEADERS,
        timeout=120,
    )
    resp.raise_for_status()
    bloco = re.search(
        r'<script id="params" type="application/json">(.*?)</script>',
        resp.text,
        re.S,
    )
    if not bloco:
        raise RuntimeError("leiturajornal não trouxe o bloco 'params' — layout mudou?")
    return json.loads(bloco.group(1)).get("jsonArray") or []


def carregar_indice(dia: date, secao: str) -> dict[tuple[str, str], str]:
    """Índice {(página, prefixo do texto): urlTitle} da seção, com cache em disco.

    Cache por dia/seção em `data/raw/dou/<dia>/`: a rotina processa vários
    trechos da mesma seção e não faz sentido rebaixar 2 MB de HTML por trecho.
    """
    arquivo = CACHE / dia.strftime("%Y-%m-%d") / f"_urltitles_{secao}.json"
    if arquivo.exists():
        materias = json.loads(arquivo.read_text(encoding="utf-8"))
    else:
        materias = _baixar_indice(dia, secao)
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(json.dumps(materias, ensure_ascii=False), encoding="utf-8")

    indice: dict[tuple[str, str], str] = {}
    for materia in materias:
        norm = _normalizar(materia.get("content", ""))
        for n in PREFIXOS:
            # Primeiro a vencer fica: em caso de matérias quase idênticas na
            # mesma página, qualquer uma delas leva à página certa.
            indice.setdefault((str(materia.get("numberPage")), norm[:n]),
                              materia.get("urlTitle"))
    return indice


def resolver(dia: date, pub_name: str, pagina: str | None, texto: str,
             indices: dict[str, dict]) -> tuple[str, bool]:
    """Devolve (link, é_link_direto_da_matéria) para uma matéria do XML.

    `indices` é um dicionário de cache vivo da execução ({secao: índice}), para
    que o chamador baixe cada seção uma única vez. Falha de rede não derruba a
    rotina: cai no link de página.
    """
    secao = secao_url(pub_name)
    if secao not in indices:
        try:
            indices[secao] = carregar_indice(dia, secao)
        except Exception as erro:  # rede, layout novo, seção inexistente
            print(f"[links_dou] índice de {secao} indisponível ({erro}) — "
                  f"usando link de página.")
            indices[secao] = {}

    norm = _normalizar(texto)
    for n in PREFIXOS:
        url_title = indices[secao].get((str(pagina), norm[:n]))
        if url_title:
            return link_materia(url_title), True
    return link_pagina(dia, pub_name, pagina), False


def main() -> int:
    dia = date.fromisoformat(sys.argv[1])
    secao = sys.argv[2] if len(sys.argv) > 2 else "do3"
    indice = carregar_indice(dia, secao)
    print(f"[links_dou] {secao} {dia}: {len(indice)} chaves indexadas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
