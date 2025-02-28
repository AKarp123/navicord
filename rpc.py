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
        self._connect()

    def _connect(self):
        discord_gateway_url = requests.get("https://discord.com/api/gateway").json()[
            "url"
        ]
        self.ws = websocket.WebSocketApp(
            f"{discord_gateway_url}/?v=10&encoding=json",
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open,
        )
        self.ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        self.ws_thread.start()

    def _process_image(self, image_url):
        url = f"https://discord.com/api/v9/applications/{self.app_id}/external-assets"
        response = requests.post(
            url,
            headers={"Authorization": self.token, "Content-Type": "application/json"},
            json={"urls": [image_url]},
        )
        data = response.json()[0]
        return f"mp:{data['external_asset_path']}"

    def _send_heartbeat(self):
        while True:
            time.sleep(5)
            payload = {"op": 1, "d": None}
            self.ws.send(json.dumps(payload))

    def send(self, activity_data):
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
        ws.send(
            json.dumps(
                {
                    "op": 2,
                    "d": {
                        "token": self.token,
                        "intents": 0,
                        "properties": {
                            "os": "python",
                            "browser": "Discord Client",
                            "device": "Discord Client",
                        },
                    },
                }
            )
        )
        threading.Thread(target=self._send_heartbeat, daemon=True).start()

    def on_error(self, ws, error):
        print(f"Error: {error}")

    def on_close(self, ws, close_status, close_msg):
        print("WebSocket closed, trying reconnect")
        print(close_msg)

        time.sleep(10)
        self._connect()  # retry per 10 seconds
