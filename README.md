# Plutarch [IN-DEVELOPMENT]

Plutarch is a discord bot which is designed with two features in mind.

1. The ability to join a voice channel and record audio files for a session. The
    audio files generated will have a composite of all members of the channel's
    audio, as well as audio files available for each individual seperately 
2. The ability to automatically create and provide a transcript of the
    conversation contained in all pertinent audio files

## Building the Project

*Requirements*:

- `python3.12`
- `pip`
- `piptools`

### Lint

Run: `make lint`
To auto fix where possible: `make lint-fix`

### Build

Run: `make build`

### Install

Run: `make install-dev`

### Build, Test, Format, and Install

Run: `make all`

## Running

### Environment

*Required Third Party Libraries*:

- `ffmpeg`
- `opus`

1. Create a `.env` file which contains the following environment variables

```
API_BASE_URL= // Discord API endpoint
DISCORD_BOT_NAME= // name of bot in discord developer portal
DISCORD_CLIENT_ID=
DISCORD_CLIENT_SECRET=
DISCORD_TOKEN=
OAUTH2_REDIRECT_URI= // oauth callback ex: http://localhost:5000/callback when local
WHISPER_MODEL= // small,base,medium,large,huge
YT_DO"/usr/local/lib/libopus.dylib"MAIN= // www.youtube.com
FFMPEG= // location of ffmpeg cli tool
OPUS= // location of .dll or .dylib opus file ex: /usr/local/lib/libopus.dylib
```

2. Run `make all`

3. Invite the Bot to your discord server through the discord developer portal
4. Run with `python3.12 -m plutarch`