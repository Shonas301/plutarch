"""audio recording cog for per-user audio separation.

uses discord-ext-voice-recv's MultiAudioSink with UserFilter to separate
audio streams by participant, storing each as a separate wav file.
"""

import logging
import os
from datetime import UTC, datetime
from pathlib import Path

import discord
from discord.ext import commands, voice_recv

from plutarch.commands.state_interface import VoiceChannelCog, VoiceMeta
from plutarch.commands.voice_connections import (
    ChannelStateManager,
    RecorderChannelState,
)

logger = logging.getLogger(__name__)

# ensure opus is loaded
discord.opus._load_default()

# discord message character limit with some buffer
DISCORD_MESSAGE_LIMIT = 1900


class MultiUserRecordingSink(voice_recv.AudioSink):
    """audio sink that records separate wav files per user.

    uses the library's MultiAudioSink internally but provides a simpler
    interface for dynamic user management during recording sessions.

    Attributes:
        output_dir: directory where wav files are written
        session_id: unique identifier for this recording session
        user_sinks: mapping of user id to their individual wav sink
        composite_sink: optional sink for all audio mixed together
    """

    def __init__(
        self,
        output_dir: Path,
        session_id: str,
        members: list[discord.Member],
        *,
        record_composite: bool = True,
    ):
        super().__init__()
        self.output_dir = output_dir
        self.session_id = session_id
        self.record_composite = record_composite

        # create output directory if needed
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # track file paths for later transcription
        self.file_paths: dict[str, Path] = {}

        # create individual sinks per user
        self._user_sinks: dict[int, voice_recv.WaveSink] = {}
        self._user_filters: dict[int, voice_recv.UserFilter] = {}

        for member in members:
            if member.bot:
                continue
            self._add_user_sink(member)

        # optional composite recording
        self._composite_sink: voice_recv.WaveSink | None = None
        if record_composite:
            composite_path = self.output_dir / f"{session_id}_composite.wav"
            self._composite_sink = voice_recv.WaveSink(str(composite_path))
            self.file_paths["_composite"] = composite_path

    def _add_user_sink(self, member: discord.Member) -> None:
        """Add a new sink for a user who joined during recording."""
        if member.id in self._user_sinks:
            return

        safe_name = "".join(c if c.isalnum() else "_" for c in member.display_name)
        file_path = self.output_dir / f"{self.session_id}_{safe_name}_{member.id}.wav"

        sink = voice_recv.WaveSink(str(file_path))
        self._user_sinks[member.id] = sink
        self._user_filters[member.id] = voice_recv.UserFilter(sink, member)
        self.file_paths[member.display_name] = file_path
        logger.info(
            "added recording sink for user: %s -> %s", member.display_name, file_path
        )

    def wants_opus(self) -> bool:
        """We want decoded pcm data, not opus."""
        return False

    def write(
        self, user: discord.User | discord.Member | None, data: voice_recv.VoiceData
    ) -> None:
        """Write audio data to appropriate user's file and composite."""
        if user is None:
            return

        # write to user's individual file
        if user.id in self._user_sinks:
            self._user_sinks[user.id].write(user, data)
        elif isinstance(user, discord.Member) and not user.bot:
            # user joined mid-recording, create sink for them
            self._add_user_sink(user)
            self._user_sinks[user.id].write(user, data)

        # write to composite
        if self._composite_sink:
            self._composite_sink.write(user, data)

    def cleanup(self) -> None:
        """Close all file handles."""
        for sink in self._user_sinks.values():
            try:
                sink.cleanup()
            except Exception:
                logger.exception("error cleaning up user sink")

        if self._composite_sink:
            try:
                self._composite_sink.cleanup()
            except Exception:
                logger.exception("error cleaning up composite sink")

        logger.info("recording session %s cleaned up", self.session_id)


class RecordAudio(commands.Cog, VoiceChannelCog, metaclass=VoiceMeta):
    """cog for recording voice channel audio with per-user separation."""

    def __init__(self, client: commands.Bot, state_manager: ChannelStateManager):
        logger.info("initializing recording commands")
        self.client = client
        self.state_manager = state_manager
        self._active_sinks: dict[int, MultiUserRecordingSink] = {}

        # default output directory, can be configured via env
        self.output_dir = Path(os.getenv("RECORDING_OUTPUT_DIR", "./recordings"))

    @commands.command(name="record")
    async def record(self, ctx: commands.Context) -> None:
        """Start recording the current voice channel.

        creates separate audio files for each participant in the channel.
        use %stop-recording to end the session and get transcriptions.
        """
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("you need to be in a voice channel to record")
            return

        channel = ctx.author.voice.channel
        channel_id = channel.id

        # check if already recording
        if channel_id in self._active_sinks:
            await ctx.send("already recording in this channel")
            return

        # get or create channel state
        channel_state = await self.state_manager.get_or_create(channel_id, channel)

        # ensure we're connected
        if channel_state.client is None or not channel_state.client.is_connected():
            await channel_state.connect()

        if channel_state.client is None:
            await ctx.send("failed to connect to voice channel")
            return

        # create recording session
        session_id = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        session_dir = self.output_dir / f"{channel.name}_{session_id}"

        # get non-bot members
        members = [m for m in channel.members if not m.bot]
        if not members:
            await ctx.send("no users to record in this channel")
            return

        # create the multi-user sink
        sink = MultiUserRecordingSink(
            output_dir=session_dir,
            session_id=session_id,
            members=members,
            record_composite=True,
        )

        # store sink reference and update recorder state
        self._active_sinks[channel_id] = sink
        channel_state.recorder = RecorderChannelState(
            file_names={name: str(path) for name, path in sink.file_paths.items()}
        )

        # start listening
        channel_state.client.listen(sink)

        member_names = ", ".join(m.display_name for m in members)
        await ctx.send(
            f"recording started for: {member_names}\nfiles will be saved to: `{session_dir}`"
        )
        logger.info("started recording in %s for %d users", channel.name, len(members))

    @commands.command(name="stop-recording")
    async def stop_recording(self, ctx: commands.Context) -> None:
        """Stop recording and optionally transcribe the audio files."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("you need to be in a voice channel")
            return

        channel = ctx.author.voice.channel
        channel_id = channel.id

        if channel_id not in self._active_sinks:
            await ctx.send("not currently recording in this channel")
            return

        # get the sink and channel state
        sink = self._active_sinks.pop(channel_id)
        channel_state = await self.state_manager.get(channel_id)

        # stop listening
        if channel_state and channel_state.client:
            channel_state.client.stop_listening()

        # cleanup the sink (closes files)
        sink.cleanup()

        # gather file info
        file_info = "\n".join(
            f"- {name}: `{path}`" for name, path in sink.file_paths.items()
        )
        await ctx.send(f"recording stopped. files saved:\n{file_info}")

        # attempt transcription if whisper is available
        await self._try_transcribe(ctx, sink.file_paths)

        # clear recorder state
        if channel_state:
            channel_state.recorder = None

        logger.info("stopped recording in %s", channel.name)

    async def _try_transcribe(
        self, ctx: commands.Context, file_paths: dict[str, Path]
    ) -> None:
        """Attempt to transcribe files if whisper is available."""
        try:
            from plutarch.transcribe.transcribe_wav import wav_to_text
        except ImportError:
            await ctx.send("whisper not installed, skipping transcription")
            return

        await ctx.send("transcribing audio files...")

        transcriptions = []
        for name, path in file_paths.items():
            if name == "_composite":
                continue  # skip composite for transcription
            try:
                text = await wav_to_text(str(path))
                if text and text.strip():
                    transcriptions.append(f"**{name}**: {text}")
            except Exception as e:
                logger.exception("error transcribing %s", path)
                transcriptions.append(f"**{name}**: (transcription failed: {e})")

        if transcriptions:
            # send in chunks to avoid message length limits
            result = "\n\n".join(transcriptions)
            if len(result) > DISCORD_MESSAGE_LIMIT:
                for t in transcriptions:
                    await ctx.send(t[:DISCORD_MESSAGE_LIMIT])
            else:
                await ctx.send(result)
        else:
            await ctx.send("no transcriptions generated (possibly no speech detected)")

    @commands.command(name="recording-status")
    async def recording_status(self, ctx: commands.Context) -> None:
        """Check if recording is active in the current channel."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("you need to be in a voice channel")
            return

        channel_id = ctx.author.voice.channel.id
        if channel_id in self._active_sinks:
            sink = self._active_sinks[channel_id]
            users = [name for name in sink.file_paths if name != "_composite"]
            await ctx.send(f"recording active for: {', '.join(users)}")
        else:
            await ctx.send("not recording in this channel")

    async def leave_voice_channel(
        self, channel: discord.VoiceChannel | discord.StageChannel
    ) -> None:
        """Cleanup when leaving a voice channel."""
        channel_id = channel.id

        # stop recording if active
        if channel_id in self._active_sinks:
            sink = self._active_sinks.pop(channel_id)
            sink.cleanup()
            logger.info("cleaned up recording on voice channel leave: %s", channel.name)

        # cleanup channel state
        channel_state = await self.state_manager.get(channel_id)
        if (
            channel_state
            and channel_state.client
            and channel_state.client.is_connected()
        ):
            channel_state.client.stop_listening()
