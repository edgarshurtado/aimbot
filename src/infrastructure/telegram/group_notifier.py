import os

import requests

from domain.ports.notifier import IGroupNotifier


def get_telegram_token() -> str:
    mode = os.getenv("MODE", "").lower()
    if mode == "prod":
        token = os.getenv("TELEGRAM_BOT_TOKEN_PROD")
    else:
        token = os.getenv("TELEGRAM_BOT_TOKEN_DEV")
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN_DEV environment variable is not set")
    return token


class TelegramGroupNotifier(IGroupNotifier):
    _GROUP_ID = -1002328222855

    def __init__(self) -> None:
        self._token = get_telegram_token()

    def notify_group(self, message: str) -> None:
        requests.post(
            f"https://api.telegram.org/bot{self._token}/sendMessage",
            params={"chat_id": self._GROUP_ID, "text": message},
        )
