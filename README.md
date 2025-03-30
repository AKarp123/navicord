# Navicord

A _headless_ Discord Rich Presence client for [Navidrome](https://www.navidrome.org/), with automatic album art fetching and timestamps

## Install & first setup

1. Install dependencies: `pip -r requirements.txt`

2. Create an .env file with the following variables:

```makefile
DISCORD_CLIENT_ID=805831541070495744 # doesn't really matter
DISCORD_TOKEN=<your_discord_token> # this is used to set your rpc headlessly
LASTFM_API_KEY=<your_lastfm_api_key> # we get album art from lastfm
NAVIDROME_SERVER=<your_navidrome_server_url> # this should look like http(s)://music.logix.lol, mind the no trailing slash
NAVIDROME_USERNAME=<your_navidrome_username>
NAVIDROME_PASSWORD=<your_navidrome_password>
```

## Other setup

There are also a few other variables that can be set in the environment file:

| Variable      | Description            | Possible Values                  |
| ------------- | ---------------------- | -------------------------------- |
| ACTIVITY_NAME | Sets the activity name | ARTIST, ALBUM, TRACK, any string |

### Contributing

If you find a bug or have a suggestion, please [open an issue](https://github.com/logixism/navicord).
If you want to contribute, please [fork the repository](https://github.com/logixism/navicord/fork) and create a pull request. Thanks!
