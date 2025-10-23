# notifier.py
"""
Envio de notificações via Telegram
Salve como: notifier.py
"""

import requests
import logging
import os

logger = logging.getLogger(__name__)

# =======================================================
# CONFIGURAÇÕES — defina via variáveis de ambiente ou fixo
# =======================================================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "SEU_TOKEN_AQUI")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "SEU_CHAT_ID_AQUI")

def send_telegram_message(message: str):
    """Função genérica para enviar mensagem ao Telegram."""
    if not BOT_TOKEN or not CHAT_ID:
        logger.warning("⚠️ Bot Telegram não configurado.")
        return False
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        r = requests.post(url, data=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem Telegram: {e}")
        return False


# =======================================================
# Notificações específicas do sistema
# =======================================================
def notify_new_viability():
    """Notifica nova solicitação de viabilidade."""
    return send_telegram_message("📬 *Nova solicitação de viabilidade recebida!*")

def notify_new_agenda_data():
    """Notifica quando o usuário envia dados de agendamento."""
    return send_telegram_message("📅 *Recebidos novos dados de agendamento!*")
