#!/usr/bin/env python3
"""Coleta do DOU via INLABS (Imprensa Nacional).

Faz login com as credenciais das env vars INLABS_LOGIN / INLABS_SENHA, baixa os
zips XML das seções do dia e extrai os arquivos em data/raw/dou/AAAA-MM-DD/.

Uso:
    python scripts/coleta_inlabs.py             # edições de hoje
    python scripts/coleta_inlabs.py 2026-08-05  # data específica (AAAA-MM-DD)

Endpoints (verificados em 2026-08-09, com a edição de 07/08/2026):
    GET  {BASE}/logar.php                            -> semeia cookies (obrigatório)
    POST {BASE}/logar.php  email/password            -> inlabs_session_cookie
    GET  {BASE}/index.php?p=AAAA-MM-DD&dl=AAAA-MM-DD-DOx.zip  -> zip de XMLs
"""

import io
import os
import sys
import time
import zipfile
from datetime import date
from pathlib import Path

import requests

# Endereço oficial do INLABS. Vale nos headers que o WAF confere (Origin e
# Referer), mesmo quando a coleta passa por relay.
SITE_OFICIAL = "https://inlabs.in.gov.br"

# De onde baixar. `INLABS_BASE_URL` aponta para o relay quando o ambiente não
# alcança o site (docs/ISSUES.md §1). Vazio = site oficial.
# Ex.: https://relay.exemplo.host/inlabs
BASE_URL = (os.environ.get("INLABS_BASE_URL") or SITE_OFICIAL).rstrip("/")
# Seções baixadas por padrão: 1 (atos/decisões) e 3 (extratos/avisos de penalidade).
# Seção 2 (pessoal) raramente traz lead — acrescente "DO2" se necessário.
SECOES = ["DO1", "DO3"]
DESTINO = Path(__file__).resolve().parent.parent / "data" / "raw" / "dou"

# O INLABS fica atrás de um WAF que devolve 502 para POST "pelado". Ele exige
# cara de navegador e os cookies de desafio (TS*) que só a página de login
# entrega — daí o GET antes do POST e os headers abaixo.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
    # Sempre o site oficial: é o que o WAF espera ver. Com o hostname do relay
    # aqui, o POST de login volta a ser recusado.
    "Origin": SITE_OFICIAL,
    "Referer": f"{SITE_OFICIAL}/logar.php",
}


TENTATIVAS = 5


def _login_em(base: str) -> requests.Session:
    """Tenta o login numa base (site oficial ou relay), com retry para o 502.

    O 502 do WAF é intermitente — a mesma requisição alterna entre sucesso e
    falha em minutos. Por isso o retry com espera crescente: sem ele a rotina
    perde o DOU do dia por uma instabilidade que passa sozinha.
    """
    login = os.environ["INLABS_LOGIN"]
    senha = os.environ["INLABS_SENHA"]

    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS + 1):
        s = requests.Session()
        s.headers.update(HEADERS)
        try:
            s.get(f"{base}/logar.php", timeout=60)  # semeia PHPSESSID + cookies do WAF
            resp = s.post(f"{base}/logar.php",
                          data={"email": login, "password": senha}, timeout=90)
            resp.raise_for_status()
            if "inlabs_session_cookie" in s.cookies:
                return s
            # 200 sem cookie: no site oficial é credencial recusada; via relay
            # pode ser o relay degradando o fluxo de login (visto em 13/08/2026
            # — a mesma credencial logava direto). Insistir na mesma base não
            # adianta; quem decide o fallback é _sessao_logada().
            raise RuntimeError(
                f"login em {base} retornou 200 sem cookie de sessão"
            )
        except requests.HTTPError as erro:
            ultimo_erro = erro
            espera = 10 * tentativa
            print(f"[coleta_inlabs] login falhou ({erro.response.status_code}), "
                  f"tentativa {tentativa}/{TENTATIVAS} — nova tentativa em {espera}s.")
            time.sleep(espera)

    raise RuntimeError(f"INLABS indisponível após {TENTATIVAS} tentativas: {ultimo_erro}")


def _sessao_logada() -> tuple[requests.Session, str]:
    """Sessão autenticada + base que funcionou (downloads usam a mesma base).

    Tenta a BASE_URL configurada (relay, se INLABS_BASE_URL estiver definida)
    e, se o login falhar lá, cai para o site oficial. O fallback existe porque
    em 13/08/2026 o POST de login via relay voltou 200 sem cookie enquanto o
    acesso direto funcionava (docs/ISSUES.md §0) — e o inverso também já
    ocorreu (proxy do ambiente recusando .gov.br). Tentar as duas bases cobre
    os dois cenários; a base que não é alcançável falha rápido.
    """
    bases = [BASE_URL]
    if BASE_URL != SITE_OFICIAL:
        bases.append(SITE_OFICIAL)

    erros: list[str] = []
    for base in bases:
        try:
            s = _login_em(base)
            if base != bases[0]:
                print(f"[coleta_inlabs] login via {bases[0]} falhou; "
                      f"seguindo pelo acesso direto ({base}).")
            return s, base
        except (RuntimeError, requests.RequestException) as erro:
            erros.append(f"{base}: {erro}")

    raise RuntimeError(
        "Login INLABS falhou em todas as bases — se o motivo for '200 sem "
        "cookie' nas duas, conferir INLABS_LOGIN/INLABS_SENHA; só numa delas, "
        "o problema é a rota (relay ou proxy), não a credencial. Detalhes: "
        + " | ".join(erros)
    )


def baixar_dia(dia: date) -> list[Path]:
    """Baixa e extrai os zips XML das seções configuradas. Retorna as pastas extraídas."""
    s, base = _sessao_logada()
    dia_str = dia.strftime("%Y-%m-%d")
    pasta_dia = DESTINO / dia_str
    pasta_dia.mkdir(parents=True, exist_ok=True)
    extraidos: list[Path] = []

    for secao in SECOES:
        # Endpoint conferido em 09/08/2026 (edição de 07/08: DO1 e DO3 baixaram).
        nome_zip = f"{dia_str}-{secao}.zip"
        url = f"{base}/index.php?p={dia_str}&dl={nome_zip}"
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
