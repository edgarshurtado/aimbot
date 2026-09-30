import time
from typing import Callable

from telegram.error import BadRequest, Forbidden, NetworkError, RetryAfter

from domain.ports.notifier import IUserNotifier

MAX_SEND_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0


class TelegramUserNotifier(IUserNotifier):
    def __init__(
        self,
        send_fn: Callable[..., None],
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._send_fn = send_fn
        self._sleep = sleep

    def notify_user(self, user_id: int, message: str) -> None:
        # python-telegram-bot leaves retrying to the caller. This runs on an
        # APScheduler worker thread, so blocking for a few seconds is fine.
        for attempt in range(1, MAX_SEND_ATTEMPTS + 1):
            try:
                self._send_fn(chat_id=user_id, message=message)
                return
            except (BadRequest, Forbidden):
                # Permanent: BadRequest subclasses NetworkError, so it has to be
                # excluded explicitly or an invalid request would be resent.
                raise
            except (NetworkError, RetryAfter) as exc:
                if attempt == MAX_SEND_ATTEMPTS:
                    raise
                if isinstance(exc, RetryAfter):
                    self._sleep(exc.retry_after)
                else:
                    self._sleep(BACKOFF_SECONDS * attempt)
