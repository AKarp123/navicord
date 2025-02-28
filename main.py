import config
import requests
import time
import threading
import json
import os

from rpc import DiscordRPC


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

    started_at = None
    ends_at = None

    image_url = None

    def _filter_nowplaying(entry):
        return [
            player
            for player in entry
            if player["username"] == config.NAVIDRONE_USERNAME
        ]

    @classmethod
    def set(cls, skip_none_check=False, **kwargs):
        image_url = kwargs.get("image_url")
        if image_url:
            cls.image_url = image_url

        id = kwargs.get("id")
        duration = kwargs.get("duration")
        artist = kwargs.get("artist")
        album = kwargs.get("album")
        title = kwargs.get("title")
        album_id = kwargs.get("album_id")

        if (
            None in [id, duration, artist, album, title, album_id]
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
        cls.started_at = time.time()
        cls.ends_at = cls.started_at + (duration or 0)

    @classmethod
    def _grab_subsonic(cls):
        res = requests.get(
            f"{config.NAVIDRONE_SERVER}/rest/getNowPlaying",
            params={
                "u": config.NAVIDRONE_USERNAME,
                "p": config.NAVIDRONE_PASSWORD,
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

            cls.set(
                id=nowPlaying["id"],
                duration=nowPlaying["duration"],
                artist=nowPlaying["artist"],
                album=nowPlaying["album"],
                title=nowPlaying["title"],
                album_id=nowPlaying["albumId"],
            )

    @classmethod
    def _grab_lastfm(cls):
        if PersistentStore.has(cls.album_id):
            cls.set(image_url=PersistentStore.get(cls.album_id))

        res = requests.get(
            "https://ws.audioscrobbler.com/2.0/",
            params={
                "method": "album.getinfo",
                "api_key": config.LASTFM_API_KEY,
                "artist": cls.artist,
                "album": cls.album,
                "format": "json",
            },
        )

        if res.status_code == 200:
            image_url = res.json()["album"]["image"][3]["#text"]

            cls.set(
                image_url=image_url,
            )

            PersistentStore.set(cls.album_id, image_url)

    @classmethod
    def grab(cls):
        cls._grab_subsonic()

        if cls.artist and cls.album:
            cls._grab_lastfm()


rpc = DiscordRPC(config.DISCORD_CLIENT_ID, config.DISCORD_TOKEN)

time_passed = 5

while True:
    time.sleep(1)

    CurrentTrack.grab()

    if time_passed >= 5:
        time_passed = 0

        if CurrentTrack.id is None:
            rpc.clear()
            continue

        rpc.send(
            {
                "timestamps": {
                    "start": CurrentTrack.started_at,
                    "end": CurrentTrack.ends_at,
                },
                "name": "music",
                "details": CurrentTrack.title,
                "state": CurrentTrack.artist,
                "image_url": CurrentTrack.image_url,
            }
        )

    time_passed += 1
