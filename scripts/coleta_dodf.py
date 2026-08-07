#!/usr/bin/env python3
"""Coleta do DODF (Diário Oficial do Distrito Federal) — acesso público, sem login.

Baixa a edição do dia (PDF) e extrai o texto para data/raw/dodf/AAAA-MM-DD/.

Uso:
    python scripts/coleta_dodf.py             # edição de hoje
    python scripts/coleta_dodf.py 2026-08-05  # data específica (AAAA-MM-DD)

Esqueleto: o site do DODF lista os arquivos da edição por um endpoint de diretório
(datas em pastas "AAAA/MM_Mês/DODF NNN DD-MM-AAAA"). Conferir o formato exato na
primeira execução real (comentários TODO).

Dependência de extração de texto: pypdf (pip install pypdf).
"""

import sys
from datetime import date
from pathlib import Path

import requests

BASE_URL = "https://dodf.df.gov.br"
DESTINO = Path(__file__).resolve().parent.parent / "data" / "raw" / "dodf"

MESES = {
    1: "01_Janeiro", 2: "02_Fevereiro", 3: "03_Março", 4: "04_Abril",
    5: "05_Maio", 6: "06_Junho", 7: "07_Julho", 8: "08_Agosto",
    9: "09_Setembro", 10: "10_Outubro", 11: "11_Novembro", 12: "12_Dezembro",
}


def _listar_edicao(dia: date) -> list[dict]:
    """Consulta o endpoint de listagem do site e retorna os arquivos da edição do dia.

    TODO(1ª execução): confirmar endpoint. Padrão conhecido do site:
      GET {BASE}/listar?dir=AAAA/MM_Mês  -> lista as edições do mês (JSON)
      GET {BASE}/listar?dir=AAAA/MM_Mês/DODF NNN DD-MM-AAAA -> arquivos da edição
    e o download em {BASE}/index/visualizar-arquivo/?pasta=...&arquivo=...
    """
    dir_mes = f"{dia.year}/{MESES[dia.month]}"
    resp = requests.get(f"{BASE_URL}/listar", params={"dir": dir_mes}, timeout=120)
    resp.raise_for_status()
    listagem = resp.json()

    sufixo = dia.strftime("%d-%m-%Y")
    edicoes = [nome for nome in listagem.get("data", []) if nome.endswith(sufixo)]
    if not edicoes:
        return []

    arquivos = []
    for edicao in edicoes:  # pode haver edição extra além da normal
        r = requests.get(f"{BASE_URL}/listar", params={"dir": f"{dir_mes}/{edicao}"}, timeout=120)
        r.raise_for_status()
        for arq in r.json().get("data", []):
            arquivos.append({"pasta": f"{dir_mes}/{edicao}", "arquivo": arq})
    return arquivos


def baixar_dia(dia: date) -> Path | None:
    """Baixa os PDFs da edição do dia e salva o texto extraído (.txt) ao lado."""
    pasta_dia = DESTINO / dia.strftime("%Y-%m-%d")
    pasta_dia.mkdir(parents=True, exist_ok=True)

    arquivos = _listar_edicao(dia)
    if not arquivos:
        print("[coleta_dodf] nenhuma edição encontrada para o dia (sem edição?).")
        return None

    for item in arquivos:
        nome = item["arquivo"]
        destino_pdf = pasta_dia / nome
        print(f"[coleta_dodf] baixando {nome} ...")
        r = requests.get(
            f"{BASE_URL}/index/visualizar-arquivo/",
            params={"pasta": item["pasta"], "arquivo": nome},
            timeout=300,
        )
        r.raise_for_status()
        destino_pdf.write_bytes(r.content)
        _extrair_texto(destino_pdf)

    return pasta_dia


def _extrair_texto(pdf: Path) -> None:
    """Extrai o texto do PDF para um .txt ao lado (insumo do prefiltro)."""
    from pypdf import PdfReader  # import tardio: só é preciso se houver edição

    reader = PdfReader(str(pdf))
    # Uma página por bloco, separadas por marcador — o prefiltro usa isso para
    # apontar a página da publicação no link do lead.
    texto = "\n\n===PAGINA===\n\n".join(p.extract_text() or "" for p in reader.pages)
    pdf.with_suffix(".txt").write_text(texto, encoding="utf-8")


def main() -> int:
    dia = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    return 0 if baixar_dia(dia) else 1


if __name__ == "__main__":
    raise SystemExit(main())
