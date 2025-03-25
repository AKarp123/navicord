from dotenv import load_dotenv
from os import getenv

load_dotenv()

ACTIVITY_NAME = (
    getenv("ACTIVITY_NAME") or "ARTIST"
)  # ARTIST | ALBUM | TRACK | (anything else for normal text)

DISCORD_CLIENT_ID = getenv("DISCORD_CLIENT_ID")
DISCORD_TOKEN = getenv("DISCORD_TOKEN")
LASTFM_API_KEY = getenv("LASTFM_API_KEY")

# don't forget http(s):// and no trailing slash
NAVIDRONE_SERVER = getenv("NAVIDRONE_SERVER")
NAVIDRONE_USERNAME = getenv("NAVIDRONE_USERNAME")
NAVIDRONE_PASSWORD = getenv("NAVIDRONE_PASSWORD")
