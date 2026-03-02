from domain.ports.notifier import IGroupNotifier, IUserNotifier
from infrastructure.telegram.group_notifier import TelegramGroupNotifier
from infrastructure.telegram.user_notifier import TelegramUserNotifier


# ── TelegramGroupNotifier ─────────────────────────────────────────────────────

def test_group_notifier_implements_interface(monkeypatch, mocker):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN_DEV", "dummy-token")
    mocker.patch("requests.post")
    notifier = TelegramGroupNotifier()
    assert isinstance(notifier, IGroupNotifier)


def test_group_notifier_sends_http_post(monkeypatch, mocker):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN_DEV", "dummy-token")
    mock_post = mocker.patch("requests.post")

    notifier = TelegramGroupNotifier()
    notifier.notify_group("Booking confirmed!")

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    url = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("url", "")
    params = call_kwargs.kwargs.get("params", {})
    assert "/sendMessage" in url
    assert params.get("chat_id") == -1002328222855
    assert params.get("text") == "Booking confirmed!"


def test_group_notifier_uses_correct_token(monkeypatch, mocker):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN_DEV", "test-token-123")
    mock_post = mocker.patch("requests.post")

    notifier = TelegramGroupNotifier()
    notifier.notify_group("hello")

    call_args = mock_post.call_args
    url = call_args.args[0] if call_args.args else call_args.kwargs.get("url", "")
    assert "bottest-token-123" in url


# ── TelegramUserNotifier ──────────────────────────────────────────────────────

def test_user_notifier_implements_interface(mocker):
    send_fn = mocker.Mock()
    notifier = TelegramUserNotifier(send_fn)
    assert isinstance(notifier, IUserNotifier)


def test_user_notifier_sends_message_to_user(mocker):
    send_fn = mocker.Mock()
    notifier = TelegramUserNotifier(send_fn)

    notifier.notify_user(user_id=12345, message="Your class is booked!")

    send_fn.assert_called_once_with(chat_id=12345, message="Your class is booked!")


def test_user_notifier_passes_user_id_as_chat_id(mocker):
    send_fn = mocker.Mock()
    notifier = TelegramUserNotifier(send_fn)

    notifier.notify_user(user_id=99999, message="test")

    call_kwargs = send_fn.call_args.kwargs
    assert call_kwargs["chat_id"] == 99999
