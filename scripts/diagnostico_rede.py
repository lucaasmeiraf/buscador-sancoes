#!/usr/bin/env python3
"""Diagnóstico de acesso às fontes — separa allowlist, WAF e site fora do ar.

Existe por causa da issue §1 de `docs/ISSUES.md`: o DODF falha no ambiente de
nuvem e funciona local, e "falhou o DODF" não diz qual das três causas foi:

1. **Allowlist do ambiente** — o proxy do Claude Cloud recusou o túnel
   (CONNECT 403 → `ProxyError`). Solução: host em Network access → Custom →
   Allowed domains, na criação do ambiente.
2. **Firewall do site** — o proxy liberou e o destino derrubou a conexão
   (reset no TLS) ou respondeu 403/503: o site recusa o IP da VM. Allowlist
   não resolve; o caminho é um relay (ex.: `DODF_BASE_URL`).
3. **Site fora do ar / lento** — 5xx ou timeout, transitório.

Cada causa tem solução diferente, então a rotina precisa dizer qual foi em vez
de despejar um stack trace.

Uso:
    python scripts/diagnostico_rede.py           # testa todos os hosts
    python scripts/diagnostico_rede.py dodf.df.gov.br
"""

from __future__ import annotations

import socket
import sys

import requests

# Hosts que a rotina precisa alcançar, com o porquê — a mesma lista que precisa
# estar na allowlist do ambiente de nuvem (docs/CONFIGURACAO.md §4.3).
HOSTS = {
    "inlabs.in.gov.br": "download do DOU (XML)",
    "www.in.gov.br": "link exato da matéria no DOU",
}

# `dodf.df.gov.br` saiu da lista: desde a issue §1 quem baixa o DODF é o GitHub
# Actions, fora deste ambiente. Continua testável por argumento
# (`python scripts/diagnostico_rede.py dodf.df.gov.br`), mas falhar aqui não é
# mais problema da rotina.

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def resolve(host: str) -> str | None:
    """IP do host, ou None se o DNS não resolver (domínio digitado errado)."""
    try:
        return socket.gethostbyname(host)
    except OSError:
        return None


def explicar(host: str, erro: Exception | None = None) -> str:
    """Frase única dizendo qual das três causas explica a falha, e o que fazer.

    Chamada pelos coletores quando desistem, para que a mensagem do WhatsApp
    diga algo acionável em vez de "erro de rede".
    """
    if resolve(host) is None:
        return (f"{host}: o nome não resolve em DNS. Confira se o domínio na "
                f"allowlist do ambiente está escrito exatamente assim — só o "
                f"hostname, sem https:// e sem barra final.")

    status = getattr(getattr(erro, "response", None), "status_code", None)

    # Ordem importa: ProxyError é subclasse de ConnectionError. As duas falhas
    # eram tratadas como uma só e o "reset by peer" do firewall do GDF foi
    # diagnosticado como allowlist por três dias (docs/ISSUES.md §1) — o curl -v
    # de 12/08/2026 mostrou que o proxy recusa com CONNECT 403, e o reset vem
    # do destino depois de o túnel abrir.
    if isinstance(erro, requests.exceptions.ProxyError) or status == 407:
        return (f"{host}: o proxy do ambiente recusou o túnel (CONNECT 403) — "
                f"bloqueio de allowlist. Acrescente '{host}' em Network access "
                f"→ Custom → Allowed domains (na criação do ambiente).")
    if isinstance(erro, requests.ConnectionError):
        return (f"{host}: o proxy liberou e a conexão foi derrubada pelo "
                f"destino (reset) — firewall do site recusando o IP desta "
                f"máquina. Allowlist não resolve; o caminho é coletar por um "
                f"relay em host que o site aceite (ex.: DODF_BASE_URL) ou de "
                f"outra rede.")
    if status in (401, 403):
        return (f"{host}: o site respondeu {status} — o domínio passou pelo "
                f"proxy e quem recusou foi o servidor (WAF). Mexer na allowlist "
                f"não resolve; é o IP da VM que está sendo barrado.")
    if isinstance(erro, requests.Timeout):
        return f"{host}: timeout. Site lento ou fora do ar — costuma passar sozinho."
    if status and status >= 500:
        return (f"{host}: o site respondeu {status}. Instabilidade do servidor — "
                f"os coletores já tentam de novo com espera crescente.")
    return f"{host}: falha não classificada ({erro!r})."


def testar(host: str) -> dict:
    """Faz um GET na raiz do host e classifica o resultado."""
    ip = resolve(host)
    if ip is None:
        return {"host": host, "ok": False, "ip": None, "motivo": explicar(host)}
    try:
        resp = requests.get(f"https://{host}/", headers={"User-Agent": UA}, timeout=60)
        resp.raise_for_status()
        return {"host": host, "ok": True, "ip": ip,
                "motivo": f"OK ({resp.status_code}, {len(resp.content)} bytes)"}
    except requests.RequestException as erro:
        return {"host": host, "ok": False, "ip": ip, "motivo": explicar(host, erro)}


def main() -> int:
    hosts = sys.argv[1:] or list(HOSTS)
    falhas = 0
    for host in hosts:
        r = testar(host)
        marca = "OK  " if r["ok"] else "FALHA"
        print(f"[{marca}] {host} ({HOSTS.get(host, '?')})")
        print(f"        ip={r['ip']}  {r['motivo']}")
        falhas += not r["ok"]
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
