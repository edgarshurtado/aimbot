import requests

class TelegramLogger:
    def __init__(self):
        self.token = "7837134549:AAFIHT8FjRQKiJ2Yb0ZrHcP8dFtgJce-fjw"
        self.group_id = -1002328222855
        self.bot_api_url = "https://api.telegram.org/bot7837134549:AAFIHT8FjRQKiJ2Yb0ZrHcP8dFtgJce-fjw/"

    def send_message(self, message: str):
        requests.post(
            self.bot_api_url + "sendMessage",
            params={"chat_id": self.group_id, "text": message})