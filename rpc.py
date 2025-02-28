import json
import threading
import time
import websocket
import requests


class DiscordRPC:
    def __init__(self, app_id, token):
        self.app_id = app_id
        self.token = token
        self.ws = None

        threading.Thread(target=self._connect).start()

    def _connect(self):
        while True:
            time.sleep(5)

            if self.ws:
                continue

            try:
                discord_gateway_url = requests.get(
                    "https://discord.com/api/gateway"
                ).json()["url"]

                websocket.enableTrace(False)
                self.ws = websocket.WebSocketApp(
                    discord_gateway_url,
                    f"{discord_gateway_url}/?v=10&encoding=json",
                    on_error=self.on_error,
                    on_close=self.on_close,
                    on_open=self.on_open,
                    on_message=self.on_message,
                )

                threading.Thread(target=self.ws.run_forever).start()

                last_pinged_since = 0
                while True:
                    if not self.ws:
                        break

                    if last_pinged_since > 10:
                        last_pinged_since = 0

                        payload = {"op": 1, "d": None}
                        self.ws.send(json.dumps(payload))

                    time.sleep(1)
                    last_pinged_since += 1

            except Exception as e:
                print(f"Websocket connection Error: {e}")

    def _process_image(self, image_url):
        url = f"https://discord.com/api/v9/applications/{self.app_id}/external-assets"
        response = requests.post(
            url,
            headers={"Authorization": self.token, "Content-Type": "application/json"},
            json={"urls": [image_url]},
        )
        data = response.json()[0]
        return f"mp:{data['external_asset_path']}"

    def send(self, activity_data):
        if not self.ws:
            return

        payload = {
            "op": 3,
            "d": {
                "since": None,
                "activities": [
                    {
                        "application_id": self.app_id,
                        "type": 2,
                        "timestamps": {
                            "start": activity_data["timestamps"]["start"] * 1000,
                            "end": activity_data["timestamps"]["end"] * 1000,
                        },
                        "name": activity_data["name"],
                        "details": activity_data["details"],
                        "state": activity_data["state"],
                        "assets": {
                            "large_image": self._process_image(
                                activity_data["image_url"]
                            ),
                        },
                    }
                ],
                "status": None,
                "afk": None,
            },
        }
        self.ws.send(json.dumps(payload))

    def clear(self):
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

    def on_open(self, ws):
        print("Websocket to discord gateway opened")

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

    def on_error(self, ws, error):
        print(f"Error: {error}")

    def on_close(self, ws, close_status, close_msg):
        self.ws = None
        print("WebSocket closed")
        print(close_msg)
