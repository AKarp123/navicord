from dotenv import load_dotenv
from os import getenv

load_dotenv()

ACTIVITY_NAME = (
    getenv("ACTIVITY_NAME") or "ARTIST"
)  # ARTIST | ALBUM | TRACK | (anything else for normal text)

POLLING_TIME = int(getenv("POLLING_TIME") or 1)

DISCORD_CLIENT_ID = getenv("DISCORD_CLIENT_ID")
DISCORD_TOKEN = getenv("DISCORD_TOKEN")
LASTFM_API_KEY = getenv("LASTFM_API_KEY")

# don't forget http(s):// and no trailing slash
NAVIDROME_SERVER = getenv("NAVIDROME_SERVER")
NAVIDROME_USERNAME = getenv("NAVIDROME_USERNAME")
NAVIDROME_PASSWORD = getenv("NAVIDROME_PASSWORD")
