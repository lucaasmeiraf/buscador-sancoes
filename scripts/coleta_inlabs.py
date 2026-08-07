#!/usr/bin/env python3
"""Coleta do DOU via INLABS (Imprensa Nacional).

Faz login com as credenciais das env vars INLABS_LOGIN / INLABS_SENHA, baixa os
zips XML das seções do dia e extrai os arquivos em data/raw/dou/AAAA-MM-DD/.

Uso:
    python scripts/coleta_inlabs.py             # edições de hoje
    python scripts/coleta_inlabs.py 2026-08-05  # data específica (AAAA-MM-DD)

Esqueleto: a estrutura está completa; conferir na primeira execução real se os
endpoints/nomes de arquivo do INLABS continuam os mesmos (comentários TODO).
"""

import io
import os
import sys
import zipfile
from datetime import date
from pathlib import Path

import requests

BASE_URL = "https://inlabs.in.gov.br"
# Seções baixadas por padrão: 1 (atos/decisões) e 3 (extratos/avisos de penalidade).
# Seção 2 (pessoal) raramente traz lead — acrescente "DO2" se necessário.
SECOES = ["DO1", "DO3"]
DESTINO = Path(__file__).resolve().parent.parent / "data" / "raw" / "dou"


def _sessao_logada() -> requests.Session:
    """Abre sessão autenticada no INLABS (cookie de sessão)."""
    login = os.environ["INLABS_LOGIN"]
    senha = os.environ["INLABS_SENHA"]

    s = requests.Session()
    # TODO(1ª execução): confirmar endpoint e nomes dos campos do form de login.
    # Padrão conhecido do INLABS: POST em /logar.php com email/password.
    resp = s.post(f"{BASE_URL}/logar.php", data={"email": login, "password": senha}, timeout=60)
    resp.raise_for_status()
    if "inlabs_session" not in s.cookies and not s.cookies:
        raise RuntimeError("Login INLABS não retornou cookie de sessão — conferir credenciais.")
    return s


def baixar_dia(dia: date) -> list[Path]:
    """Baixa e extrai os zips XML das seções configuradas. Retorna as pastas extraídas."""
    s = _sessao_logada()
    dia_str = dia.strftime("%Y-%m-%d")
    pasta_dia = DESTINO / dia_str
    pasta_dia.mkdir(parents=True, exist_ok=True)
    extraidos: list[Path] = []

    for secao in SECOES:
        # TODO(1ª execução): confirmar URL de download. Padrão conhecido:
        #   {BASE}/index.php?p={AAAA-MM-DD}&dl={AAAA-MM-DD}-{SECAO}.zip
        nome_zip = f"{dia_str}-{secao}.zip"
        url = f"{BASE_URL}/index.php?p={dia_str}&dl={nome_zip}"
        print(f"[coleta_inlabs] baixando {nome_zip} ...")
        resp = s.get(url, timeout=300)

        if resp.status_code == 404 or not resp.content[:2] == b"PK":
            # Sem edição nesse dia/seção (feriado, fim de semana) ou resposta HTML de erro.
            print(f"[coleta_inlabs] {nome_zip} indisponível — pulando.")
            continue

        pasta_secao = pasta_dia / secao
        pasta_secao.mkdir(exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            z.extractall(pasta_secao)  # XMLs individuais, um por matéria
        extraidos.append(pasta_secao)
        print(f"[coleta_inlabs] {nome_zip} -> {pasta_secao} ({len(list(pasta_secao.iterdir()))} arquivos)")

    return extraidos


def main() -> int:
    dia = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    extraidos = baixar_dia(dia)
    if not extraidos:
        print("[coleta_inlabs] nenhuma seção baixada (dia sem edição?).")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
