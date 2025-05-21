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
            logging.warning("Cannot send activity: Not connected to Discord.")
            return

        try:
            # Ensure assets dictionary and large_image key exist before processing
            if "assets" not in activity_data: activity_data["assets"] = {}
            large_image_url = activity_data["assets"].get("large_image")
            
            activity_data["assets"]["large_image"] = self._process_image(large_image_url)
            
            payload = {
                "op": 3,
                "d": {
                    "since": None, # time.time() * 1000 if you want to show "elapsed"
                    "activities": [activity_data],
                    "status": "idle", # Or "online", "dnd", "invisible"
                    "afk": False, # Or True
                },
            }
            self.ws.send(json.dumps(payload))
            logging.debug("Activity payload sent.")
        except Exception as e:
            logging.error(f"Error sending activity: {e}")
            # If sending fails, it might indicate a dead connection.
            # Set connected to False; the manager loop or _on_close should handle it.
            self.connected = False 
            if self.ws:
                try: self.ws.close()
                except: pass
            # self.ws will be set to None by _on_close or connection manager

    def clear_activity(self):
        
            payload = {
                "op": 3,
                "d": {
                    "since": None,
                    "activities": [None], # Sending None activity clears it
                    "status": "invisible", # Or your desired status
                    "afk": True,
                },
            }
            self.ws.send(json.dumps(payload))
            logging.debug("Clear activity payload sent.")
    
    def stop_activity(self): # Alias for clear_activity
        self.clear_activity()

