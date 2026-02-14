"""tests for record_audio module."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from plutarch.commands.record_audio import (
    DISCORD_MESSAGE_LIMIT,
    MultiUserRecordingSink,
    RecordAudio,
)
from plutarch.commands.voice_connections import ChannelStateManager


class TestMultiUserRecordingSink:
    """tests for MultiUserRecordingSink class."""

    @pytest.fixture
    def temp_dir(self):
        """create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_member(self):
        """create a mock discord member."""
        member = MagicMock()
        member.id = 12345
        member.display_name = "TestUser"
        member.bot = False
        return member

    @pytest.fixture
    def mock_bot_member(self):
        """create a mock discord bot member."""
        member = MagicMock()
        member.id = 99999
        member.display_name = "BotUser"
        member.bot = True
        return member

    def test_creates_output_directory(self, temp_dir, mock_member):
        """should create output directory if it doesn't exist."""
        output_dir = temp_dir / "new_session"
        assert not output_dir.exists()

        with patch("plutarch.commands.record_audio.voice_recv"):
            sink = MultiUserRecordingSink(
                output_dir=output_dir,
                session_id="test",
                members=[mock_member],
            )
            # cleanup to close any file handles
            sink.cleanup()

        assert output_dir.exists()

    def test_skips_bot_members(self, temp_dir, mock_member, mock_bot_member):
        """should not create sinks for bot members."""
        with patch("plutarch.commands.record_audio.voice_recv") as mock_vr:
            mock_vr.WaveSink = MagicMock()
            sink = MultiUserRecordingSink(
                output_dir=temp_dir,
                session_id="test",
                members=[mock_member, mock_bot_member],
            )
            sink.cleanup()

        # should only have user + composite (2 calls), not bot
        expected_wav_sink_calls = 2
        assert mock_vr.WaveSink.call_count == expected_wav_sink_calls

    def test_file_paths_tracked(self, temp_dir, mock_member):
        """should track file paths for each user."""
        with patch("plutarch.commands.record_audio.voice_recv") as mock_vr:
            mock_vr.WaveSink = MagicMock()
            sink = MultiUserRecordingSink(
                output_dir=temp_dir,
                session_id="test",
                members=[mock_member],
            )
            sink.cleanup()

        assert mock_member.display_name in sink.file_paths
        assert "_composite" in sink.file_paths

    def test_composite_recording_optional(self, temp_dir, mock_member):
        """should skip composite when record_composite=False."""
        with patch("plutarch.commands.record_audio.voice_recv") as mock_vr:
            mock_vr.WaveSink = MagicMock()
            sink = MultiUserRecordingSink(
                output_dir=temp_dir,
                session_id="test",
                members=[mock_member],
                record_composite=False,
            )
            sink.cleanup()

        assert "_composite" not in sink.file_paths
        # only 1 call for user, not composite
        expected_wav_sink_calls = 1
        assert mock_vr.WaveSink.call_count == expected_wav_sink_calls

    def test_wants_opus_returns_false(self, temp_dir, mock_member):
        """should return False for wants_opus (we want PCM)."""
        with patch("plutarch.commands.record_audio.voice_recv"):
            sink = MultiUserRecordingSink(
                output_dir=temp_dir,
                session_id="test",
                members=[mock_member],
            )
            assert sink.wants_opus() is False
            sink.cleanup()

    def test_write_ignores_none_user(self, temp_dir, mock_member):
        """should ignore writes with None user."""
        with patch("plutarch.commands.record_audio.voice_recv") as mock_vr:
            mock_sink = MagicMock()
            mock_vr.WaveSink.return_value = mock_sink

            sink = MultiUserRecordingSink(
                output_dir=temp_dir,
                session_id="test",
                members=[mock_member],
            )

            mock_data = MagicMock()
            sink.write(None, mock_data)

            # should not write to any sink
            mock_sink.write.assert_not_called()
            sink.cleanup()

    def test_write_to_user_sink(self, temp_dir, mock_member):
        """should write to correct user's sink."""
        with patch("plutarch.commands.record_audio.voice_recv") as mock_vr:
            mock_sink = MagicMock()
            mock_vr.WaveSink.return_value = mock_sink

            sink = MultiUserRecordingSink(
                output_dir=temp_dir,
                session_id="test",
                members=[mock_member],
            )

            mock_data = MagicMock()
            sink.write(mock_member, mock_data)

            # should write to sink (once for user, once for composite)
            expected_write_calls = 2
            assert mock_sink.write.call_count == expected_write_calls
            sink.cleanup()

    def test_sanitizes_display_name(self, temp_dir):
        """should sanitize display names with special characters."""
        member = MagicMock()
        member.id = 12345
        member.display_name = "User@With#Special!Chars"
        member.bot = False

        with patch("plutarch.commands.record_audio.voice_recv") as mock_vr:
            mock_vr.WaveSink = MagicMock()
            sink = MultiUserRecordingSink(
                output_dir=temp_dir,
                session_id="test",
                members=[member],
            )
            sink.cleanup()

        # file path should have sanitized name
        file_path = sink.file_paths[member.display_name]
        assert "@" not in str(file_path)
        assert "#" not in str(file_path)
        assert "!" not in str(file_path)


class TestRecordAudio:
    """tests for RecordAudio cog."""

    @pytest.fixture
    def manager(self):
        """create a fresh state manager."""
        return ChannelStateManager()

    @pytest.fixture
    def mock_client(self):
        """create a mock discord client."""
        return MagicMock()

    @pytest.fixture
    def cog(self, mock_client, manager):
        """create the RecordAudio cog."""
        return RecordAudio(mock_client, manager)

    @pytest.fixture
    def mock_ctx(self):
        """create a mock command context."""
        ctx = MagicMock()
        ctx.send = AsyncMock()
        ctx.author = MagicMock()
        ctx.author.voice = MagicMock()
        ctx.author.voice.channel = MagicMock()
        ctx.author.voice.channel.id = 12345
        ctx.author.voice.channel.name = "test-channel"
        ctx.author.voice.channel.members = []
        return ctx

    async def test_record_requires_voice_channel(self, cog, mock_ctx):
        """should require user to be in voice channel."""
        mock_ctx.author.voice = None

        # call the callback directly, bypassing command wrapper
        await cog.record.callback(cog, mock_ctx)

        mock_ctx.send.assert_called_once()
        assert "voice channel" in mock_ctx.send.call_args[0][0]

    async def test_record_prevents_duplicate_recording(self, cog, mock_ctx):
        """should prevent starting recording twice in same channel."""
        channel = mock_ctx.author.voice.channel
        member = MagicMock()
        member.bot = False
        channel.members = [member]

        # simulate active recording
        cog._active_sinks[channel.id] = MagicMock()

        await cog.record.callback(cog, mock_ctx)

        assert "already recording" in mock_ctx.send.call_args[0][0]

    async def test_stop_recording_requires_active_session(self, cog, mock_ctx):
        """should require active recording to stop."""
        await cog.stop_recording.callback(cog, mock_ctx)

        mock_ctx.send.assert_called()
        assert "not currently recording" in mock_ctx.send.call_args[0][0]

    async def test_recording_status_when_not_recording(self, cog, mock_ctx):
        """should report not recording when no active session."""
        await cog.recording_status.callback(cog, mock_ctx)

        mock_ctx.send.assert_called_once()
        assert "not recording" in mock_ctx.send.call_args[0][0]

    async def test_recording_status_when_recording(self, cog, mock_ctx, temp_dir):
        """should report active users when recording."""
        channel_id = mock_ctx.author.voice.channel.id
        mock_sink = MagicMock()
        mock_sink.file_paths = {
            "User1": temp_dir / "user1.wav",
            "_composite": temp_dir / "c.wav",
        }
        cog._active_sinks[channel_id] = mock_sink

        await cog.recording_status.callback(cog, mock_ctx)

        mock_ctx.send.assert_called_once()
        assert "User1" in mock_ctx.send.call_args[0][0]

    @pytest.fixture
    def temp_dir(self):
        """create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)


class TestConstants:
    """tests for module constants."""

    def test_discord_message_limit(self):
        """should have reasonable message limit."""
        # discord limit is 2000, we use 1900 as buffer
        discord_actual_limit = 2000
        reasonable_lower_bound = 1800
        assert discord_actual_limit > DISCORD_MESSAGE_LIMIT
        assert reasonable_lower_bound < DISCORD_MESSAGE_LIMIT
