from typing import Callable

from domain.ports.notifier import IUserNotifier


class TelegramUserNotifier(IUserNotifier):
    def __init__(self, send_fn: Callable[..., None]) -> None:
        self._send_fn = send_fn

    def notify_user(self, user_id: int, message: str) -> None:
        self._send_fn(chat_id=user_id, message=message)
