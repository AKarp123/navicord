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
        # self.uri = "wss://gateway.discord.gg/?encoding=json&v=9" # Gateway URL is fetched dynamically
        self.connected = False
        self.reconnect_delay = 5
        self.connecting = False # True if a connection attempt is currently in progress
        
        self.ping_thread = None
        self.heartbeat_interval_sec = 41.25  # Default, will be updated by HELLO

        # Main connection management thread
        self.connection_thread = threading.Thread(target=self._connect_loop_manager, name="RPCConnectionManager", daemon=True)
        self.connection_thread.start()

    def _send_identify(self):
        logging.info("Sending IDENTIFY payload.")
        try:
            if not self.ws or not getattr(self.ws, 'sock', None) or not self.ws.sock.connected:
                logging.error("Cannot send IDENTIFY, WebSocket is not connected or available.")
                if self.ws:
                    try: self.ws.close() # This should trigger _on_close if not already closing
                    except Exception: pass
                # State will be reset by _on_close or connection manager
                return

            identify_payload = {
                "op": 2,
                "d": {
                    "token": self.token,
                    "intents": 0,  # For RPC, typically no intents are needed
                    "properties": {
                        "os": "Windows 10", # These can be customized
                        "browser": "navicord_rpc_client",
                        "device": "navicord_rpc_client",
                    },
                },
            }
            self.ws.send(json.dumps(identify_payload))
            logging.info("IDENTIFY payload sent successfully.")
        except Exception as e:
            logging.error(f"Error sending IDENTIFY payload: {e}")
            if self.ws:
                try: self.ws.close()
                except Exception: pass
            # Let _on_close handle full state reset.

    def _ping_loop(self, current_heartbeat_interval):
        logging.info(f"Ping loop started with interval {current_heartbeat_interval:.2f}s.")
        try:
            while self.connected and self.ws:
                # Break sleep into smaller chunks to react to disconnects faster
                sleep_end_time = time.time() + current_heartbeat_interval
                while time.time() < sleep_end_time:
                    if not self.connected or not self.ws:
                        logging.info("Ping loop: Connection state changed during sleep. Exiting.")
                        return
                    time.sleep(0.5) # Check connection state every 0.5s

                if not self.connected or not self.ws: # Final check
                    logging.info("Ping loop: Connection lost before sending ping. Exiting.")
                    return

                logging.debug(f"Sending heartbeat (op 1), sequence: {self.seq}")
                self.ws.send(json.dumps({"op": 1, "d": self.seq}))
        except websocket.WebSocketConnectionClosedException:
            logging.info("Ping loop: WebSocket connection closed. Exiting.")
        except AttributeError: # e.g. self.ws became None mid-operation
            logging.info("Ping loop: WebSocket attribute error (likely None). Exiting.")
        except Exception as e:
            logging.error(f"Ping loop: Unhandled error: {e}. Exiting.")
        finally:
            logging.info("Ping loop ended.")

    def _connect_loop_manager(self):
        while True: # This outer loop ensures we always try to maintain a connection
            if self.connected and self.ws:
                # If connected, wait for disconnection
                while self.connected and self.ws:
                    time.sleep(1)
                # Exited loop: means disconnected or ws became None
                logging.info("Detected disconnection in manager loop.")
                # Fall through to reconnection logic with backoff

            # Attempt to establish a connection if not already trying
            if not self.connecting and not self.connected:
                self.connecting = True # Signal that we are initiating a connection attempt
                self.ws = None # Ensure ws is None before new attempt
                try:
                    logging.info("Attempting to connect to Discord gateway...")
                    gateway_response = requests.get("https://discord.com/api/gateway", timeout=10)
                    gateway_response.raise_for_status()
                    discord_gateway_url = gateway_response.json()["url"]
                    
                    # Append encoding and version if not already present (Discord usually includes it)
                    if "?encoding=json&v=" not in discord_gateway_url:
                       discord_gateway_url += "?encoding=json&v=9"
                    
                    logging.info(f"Gateway URL: {discord_gateway_url}")

                    current_ws_instance = websocket.WebSocketApp(
                        discord_gateway_url,
                        on_message=self._on_message,
                        on_error=self._on_error,
                        on_close=self._on_close,
                        on_open=self._on_open,
                    )
                    self.ws = current_ws_instance # Assign to self.ws so callbacks can use it

                    # Run WebSocketApp in its own thread
                    ws_thread = threading.Thread(target=current_ws_instance.run_forever, name="WebSocketClientLibThread", daemon=True)
                    ws_thread.start()

                    # Wait for the connection attempt to resolve (either connected or failed)
                    # self.connecting will be set to False by _on_message (READY) or by _on_error/_on_close
                    connect_attempt_timeout = 30.0 # seconds
                    start_time = time.time()
                    
                    while self.connecting and (time.time() - start_time < connect_attempt_timeout):
                        time.sleep(0.1) # Short sleep while waiting for callbacks
                    
                    if self.connecting: # Timed out waiting for READY or error callback
                        logging.error("Connection attempt timed out. Closing WebSocket instance.")
                        self.connecting = False # Reset flag
                        if self.ws == current_ws_instance: # Ensure it's the instance we started
                           try: current_ws_instance.close() # This should trigger _on_close
                           except Exception as e_close: logging.error(f"Error closing timed-out ws: {e_close}")
                        # self.ws will be set to None by _on_close hopefully

                except requests.exceptions.RequestException as e_req:
                    logging.error(f"Failed to get Discord gateway URL: {e_req}")
                    self.connecting = False # Reset flag
                    self.ws = None # Ensure ws is cleared
                except Exception as e_conn:
                    logging.error(f"Error during connection setup process: {e_conn}")
                    self.connecting = False # Reset flag
                    if self.ws: # If ws was assigned
                        try: self.ws.close()
                        except Exception: pass
                    self.ws = None # Ensure ws is cleared
            
            # If connection attempt failed or we disconnected, apply backoff
            if not self.connected:
                self.connecting = False # Ensure this is false before sleeping
                logging.info(f"Disconnected or connection failed. Retrying in {self.reconnect_delay:.1f}s.")
                time.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, 60) # Exponential backoff, max 60s
            else:
                # If we are somehow here and connected, just wait a bit to avoid tight loop if state is weird
                time.sleep(1)


    def _on_message(self, ws, message):
        data = json.loads(message)
        
        if "s" in data and data["s"] is not None: # Check s is not None
            self.seq = data["s"]
        
        op = data.get("op")
        event_type = data.get("t")

        logging.debug(f"Received Op: {op}, Event: {event_type}, Data: {message[:200]}")

        if op == 10:  # Hello
            self.heartbeat_interval_sec = data['d']['heartbeat_interval'] / 1000.0
            logging.info(f"Received HELLO. Heartbeat interval: {self.heartbeat_interval_sec:.2f}s. Sending IDENTIFY.")
            self._send_identify() # Send IDENTIFY after HELLO
        
        elif op == 11: # Heartbeat ACK
            logging.debug("Received Heartbeat ACK.")

        elif op == 0: # Dispatch event
            if event_type == "READY":
                logging.info("Received READY. Discord RPC connection successful.")
                self.connected = True
                self.connecting = False # Connection attempt successful
                self.reconnect_delay = 5  # Reset reconnect delay

                # Start ping loop in its own thread
                if self.ping_thread and self.ping_thread.is_alive():
                    logging.warning("Old ping thread found alive. This is unexpected.")
                
                self.ping_thread = threading.Thread(target=self._ping_loop, args=(self.heartbeat_interval_sec,), name="RPCPingThread", daemon=True)
                self.ping_thread.start()
            else:
                logging.debug(f"Received unhandled event: {event_type}")
        else:
            logging.debug(f"Received unhandled Opcode: {op}")


    def _on_open(self, ws):
        logging.info("WebSocket connection opened by library. Waiting for HELLO from Discord.")
        # self.connecting should be True at this point, set by _connect_loop_manager
        # IDENTIFY is sent after HELLO is received in _on_message.

    def _on_error(self, ws, error):
        logging.error(f"WebSocket error reported by library: {error}")
        # This callback can be called for various reasons, sometimes before _on_close.
        # The primary handler for cleanup and state reset is _on_close.
        # Ensure critical state flags are reset to allow reconnection manager to take over.
        self.connected = False
        self.connecting = False # Signal that any active connection attempt is over/failed
        # self.ws might be closed by the library or in _on_close.
        # If self.ws is still the current instance, _on_close should handle it.
        # If not, setting self.ws = None here ensures the manager knows.
        if self.ws == ws: # Only nullify if it's our current active ws.
            self.ws = None


    def _on_close(self, ws, close_status_code, close_msg):
        logging.info(f"WebSocket closed by library: Status={close_status_code}, Msg='{close_msg}'")
        self.connected = False
        self.connecting = False # Ensure this is reset
        
        # Clear the WebSocket instance if it's the one we were using
        if self.ws == ws:
            self.ws = None
        
        logging.info("State reset due to WebSocket closure. Connection manager will handle reconnection.")
        # The _connect_loop_manager will detect self.ws is None and self.connected is False, then retry.

    def _process_image(self, image_url):
        if image_url is None:
            return self._process_image("https://i.imgur.com/hb3XPzA.png")

        if image_url.startswith("mp:"):
            return image_url

        url = f"https://discord.com/api/v9/applications/{self.app_id}/external-assets"
        try:
            response = requests.post(
                url,
                headers={"Authorization": self.token, "Content-Type": "application/json"},
                json={"urls": [image_url]},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error processing image via Discord API: {e}")
            return self._process_image("https://i.imgur.com/hb3XPzA.png") # Fallback
        except json.JSONDecodeError:
            logging.error("Error decoding Discord API response for image processing.")
            return self._process_image("https://i.imgur.com/hb3XPzA.png") # Fallback


        if not isinstance(data, list) or not data:
            logging.warning(f"Unexpected data from Discord external asset upload: {data}")
            return self._process_image("https://i.imgur.com/hb3XPzA.png")
        else:
            image = data[0].get("external_asset_path")
            if not image:
                logging.warning(f"No external_asset_path in response: {data[0]}")
                return self._process_image("https://i.imgur.com/hb3XPzA.png")


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
        if not self.ws or not self.connected:
            logging.warning("Cannot clear activity: Not connected to Discord.")
            return
            
        try:
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
        except Exception as e:
            logging.error(f"Error clearing activity: {e}")
            self.connected = False
            if self.ws:
                try: self.ws.close()
                except: pass
    
    def stop_activity(self): # Alias for clear_activity
        self.clear_activity()

    def shutdown(self): # Call this for graceful shutdown
        logging.info("Shutting down DiscordRPC client...")
        self.connected = False # Signal loops to stop
        self.connecting = False 
        if self.ws:
            try:
                self.ws.close()
            except Exception as e:
                logging.error(f"Exception during WebSocket close on shutdown: {e}")
        # Threads are daemons, they will exit when the main program exits.
        # If you need to join them, you'd store the thread objects and join them.
        # For now, daemon threads are fine.
        logging.info("DiscordRPC client shutdown initiated.")

# Example usage (for testing, not part of the class)
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(threadName)s - %(message)s')
    
    # Replace with your actual APP_ID and TOKEN for testing
    APP_ID = "YOUR_APP_ID"
    TOKEN = "YOUR_DISCORD_USER_TOKEN_OR_BOT_TOKEN_WITH_RPC_SCOPES" # User tokens are against ToS for bots.

    if APP_ID == "YOUR_APP_ID" or TOKEN == "YOUR_DISCORD_USER_TOKEN_OR_BOT_TOKEN_WITH_RPC_SCOPES":
        print("Please replace YOUR_APP_ID and YOUR_DISCORD_USER_TOKEN_OR_BOT_TOKEN_WITH_RPC_SCOPES with actual values to test.")
    else:
        rpc_client = DiscordRPC(app_id=APP_ID, token=TOKEN)
        try:
            count = 0
            while True:
                if rpc_client.connected:
                    print(f"RPC Connected. Sending sample activity update {count}...")
                    rpc_client.send_activity({
                        "name": "Test Activity",
                        "details": "Running a test",
                        "state": f"Update #{count}",
                        "timestamps": {"start": int(time.time())},
                        "assets": {"large_image": "https://i.imgur.com/kopfhMA.png", "large_text": "Test Image"}
                    })
                    count += 1
                    time.sleep(30) # Send update every 30s
                else:
                    print("RPC not connected. Waiting...")
                    time.sleep(5)
        except KeyboardInterrupt:
            print("Keyboard interrupt received. Shutting down.")
        finally:
            rpc_client.shutdown()
            print("RPC client shut down.")
