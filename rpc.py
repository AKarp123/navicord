import json
import time
import logging
import threading
import websocket
import requests


class DiscordRPC:
    def __init__(self, app_id, token):
        self.app_id = app_id
        self.token = token
        self.ws = None
        self.seq = None
        self.uri = "wss://gateway.discord.gg/?encoding=json&v=9"
        threading.Thread(target=self._connect, daemon=True).start()

    def _connect(self):
        while True:
            time.sleep(5)
            if self.ws:
                continue
            try:
                discord_gateway_url = requests.get(
                    "https://discord.com/api/gateway"
                ).json()["url"]
                self.ws = websocket.WebSocketApp(
                    discord_gateway_url,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                    on_open=self._on_open,
                )
                threading.Thread(target=self.ws.run_forever, daemon=True).start()
                self._ping_loop()
            except Exception as e:
                logging.error(f"WebSocket connection error: {e}")

    def _on_message(self, ws, message):
        data = json.loads(message)
        if "s" in data:
            self.seq = data["s"]

    def _ping_loop(self):
        while self.ws:
            time.sleep(41.25)
            try:
                self.ws.send(json.dumps({"op": 1, "d": self.seq}))
            except Exception:
                self._connect()

    def _on_open(self, ws):
        logging.info("WebSocket to Discord gateway opened")
        self.ws.send(
            json.dumps(
                {
                    "op": 2,
                    "d": {
                        "token": self.token,
                        "intents": 0,
                        "properties": {
                            "os": "Windows 10",
                            "browser": "Discord Client",
                            "device": "Discord Client",
                        },
                    },
                }
            )
        )

    def _on_error(self, ws, error):
        logging.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status, close_msg):
        self.ws = None
        logging.info(f"WebSocket closed: {close_msg}")

    def _process_image(self, image_url):
        if image_url.startswith("mp:"):
            return image_url

        url = f"https://discord.com/api/v9/applications/{self.app_id}/external-assets"
        response = requests.post(
            url,
            headers={"Authorization": self.token, "Content-Type": "application/json"},
            json={"urls": [image_url]},
        )
        data = response.json()

        if not isinstance(data, list):
            return self._process_image("https://i.imgur.com/hb3XPzA.png")
        else:
            image = data[0]["external_asset_path"]

        return f"mp:{image}"

    def send_activity(self, activity_data):
        if not self.ws:
            return

        if "large_image" in activity_data["assets"]:
            activity_data["assets"]["large_image"] = self._process_image(
                activity_data["assets"]["large_image"]
            )

        payload = {
            "op": 3,
            "d": {
                "since": None,
                "activities": [activity_data],
                "status": "dnd",
                "afk": False,
            },
        }
        try:
            self.ws.send(json.dumps(payload))
        except Exception:
            self._connect()

    def clear_activity(self):
        if not self.ws:
            return
        payload = {
            "op": 3,
            "d": {
                "since": None,
                "activities": [None],
                "status": None,
                "afk": None,
            },
        }
        self.ws.send(json.dumps(payload))
