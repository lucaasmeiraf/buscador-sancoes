#!/usr/bin/env python3
"""Coleta do DODF (Diário Oficial do Distrito Federal) — acesso público, sem login.

Baixa os PDFs da edição do dia (íntegra + edições extras) e extrai o texto para
data/raw/dodf/AAAA-MM-DD/.

Onde roda: no **GitHub Actions** (`.github/workflows/coleta-dodf.yml`), não na
rotina — o ambiente de nuvem do Claude não alcança `dodf.df.gov.br`
(docs/ISSUES.md §1). Continua rodando local para teste.

Uso:
    python scripts/coleta_dodf.py             # edição de hoje
    python scripts/coleta_dodf.py 2026-08-05  # data específica (AAAA-MM-DD)

Saída (exit code): 0 = baixou; 2 = não há edição para o dia (fim de semana,
feriado — não é erro); 1 = falha de verdade.

Endpoints (verificados em 2026-08-06):
    POST {BASE}/dodf/jornal/diario  com data=<epoch da meia-noite em Brasília>
        -> JSON com "lstLinkPdf": {"INTEGRA": [{"nome", "link"}], "EDICAO EXTRA": [...]}
           onde link = "AAAA|MM_Mês|DODF NNN DD-MM-AAAA|&arquivo=<nome do pdf>"
    GET  {BASE}/dodf/jornal/visualizar-pdf?pasta=...&arquivo=...  -> o PDF

Dependência de extração de texto: pypdf (pip install pypdf).
"""

import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

import diagnostico_rede

# Endereço público do diário. É o que vale nos links entregues à cliente, mesmo
# quando a coleta passa por outro caminho.
SITE_OFICIAL = "https://dodf.df.gov.br"

# De onde baixar. `DODF_BASE_URL` existe para o plano B da issue §1: se o site
# recusar o IP do runner do GitHub, aponta-se para um relay em host já liberado
# (ex.: o servidor da Evolution API) sem tocar no código. Vazio = site oficial.
BASE_URL = (os.environ.get("DODF_BASE_URL") or SITE_OFICIAL).rstrip("/")
HOST = urlparse(BASE_URL).hostname or "dodf.df.gov.br"
DESTINO = Path(__file__).resolve().parent.parent / "data" / "raw" / "dodf"

# Brasília é UTC-3 fixo (sem horário de verão desde 2019). A API do site indexa
# as edições pelo epoch da meia-noite local do dia.
FUSO_BRASILIA = timezone(timedelta(hours=-3))

# UA de navegador completo: o WAF do INLABS recusava o UA curto, e o DODF é
# candidato ao mesmo comportamento (ver docs/ISSUES.md §1, hipótese 3).
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
    # Referer do site oficial mesmo quando a coleta vai por relay: é o que o WAF
    # do GDF espera ver, e o hostname do relay ali só daria motivo para recusa.
    "Referer": f"{SITE_OFICIAL}/",
    # Exigido pela API do diário; inofensivo nos GETs de PDF.
    "X-Requested-With": "XMLHttpRequest",
}

TENTATIVAS = 3


def _obter(metodo: str, url: str, **kwargs) -> requests.Response:
    """Requisição com retry e erro *diagnosticado* em vez de stack trace cru.

    Motivo: a rotina roda sem ninguém olhando, e "falhou o DODF" não diz se o
    problema é a allowlist do ambiente, o WAF do GDF ou o site fora do ar — três
    causas com três soluções diferentes. Ver docs/ISSUES.md §1.
    """
    ultimo = None
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            resp = requests.request(metodo, url, headers=HEADERS, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as erro:
            ultimo = erro
            if tentativa < TENTATIVAS:
                print(f"[coleta_dodf] {metodo} falhou ({erro.__class__.__name__}), "
                      f"tentativa {tentativa}/{TENTATIVAS}.")
                time.sleep(10 * tentativa)

    raise RuntimeError(diagnostico_rede.explicar(HOST, ultimo)) from ultimo


def _listar_edicao(dia: date) -> list[dict]:
    """Consulta a API do diário e retorna os PDFs da edição do dia.

    Cada item: {"pasta": "AAAA|MM_Mês|DODF NNN DD-MM-AAAA|", "arquivo": "....pdf"}.
    Inclui a íntegra e eventuais edições extras.
    """
    epoch = int(datetime(dia.year, dia.month, dia.day, tzinfo=FUSO_BRASILIA).timestamp())
    resp = _obter(
        "POST",
        f"{BASE_URL}/dodf/jornal/diario",
        data={"data": str(epoch), "pagina": 1, "tpJornal": "", "letra": ""},
        timeout=120,
    )
    lst_link_pdf = resp.json().get("lstLinkPdf") or {}

    arquivos = []
    for grupo in lst_link_pdf.values():  # "INTEGRA", "EDICAO EXTRA", ...
        for item in grupo:
            # link = "2026|08_Agosto|DODF 144 06-08-2026|&arquivo=DODF 144 ... INTEGRA.pdf"
            pasta, _, arquivo = item["link"].partition("&arquivo=")
            if arquivo:
                arquivos.append({"pasta": pasta, "arquivo": arquivo})
    return arquivos


def baixar_dia(dia: date) -> Path | None:
    """Baixa os PDFs da edição do dia e salva o texto extraído (.txt) ao lado."""
    pasta_dia = DESTINO / dia.strftime("%Y-%m-%d")
    pasta_dia.mkdir(parents=True, exist_ok=True)

    arquivos = _listar_edicao(dia)
    if not arquivos:
        print("[coleta_dodf] nenhuma edição encontrada para o dia (sem edição?).")
        return None

    baixados = []
    for item in arquivos:
        nome = item["arquivo"]
        destino_pdf = pasta_dia / nome
        print(f"[coleta_dodf] baixando {nome} ...")
        r = _obter(
            "GET",
            f"{BASE_URL}/dodf/jornal/visualizar-pdf",
            params={"pasta": item["pasta"], "arquivo": nome},
            timeout=300,
        )
        if not r.content.startswith(b"%PDF"):
            print(f"[coleta_dodf] {nome}: resposta não é PDF — pulando.")
            continue
        destino_pdf.write_bytes(r.content)
        _extrair_texto(destino_pdf)
        # r.url já vem com pasta/arquivo percent-encoded, e o endpoint responde
        # com Content-Disposition: inline — o prefiltro acrescenta "#page=N" e o
        # link abre o diário direto na página da publicação.
        numero = re.search(r"DODF\s+(\d+)", nome)
        baixados.append({
            "arquivo": nome,
            "edicao": numero.group(1) if numero else None,
            # Sempre o endereço oficial: `r.url` apontaria para o relay quando
            # DODF_BASE_URL estiver em uso, e esse link vai para a cliente.
            "url": r.url.replace(BASE_URL, SITE_OFICIAL, 1),
        })

    # Metadados que o prefiltro precisa para montar o link — o nome do arquivo
    # sozinho não permite reconstruir a URL (a "pasta" tem mês por extenso).
    (pasta_dia / "_edicao.json").write_text(
        json.dumps(baixados, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return pasta_dia


def _neutralizar_cryptography_quebrada() -> None:
    """Impede que uma cryptography de sistema podre derrube o import do pypdf.

    A imagem da VM da nuvem traz uma cryptography cujo binding Rust não acha
    `_cffi_backend` e explode com PanicException — que o fallback do pypdf
    (escrito para ImportError) não captura. Sondamos o binding antes: se
    estourar, bloqueamos o pacote em sys.modules, o `import cryptography` do
    pypdf vira ImportError e ele cai no provider puro-Python. Nada se perde —
    cryptography só serviria para PDF criptografado, e o DODF não é.
    """
    import os
    import sys

    # O pânico do binding Rust escreve direto no fd 2 antes de virar exceção —
    # sem o silenciador, o stderr ganha um "ModuleNotFoundError ... panicked"
    # que parece falha e confunde quem lê o log (a extração segue normal).
    quebrada = False
    stderr_original = os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, 2)
        try:
            import cryptography.hazmat.bindings._rust  # noqa: F401
        except BaseException:  # PanicException herda de BaseException
            quebrada = True
    finally:
        os.dup2(stderr_original, 2)
        os.close(devnull)
        os.close(stderr_original)

    if not quebrada:
        return
    for mod in [m for m in sys.modules if m.split(".")[0] == "cryptography"]:
        del sys.modules[mod]
    sys.modules["cryptography"] = None  # None => import levanta ImportError
    print("[coleta_dodf] cryptography do sistema está quebrada — neutralizada; "
          "o pypdf segue no fallback puro-Python (suficiente: o DODF não é "
          "criptografado).")


def _extrair_texto(pdf: Path) -> None:
    """Extrai o texto do PDF para um .txt ao lado (insumo do prefiltro)."""
    _neutralizar_cryptography_quebrada()
    from pypdf import PdfReader  # import tardio: só é preciso se houver edição

    reader = PdfReader(str(pdf))
    # Uma página por bloco, separadas por marcador — o prefiltro usa isso para
    # apontar a página da publicação no link do lead.
    texto = "\n\n===PAGINA===\n\n".join(p.extract_text() or "" for p in reader.pages)
    pdf.with_suffix(".txt").write_text(texto, encoding="utf-8")


def main() -> int:
    dia = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    # 2 (e não 1) quando não há edição: o workflow precisa separar "dia sem
    # diário", que é normal e deve publicar lista vazia, de "coleta quebrou".
    return 0 if baixar_dia(dia) else 2


if __name__ == "__main__":
    raise SystemExit(main())
