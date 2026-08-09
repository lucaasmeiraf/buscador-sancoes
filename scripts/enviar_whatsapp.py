#!/usr/bin/env python3
"""Envio de mensagem por WhatsApp via Evolution API (servidor próprio em nuvem).

Faz POST no endpoint sendText da instância. Toda a configuração vem de env vars:
    EVOLUTION_API_URL   ex.: https://evo.seudominio.com  (sem barra final)
    EVOLUTION_API_KEY   apikey da instância
    EVOLUTION_INSTANCE  nome da instância
    WHATSAPP_DESTINO    número de destino em formato internacional, ex.: 5561999998888

Uso:
    python scripts/enviar_whatsapp.py --texto "mensagem"
    python scripts/enviar_whatsapp.py --arquivo data/resumo.txt
ou, de outro script:
    from enviar_whatsapp import enviar_texto
    enviar_texto("Bom dia! ...")
"""

import argparse
import os
from pathlib import Path

import requests

# Conveniência de teste local (lê o .env). Na nuvem as variáveis já vêm do
# ambiente e o pacote não está instalado — por isso o import é opcional.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

def enviar_texto(texto: str) -> dict:
    """Envia `texto` para WHATSAPP_DESTINO via Evolution API. Retorna o JSON da resposta.

    Endpoint da Evolution API v2:
        POST {EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}
        header: apikey
        body:   {"number": "<destino>", "text": "<mensagem>"}
    """
    base = os.environ["EVOLUTION_API_URL"].rstrip("/")
    instancia = os.environ["EVOLUTION_INSTANCE"]
    destino = os.environ["WHATSAPP_DESTINO"]

    resp = requests.post(
        f"{base}/message/sendText/{instancia}",
        headers={
            "apikey": os.environ["EVOLUTION_API_KEY"],
            "Content-Type": "application/json",
        },
        json={"number": destino, "text": texto},
        timeout=60,
    )
    resp.raise_for_status()
    print(f"[enviar_whatsapp] enviado para {destino[:4]}*** ({len(texto)} caracteres)")
    return resp.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Envia mensagem via Evolution API")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--texto", help="mensagem literal")
    grupo.add_argument("--arquivo", help="arquivo .txt com a mensagem")
    args = parser.parse_args()

    texto = args.texto or Path(args.arquivo).read_text(encoding="utf-8")
    if not texto.strip():
        print("[enviar_whatsapp] mensagem vazia — nada enviado.")
        return 1
    enviar_texto(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
