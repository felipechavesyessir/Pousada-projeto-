import os
from decimal import Decimal
from typing import Optional

from dotenv import load_dotenv
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")


def _format_brl(value: Decimal) -> str:
    normalized = f"{value:.2f}".replace(".", ",")
    return f"R$ {normalized}"


def build_status_message(nome: str, status: str, valor_restante: Decimal) -> str:
    if status == "entrada_paga":
        return (
            f"Ola, {nome}. Recebemos sua entrada com sucesso. "
            f"Valor restante da reserva: {_format_brl(valor_restante)}."
        )
    if status == "completo":
        return (
            f"Ola, {nome}. Pagamento total confirmado. "
            "Sua reserva esta 100% concluida."
        )
    return f"Ola, {nome}. Sua reserva esta em status: {status}."


def notify_status_update(reserva: object, status: str) -> Optional[str]:
    nome = getattr(reserva, "nome", "Hospede")
    telefone = getattr(reserva, "telefone", "")
    valor_restante = getattr(reserva, "valor_restante", Decimal("0.00"))
    mensagem = build_status_message(nome=nome, status=status, valor_restante=valor_restante)
    return send_whatsapp_message(message_body=mensagem, to_number=telefone)


def send_whatsapp_message(
    message_body: str,
    to_number: str,
    media_url: Optional[str] = None,
) -> Optional[str]:
    """Sends a WhatsApp message using Twilio and optionally attaches media."""
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        print("Twilio credentials are missing. Message skipped.")
        return None

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    payload = {
        "from_": TWILIO_WHATSAPP_FROM,
        "to": to_number,
        "body": message_body,
    }

    if media_url:
        payload["media_url"] = [media_url]

    try:
        message = client.messages.create(**payload)
        return message.sid
    except TwilioRestException as exc:
        print(f"Twilio send error: {exc}")
        return None
