#!/usr/bin/env python3
"""Planilha-mestre acumulada dos leads (Modelo A do escopo, §4.1).

Acrescenta os leads qualificados do dia a `data/leads.csv` — um CSV versionado no
repositório, que abre direto no Excel/Google Sheets. O WhatsApp empurra o que é
novo e urgente; a planilha guarda o histórico e o controle de status.

Duas garantias:

- **Não duplica**: a chave é o `hash` do trecho (o mesmo usado na deduplicação do
  prefiltro). Rodar duas vezes no mesmo dia não gera linha repetida.
- **Não sobrescreve o trabalho manual**: a coluna `status` é preenchida à mão
  (contatado / proposta enviada / cliente / descartado) e nunca é tocada em
  linhas já existentes.

Uso:
    python scripts/planilha.py --entrada data/leads_hoje.json
    python scripts/planilha.py --entrada data/leads_hoje.json --saida outra.csv
"""

import argparse
import csv
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLANILHA = RAIZ / "data" / "leads.csv"

# Ordem das colunas = ordem de leitura na planilha. Os campos vêm da seção 3.2 do
# escopo; `status` e `observacoes` são de preenchimento manual.
COLUNAS = [
    "data_publicacao",
    "empresa",
    "cnpj",
    "orgao_sancionador",
    "tipo_penalidade",
    "valor_multa",
    "valor_multa_texto",
    "acima_do_corte",
    "fundamento_legal",
    "objeto_contrato",
    "num_contrato_processo",
    "fase_processual",
    "prazo_estimado_defesa",
    "multiplas_sancoes",
    "fonte",
    "edicao",
    "pagina",
    "link",
    "hash",
    "status",
    "observacoes",
]


def carregar(planilha: Path) -> tuple[list[dict], set[str]]:
    """Lê a planilha existente. Retorna (linhas, hashes já presentes)."""
    if not planilha.exists():
        return [], set()
    with planilha.open(encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.DictReader(f))
    return linhas, {l.get("hash", "") for l in linhas if l.get("hash")}


def acrescentar(leads: list[dict], planilha: Path = PLANILHA) -> int:
    """Acrescenta os leads inéditos à planilha. Retorna quantos entraram."""
    linhas, vistos = carregar(planilha)

    novos = 0
    for lead in leads:
        if not lead.get("qualificado", True):
            continue
        h = lead.get("hash", "")
        if h and h in vistos:
            continue
        vistos.add(h)
        linhas.append({c: _texto(lead.get(c)) for c in COLUNAS})
        novos += 1

    planilha.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig: sem o BOM o Excel em português abre os acentos errados.
    with planilha.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(linhas)

    print(f"[planilha] {novos} lead(s) novo(s) -> {planilha} "
          f"({len(linhas)} linha(s) no total)")
    return novos


def _texto(valor) -> str:
    """Normaliza para célula de CSV (None vira vazio, bool vira SIM/NÃO)."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "SIM" if valor else "NÃO"
    if isinstance(valor, (list, dict)):
        return json.dumps(valor, ensure_ascii=False)
    return str(valor)


def main() -> int:
    parser = argparse.ArgumentParser(description="Acrescenta leads à planilha-mestre")
    parser.add_argument("--entrada", required=True,
                        help="JSON com a lista de leads qualificados do dia")
    parser.add_argument("--saida", default=str(PLANILHA), help="CSV de destino")
    args = parser.parse_args()

    leads = json.loads(Path(args.entrada).read_text(encoding="utf-8"))
    if isinstance(leads, dict):
        leads = leads.get("leads", [])
    acrescentar(leads, Path(args.saida))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
