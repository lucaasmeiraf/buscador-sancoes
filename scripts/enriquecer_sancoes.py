#!/usr/bin/env python3
"""Enriquecimento dos leads via CEIS / CNEP (API do Portal da Transparência).

Fecha a lacuna do §2 do escopo: "uma multa contratual pode sair no DOU como
'Termo de Apenação' sem CNPJ e sem valor; o mesmo caso aparece no CEIS/CNEP já
com CNPJ e enquadramento. O lead só fica completo quando as duas pontas se
encontram."

Preenche três coisas que o diário sozinho não dá:

- `cnpj` — quando o diário traz só a razão social (§3.2);
- `link_registro_sancao` — o "link do registro de sanção" do §4.3;
- `sancoes_cadastro` — sanções anteriores da empresa, que alimentam o sinal de
  "múltiplas sanções" (§3.3) com histórico de verdade, não só o do dia.

**Nunca é gatilho de lead.** O lead nasce do diário; aqui ele só ganha dados.
Um lead que não casa com nada no cadastro continua valendo.

Requer a env var `PORTAL_TRANSPARENCIA_TOKEN` (chave gratuita em
<https://portaldatransparencia.gov.br/api-de-dados/cadastrar-email>). **Sem a
chave o script não falha**: avisa e devolve os leads intactos, para não derrubar
a rotina por causa de um enriquecimento opcional.

Uso:
    python scripts/enriquecer_sancoes.py --entrada data/leads_hoje.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

API = "https://api.portaldatransparencia.gov.br/api-de-dados"
CONSULTA_PUBLICA = "https://portaldatransparencia.gov.br/sancoes/consulta"

# A API limita requisições por minuto e responde 429 quando estoura. Uma pausa
# fixa é suficiente: são poucos leads por dia, não vale um controle mais fino.
PAUSA_SEGUNDOS = 2.0
TIMEOUT = 60


def _token() -> str | None:
    return os.environ.get("PORTAL_TRANSPARENCIA_TOKEN") or None


def so_digitos(valor: str | None) -> str:
    return re.sub(r"\D", "", valor or "")


def link_registro(termo: str) -> str:
    """Link público do registro de sanção (CEIS/CNEP) por CNPJ ou razão social."""
    return f"{CONSULTA_PUBLICA}?termo={requests.utils.quote(termo)}"


def consultar(cadastro: str, token: str, **params) -> list[dict]:
    """GET em /ceis ou /cnep. Devolve [] em qualquer falha — enriquecer é opcional."""
    try:
        resp = requests.get(
            f"{API}/{cadastro}",
            params={"pagina": 1, **params},
            headers={"chave-api-dados": token, "accept": "application/json"},
            timeout=TIMEOUT,
        )
        if resp.status_code == 429:
            print(f"[enriquecer] {cadastro}: limite de requisições — aguardando 30s.")
            time.sleep(30)
            return consultar(cadastro, token, **params)
        resp.raise_for_status()
        dados = resp.json()
        return dados if isinstance(dados, list) else []
    except requests.RequestException as erro:
        print(f"[enriquecer] {cadastro} indisponível ({erro.__class__.__name__}) — seguindo sem.")
        return []


def _cavar(registro: dict, *caminhos: str) -> str | None:
    """Primeiro valor não vazio entre vários caminhos "a.b.c" do JSON.

    A API do Portal já renomeou campos entre versões, e a rotina roda sozinha —
    tentar mais de um caminho custa nada e evita que um `KeyError` mate o
    enriquecimento inteiro.
    """
    for caminho in caminhos:
        valor: object = registro
        for parte in caminho.split("."):
            valor = valor.get(parte) if isinstance(valor, dict) else None
            if valor is None:
                break
        if isinstance(valor, str) and valor.strip():
            return valor.strip()
    return None


def _resumir(registro: dict, cadastro: str) -> dict:
    """Extrai o essencial de um registro de sanção, guardando o bruto por segurança."""
    return {
        "cadastro": cadastro.upper(),
        "tipo": _cavar(registro, "tipoSancao.descricaoResumida", "tipoSancao.descricao",
                       "descricaoResumida"),
        "orgao": _cavar(registro, "orgaoSancionador.nome", "orgaoSancionador.razaoSocial"),
        "inicio": _cavar(registro, "dataInicioSancao", "dataPublicacaoSancao"),
        "fim": _cavar(registro, "dataFimSancao"),
        "cnpj": so_digitos(_cavar(registro, "sancionado.codigoFormatado", "sancionado.cpfCnpj",
                                  "pessoa.cnpjFormatado")),
        "nome": _cavar(registro, "sancionado.nome", "pessoa.nome", "pessoa.razaoSocial"),
        "bruto": registro,
    }


def enriquecer_lead(lead: dict, token: str) -> dict:
    """Acrescenta CNPJ, link do registro e histórico de sanções a um lead."""
    cnpj = so_digitos(lead.get("cnpj"))
    empresa = (lead.get("empresa") or "").strip()

    if cnpj:
        filtro = {"codigoSancionado": cnpj}
    elif empresa:
        filtro = {"nomeSancionado": empresa}
    else:
        return lead   # sem empresa nem CNPJ não há o que consultar

    achados = []
    for cadastro in ("ceis", "cnep"):
        for registro in consultar(cadastro, token, **filtro):
            achados.append(_resumir(registro, cadastro))
        time.sleep(PAUSA_SEGUNDOS)

    lead["sancoes_cadastro"] = achados
    lead["link_registro_sancao"] = link_registro(cnpj or empresa)

    # CNPJ descoberto pelo nome: só aceita se todos os achados concordarem, para
    # não colar o CNPJ da empresa errada num lead por homonímia de razão social.
    if not cnpj:
        candidatos = {a["cnpj"] for a in achados if a["cnpj"]}
        if len(candidatos) == 1:
            cnpj_novo = candidatos.pop()
            lead["cnpj"] = cnpj_novo
            lead["cnpj_origem"] = "CEIS/CNEP"
            lead["link_registro_sancao"] = link_registro(cnpj_novo)
        elif len(candidatos) > 1:
            lead["cnpj_origem"] = f"ambíguo — {len(candidatos)} CNPJs para a mesma razão social"

    # Sanção anterior no cadastro é o sinal de reincidência do §3.3 com
    # histórico real, não só o do dia.
    if achados:
        lead["multiplas_sancoes"] = True

    return lead


def main() -> int:
    parser = argparse.ArgumentParser(description="Enriquece leads via CEIS/CNEP")
    parser.add_argument("--entrada", required=True, help="JSON com os leads qualificados")
    parser.add_argument("--saida", help="JSON de saída (padrão: sobrescreve a entrada)")
    args = parser.parse_args()

    entrada = Path(args.entrada)
    leads = json.loads(entrada.read_text(encoding="utf-8"))
    if isinstance(leads, dict):
        leads = leads.get("leads", [])

    token = _token()
    if not token:
        print("[enriquecer] PORTAL_TRANSPARENCIA_TOKEN ausente — leads seguem sem "
              "CNPJ do cadastro e sem link do registro de sanção. "
              "Chave gratuita: portaldatransparencia.gov.br/api-de-dados/cadastrar-email")
        return 0

    for i, lead in enumerate(leads, start=1):
        alvo = lead.get("empresa") or lead.get("cnpj") or "?"
        print(f"[enriquecer] {i}/{len(leads)} {alvo[:60]}")
        enriquecer_lead(lead, token)

    saida = Path(args.saida) if args.saida else entrada
    saida.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")
    com_cnpj = sum(1 for l in leads if so_digitos(l.get("cnpj")))
    print(f"[enriquecer] {len(leads)} lead(s) -> {saida} ({com_cnpj} com CNPJ)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
