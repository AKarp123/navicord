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
        self.connected = False
        self.reconnect_delay = 5
        self.connecting = False
        threading.Thread(target=self._connect, daemon=True).start()

    def _connect(self):
        while True:
            try:
                if self.connecting:
                    time.sleep(1)
                    continue

                if self.ws and not self.connected:
                    # Only clear activity if we have a websocket but it's not connected
                    try:
                        payload = {
                            "op": 3,
                            "d": {
                                "since": None,
                                "activities": [None],
                                "status": "invisible",
                                "afk": True,
                            },
                        }
                        self.ws.send(json.dumps(payload))
                    except:
                        pass
                    self.ws.close()
                    self.ws = None
                
                if not self.ws:
                    self.connecting = True
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
                self.connecting = False
                time.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 1.5, 30)  # Exponential backoff, max 30 seconds

    def _on_message(self, ws, message):
        data = json.loads(message)
        if "s" in data:
            self.seq = data["s"]
        if data.get("t") == "READY":
            self.connected = True
            self.connecting = False
            self.reconnect_delay = 5  # Reset delay on successful connection

    def _ping_loop(self):
        while self.ws:
            try:
                time.sleep(41.25)
                if not self.ws or not self.connected:
                    break
                    
                self.ws.send(json.dumps({"op": 1, "d": self.seq}))
            except Exception as e:
                logging.error(f"Ping error: {e}")
                self.connected = False
                self.connecting = False
                if self.ws:
                    try:
                        self.ws.close()
                    except:
                        pass
                self.ws = None
                break

    def _on_open(self, ws):
        logging.info("WebSocket to Discord gateway opened")
        try:
            if not self.ws:
                logging.error("WebSocket object is None in _on_open")
                self.connected = False
                self.connecting = False
                return
                
            if not self.ws.sock or not self.ws.sock.connected:
                logging.error("WebSocket socket is not connected in _on_open")
                self.connected = False
                self.connecting = False
                self.ws = None
                return
                
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
        except Exception as e:
            logging.error(f"Error in on_open: {e}")
            self.connected = False
            self.connecting = False
            if self.ws:
                try:
                    self.ws.close()
                except:
                    pass
            self.ws = None
            self._connect()

    def _on_error(self, ws, error):
        logging.error(f"WebSocket error: {error}")
        self.connected = False
        self.connecting = False
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
        self.ws = None
        self._connect()

    def _on_close(self, ws, close_status, close_msg):
        logging.info(f"WebSocket closed: {close_msg}")
        self.connected = False
        self.connecting = False
        self.ws = None
        self._connect()

    def _process_image(self, image_url):
        if image_url is None:
            return self._process_image("https://i.imgur.com/hb3XPzA.png")

        if image_url.startswith("mp:"):
            return image_url

        url = f"https://discord.com/api/v9/applications/{self.app_id}/external-assets"
        response = requests.post(
            url,
            headers={"Authorization": self.token, "Content-Type": "application/json"},
            json={"urls": [image_url]},
        )
        try:
            data = response.json()
        except:
            return self._process_image("https://i.imgur.com/hb3XPzA.png")

        if not isinstance(data, list):
            return self._process_image("https://i.imgur.com/hb3XPzA.png")
        else:
            image = data[0]["external_asset_path"]

        return f"mp:{image}"

    def send_activity(self, activity_data):
        if not self.ws or not self.connected:
            self._connect()
            return

        try:
            activity_data["assets"]["large_image"] = self._process_image(
                activity_data["assets"]["large_image"]
            )
            payload = {
                "op": 3,
                "d": {
                    "since": None,
                    "activities": [activity_data],
                    "status": "idle",
                    "afk": True,
                },
            }
            self.ws.send(json.dumps(payload))
        except Exception as e:
            logging.error(f"Error sending activity: {e}")
            self.connected = False
            self.connecting = False
            self._connect()

    def clear_activity(self):
        if not self.ws or not self.connected:
            self._connect()
            return
            
        try:
            payload = {
                "op": 3,
                "d": {
                    "since": None,
                    "activities": [None],
                    "status": "invisible",
                    "afk": True,
                },
            }
            self.ws.send(json.dumps(payload))
        except Exception as e:
            logging.error(f"Error clearing activity: {e}")
            self.connected = False
            self.connecting = False
            self._connect()
    
    def stop_activity(self):
        self.clear_activity()
