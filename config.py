from dotenv import load_dotenv
from os import getenv

load_dotenv()

DISCORD_CLIENT_ID = 805831541070495744
DISCORD_TOKEN = getenv("DISCORD_TOKEN")
LASTFM_API_KEY = getenv("LASTFM_API_KEY")

# don't forget http(s):// and no trailing slash
NAVIDRONE_SERVER = getenv("NAVIDRONE_SERVER")
NAVIDRONE_USERNAME = getenv("NAVIDRONE_USERNAME")
NAVIDRONE_PASSWORD = getenv("NAVIDRONE_PASSWORD")
