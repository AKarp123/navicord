import config
import requests
import time
import threading
import json
import os

from rpc import DiscordRPC
import signal
import sys


class PersistentStore:
    data = {}
    has_loaded = False
    lock = threading.RLock()
    filename = os.path.join(os.path.dirname(__file__), "images.json")

    @classmethod
    def get(cls, key):
        if not cls.has_loaded:
            cls.load()

        return cls.data.get(key)

    @classmethod
    def set(cls, key, value):
        if not cls.has_loaded:
            cls.load()

        with cls.lock:
            cls.data[key] = value
            cls.save()

    @classmethod
    def has(cls, key):
        if not cls.has_loaded:
            cls.load()

        return key in cls.data

    @classmethod
    def load(cls):
        try:
            with open(cls.filename) as file:
                cls.data = json.load(file)
        except FileNotFoundError:
            cls.data = {}

        cls.has_loaded = True

    @classmethod
    def save(cls):
        with cls.lock:
            with open(cls.filename + ".tmp", "w") as file:
                file.write(json.dumps(cls.data))

            os.replace(cls.filename + ".tmp", cls.filename)


class CurrentTrack:
    id = None
    album_id = None

    title = None
    artist = None
    album = None
    album_artist = None
    track_number = None
    track_total = None

    started_at = None
    ends_at = None

    image_url = None


    def _filter_nowplaying(entry):
        return [
            player
            for player in entry
            if player["username"] == config.NAVIDROME_USERNAME
        ]

    @classmethod
    def set(cls, skip_none_check=False, **kwargs):
        image_url = kwargs.get("image_url")
        cls.image_url = image_url
        

        id = kwargs.get("id")
        duration = kwargs.get("duration")
        artist = kwargs.get("artist")
        album = kwargs.get("album")
        album_artist = kwargs.get("album_artist")
        title = kwargs.get("title")
        album_id = kwargs.get("album_id")
        track_total = kwargs.get("track_total")
        track_number = kwargs.get("track_number")

        if (
            None in [id, duration, artist, album, title, album_id, track_total, track_number, album_artist]
            and not skip_none_check
        ):
            return

        if id == cls.id:
            return

        cls.id = id
        cls.album_id = album_id
        cls.title = title
        cls.artist = artist
        cls.album = album
        cls.track_total = track_total
        cls.started_at = time.time()
        cls.ends_at = cls.started_at + (duration or 0)
        cls.track_number = track_number
        cls.track_total = track_total
        cls.album_artist = album_artist
        
        print(f"Now playing: {cls.artist} - {cls.title} ({cls.album})")
        

    @classmethod
    def _grab_subsonic(cls):
        res = requests.get(
            f"{config.NAVIDROME_SERVER}/rest/getNowPlaying",
            params={
                "u": config.NAVIDROME_USERNAME,
                "p": config.NAVIDROME_PASSWORD,
                "f": "json",
                "v": "1.13.0",
                "c": "navicord",
            },
        )

        if res.status_code != 200:
            print("There was an error getting now playing: ", res.text)
            return

        try:
            json = res.json()["subsonic-response"]
        except:
            print("There was an error parsing subsonic response: ", res.text)
            return

        if len(json["nowPlaying"]) == 0:
            cls.set(skip_none_check=True)
            return

        if json["status"] == "ok" and len(json["nowPlaying"]) > 0:
            nowPlayingEntry = json["nowPlaying"]["entry"]
            nowPlayingList = cls._filter_nowplaying(nowPlayingEntry)
            

            if len(nowPlayingList) == 0:
                cls.set(skip_none_check=True)
                return

            nowPlaying = nowPlayingList[0]
            
            
            albumInfo = requests.get(
                f"{config.NAVIDROME_SERVER}/rest/getAlbum",
                params={
                    "u": config.NAVIDROME_USERNAME,
                    "p": config.NAVIDROME_PASSWORD,
                    "id": nowPlaying["albumId"],
                    "f": "json",
                    "v": "1.13.0",
                    "c": "navicord",
                },
            )
            
            
            if albumInfo.status_code == 200:
                try:
                    album_data = albumInfo.json()["subsonic-response"]["album"]
                    track_total = len(album_data["song"])
                    cls.set(
                        id=nowPlaying["id"],
                        duration=nowPlaying["duration"],
                        artist=nowPlaying["artist"],
                        album=nowPlaying["album"],
                        title=nowPlaying["title"],
                        album_id=nowPlaying["albumId"],
                        album_artist=album_data["artist"],
                        track_number=nowPlaying.get("trackNumber", 1),
                        track_total=track_total
                    )
                except Exception as e:
                    print("There was an error parsing album data: ", e)
                    track_total = None
            else:
                print("There was an error getting album info: ", albumInfo.text)
                    

    @classmethod
    def _grab_lastfm(cls):
        if PersistentStore.has(cls.album_id):
            cls.set(image_url=PersistentStore.get(cls.album_id))
            return

        res = requests.get(
            "https://ws.audioscrobbler.com/2.0/",
            params={
                "method": "album.getinfo",
                "api_key": config.LASTFM_API_KEY,
                "artist": cls.album_artist,
                "album": cls.album,
                "format": "json",
            },
        )
        if res.status_code == 200:
            image_url = res.json()["album"]["image"][3]["#text"]

            if image_url == "":
                cls.set(image_url=None)
                return

            cls.set(
                image_url=image_url,
            )

            PersistentStore.set(cls.album_id, image_url)
        else:
            print("There was an error getting lastfm: ", res.text)

    @classmethod
    def grab(cls):
        cls._grab_subsonic()

        if cls.artist and cls.album:
            cls._grab_lastfm()


rpc = DiscordRPC(config.DISCORD_CLIENT_ID, config.DISCORD_TOKEN)

time_passed = 5
activity_cleared = False
print("Starting Navicord...")
while True:
    def signal_handler(sig, frame):
        print("Exiting...")
        rpc.stop_activity()
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGQUIT, signal_handler)
    signal.signal(signal.SIGHUP, signal_handler)
    try:
        time.sleep(config.POLLING_TIME)

        CurrentTrack.grab()

        if time_passed >= 5:
            time_passed = 0

            if CurrentTrack.id is None:
                if not activity_cleared:
                    print("No track found, clearing activity...")
                    rpc.clear_activity()
                    activity_cleared = True
                continue
            if time.time() > CurrentTrack.ends_at:
                if not activity_cleared:
                    print("Track ended, clearing activity...")
                    rpc.clear_activity()
                    activity_cleared = True 
                continue

            match config.ACTIVITY_NAME:
                case "ARTIST":
                    activity_name = CurrentTrack.artist
                case "ALBUM":
                    activity_name = CurrentTrack.album
                case "TRACK":
                    activity_name = CurrentTrack.title
                case _:
                    activity_name = config.ACTIVITY_NAME

            large_text_format = f"{CurrentTrack.album_artist} - {CurrentTrack.album}" if CurrentTrack.album_artist != CurrentTrack.artist else CurrentTrack.album
            
            
            rpc.send_activity(
                {
                    "application_id": config.DISCORD_CLIENT_ID,
                    "type": 2,
                    "state": f"{CurrentTrack.artist}",
                    
                    "details": CurrentTrack.title,
                    "assets": {
                        "large_image": CurrentTrack.image_url,
                        "large_text": large_text_format + f" ({CurrentTrack.track_number} of {CurrentTrack.track_total})",
                    },
                    "timestamps": {
                        "start": CurrentTrack.started_at * 1000,
                        "end": CurrentTrack.ends_at * 1000,
                    },
                    "name": activity_name,
                }
            )
            activity_cleared = False

        time_passed += 1
    except Exception as e:
        print("There was an error: ", e)
        time.sleep(5)
        break

    
