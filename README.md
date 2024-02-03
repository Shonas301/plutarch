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