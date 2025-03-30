# Navicord

A _headless_ Discord Rich Presence client for [Navidrome](https://www.navidrome.org/), with automatic album art fetching and timestamps

## Necessary setup
Create an .env file with the following variables:

```env
DISCORD_CLIENT_ID=805831541070495744 # doesn't really matter
DISCORD_TOKEN=<your_discord_token> # this is used to set your rpc headlessly https://github.com/NotNexuss/Get-Discord-Token
LASTFM_API_KEY=<your_lastfm_api_key> # we get album art from lastfm https://www.last.fm/api
NAVIDROME_SERVER=<your_navidrome_server_url> # this should look like http(s)://music.logix.lol, mind the no trailing slash
NAVIDROME_USERNAME=<your_navidrome_username>
NAVIDROME_PASSWORD=<your_navidrome_password>
```

## Other setup

There are also a few other variables that can be set in the environment file:

| Variable      | Description            | Possible Values                  |
| ------------- | ---------------------- | -------------------------------- |
| ACTIVITY_NAME | Sets the activity name | ARTIST, ALBUM, TRACK, any string |

## Run the server
### Using docker
To run the server with docker, you can use the following command:
```bash
docker compose up
```

### Using python
To run the server with python, you can use the following commands:

First, install the dependencies (needs to be done only the first time)
```bash
pip install -r requirements.txt
```

Then, run the server
```bash
python main.py
```

### Contributing

If you find a bug or have a suggestion, please [open an issue](https://github.com/logixism/navicord).
If you want to contribute, please [fork the repository](https://github.com/logixism/navicord/fork) and create a pull request. Thanks!
