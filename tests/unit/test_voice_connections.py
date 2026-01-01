"""tests for voice_connections module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from plutarch.commands.voice_connections import (
    ChannelState,
    ChannelStateManager,
    PlayerChannelState,
    RecorderChannelState,
    get_channels,
)


class TestPlayerChannelState:
    """tests for PlayerChannelState dataclass."""

    def test_default_values(self):
        """should initialize with empty queue and defaults."""
        state = PlayerChannelState()
        assert state.queue == []
        assert state.playing == ""
        assert state.remain_connected is False

    def test_queue_operations(self):
        """should support standard list operations on queue."""
        state = PlayerChannelState()
        state.queue.append("song1")
        state.queue.append("song2")
        expected_length_after_append = 2
        assert len(state.queue) == expected_length_after_append
        assert state.queue.pop(0) == "song1"
        expected_length_after_pop = 1
        assert len(state.queue) == expected_length_after_pop

    def test_custom_initialization(self):
        """should accept custom values."""
        state = PlayerChannelState(
            queue=["a", "b"],
            playing="current",
            remain_connected=True,
        )
        assert state.queue == ["a", "b"]
        assert state.playing == "current"
        assert state.remain_connected is True


class TestRecorderChannelState:
    """tests for RecorderChannelState dataclass."""

    def test_default_values(self):
        """should initialize with empty dict."""
        state = RecorderChannelState()
        assert state.file_names == {}

    def test_file_names_operations(self):
        """should support dict operations on file_names."""
        state = RecorderChannelState()
        state.file_names["user1"] = "/path/to/file1.wav"
        state.file_names["user2"] = "/path/to/file2.wav"
        expected_user_count = 2
        assert len(state.file_names) == expected_user_count
        assert state.file_names["user1"] == "/path/to/file1.wav"


class TestChannelState:
    """tests for ChannelState dataclass."""

    def test_default_values(self):
        """should initialize with channel and defaults."""
        mock_channel = MagicMock()
        state = ChannelState(channel=mock_channel)
        assert state.channel is mock_channel
        assert state.client is None
        assert state.player is None
        assert state.recorder is None

    def test_with_player_state(self):
        """should accept player state."""
        mock_channel = MagicMock()
        player = PlayerChannelState(playing="test.mp3")
        state = ChannelState(channel=mock_channel, player=player)
        assert state.player.playing == "test.mp3"

    @pytest.mark.asyncio
    async def test_connect_creates_client(self):
        """should create voice client on connect."""
        mock_channel = MagicMock()
        mock_client = AsyncMock()
        mock_channel.connect = AsyncMock(return_value=mock_client)

        state = ChannelState(channel=mock_channel)

        with patch("plutarch.commands.voice_connections.voice_recv") as mock_voice_recv:
            mock_voice_recv.VoiceRecvClient = MagicMock()
            result = await state.connect()

        assert result is mock_client
        assert state.client is mock_client

    @pytest.mark.asyncio
    async def test_connect_returns_existing_client(self):
        """should return existing client if already connected."""
        mock_channel = MagicMock()
        mock_client = MagicMock()

        state = ChannelState(channel=mock_channel, client=mock_client)
        result = await state.connect()

        assert result is mock_client
        mock_channel.connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_connect_returns_none_if_no_channel(self):
        """should return None if channel is falsy."""
        state = ChannelState(channel=None)
        result = await state.connect()
        assert result is None


class TestGetChannels:
    """tests for get_channels function."""

    def test_returns_dict(self):
        """should return the global CHANNELS dict."""
        channels = get_channels()
        assert isinstance(channels, dict)

    def test_returns_same_instance(self):
        """should return the same dict instance each time."""
        channels1 = get_channels()
        channels2 = get_channels()
        assert channels1 is channels2

    def test_mutations_persist(self):
        """mutations should persist across calls."""
        channels = get_channels()
        test_key = "__test_key__"
        try:
            channels[test_key] = "test_value"
            assert get_channels()[test_key] == "test_value"
        finally:
            # cleanup
            channels.pop(test_key, None)


class TestChannelStateManager:
    """tests for ChannelStateManager class."""

    @pytest.fixture
    def manager(self):
        """create a fresh manager for each test."""
        return ChannelStateManager()

    @pytest.fixture
    def mock_channel(self):
        """create a mock voice channel."""
        channel = MagicMock()
        channel.id = 12345
        return channel

    async def test_get_returns_none_for_unknown_channel(self, manager):
        """should return None for unknown channel ID."""
        result = await manager.get(99999)
        assert result is None

    async def test_get_or_create_creates_new_state(self, manager, mock_channel):
        """should create new state if channel doesn't exist."""
        state = await manager.get_or_create(mock_channel.id, mock_channel)
        assert state is not None
        assert state.channel is mock_channel
        assert state.client is None
        assert state.player is None

    async def test_get_or_create_returns_existing_state(self, manager, mock_channel):
        """should return existing state if channel exists."""
        state1 = await manager.get_or_create(mock_channel.id, mock_channel)
        state1.player = PlayerChannelState(playing="test.mp3")

        state2 = await manager.get_or_create(mock_channel.id, mock_channel)
        assert state1 is state2
        assert state2.player.playing == "test.mp3"

    async def test_get_returns_created_state(self, manager, mock_channel):
        """should return state after creation."""
        await manager.get_or_create(mock_channel.id, mock_channel)
        state = await manager.get(mock_channel.id)
        assert state is not None
        assert state.channel is mock_channel

    async def test_remove_returns_state(self, manager, mock_channel):
        """should remove and return state."""
        await manager.get_or_create(mock_channel.id, mock_channel)
        state = await manager.remove(mock_channel.id)
        assert state is not None
        assert state.channel is mock_channel

    async def test_remove_returns_none_for_unknown(self, manager):
        """should return None when removing unknown channel."""
        result = await manager.remove(99999)
        assert result is None

    async def test_remove_actually_removes(self, manager, mock_channel):
        """should actually remove state from manager."""
        await manager.get_or_create(mock_channel.id, mock_channel)
        await manager.remove(mock_channel.id)
        result = await manager.get(mock_channel.id)
        assert result is None

    async def test_set_overwrites_existing(self, manager, mock_channel):
        """should overwrite existing state with set."""
        await manager.get_or_create(mock_channel.id, mock_channel)
        new_state = ChannelState(channel=mock_channel)
        new_state.player = PlayerChannelState(playing="new.mp3")
        await manager.set(mock_channel.id, new_state)

        result = await manager.get(mock_channel.id)
        assert result.player.playing == "new.mp3"

    async def test_contains_returns_false_for_unknown(self, manager):
        """should return False for unknown channel."""
        result = await manager.contains(99999)
        assert result is False

    async def test_contains_returns_true_for_known(self, manager, mock_channel):
        """should return True for known channel."""
        await manager.get_or_create(mock_channel.id, mock_channel)
        result = await manager.contains(mock_channel.id)
        assert result is True

    async def test_all_channel_ids_empty(self, manager):
        """should return empty list when no channels."""
        result = await manager.all_channel_ids()
        assert result == []

    async def test_all_channel_ids_returns_all(self, manager):
        """should return all channel IDs."""
        channel1 = MagicMock()
        channel1.id = 111
        channel2 = MagicMock()
        channel2.id = 222

        await manager.get_or_create(channel1.id, channel1)
        await manager.get_or_create(channel2.id, channel2)

        result = await manager.all_channel_ids()
        assert sorted(result) == [111, 222]
