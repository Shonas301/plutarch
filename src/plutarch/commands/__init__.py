from .audio_player import AudioLinkPlayer
from .ready import ReadyConnection

cogs = [ReadyConnection, AudioLinkPlayer]


__all__ = ["cogs"]


def find_file_containing_string(directory: str, search_string: str) -> str | None:
    """Find a file in the given directory that contains the specified string.

    Args:
        directory (str): The directory to search in.
        search_string (str): The string to search for.

    Returns:
        str | None: The path of the first file containing the string, or None if not found.
    """
    import os

    for root, _, files in os.walk(directory):
        for file in files:
            with open(os.path.join(root, file)) as f:
                if search_string in f.read():
                    return os.path.join(root, file)
    return None


def find_file_containing_string_all_at_once(
    directory: str, search_string: str
) -> str | None:
    """Find a file in the given directory that contains the specified string.

    Args:
        directory (str): The directory to search in.
        search_string (str): The string to search for.

    Returns:
        str | None: The path of the first file containing the string, or None if not found.
    """
    import os

    for root, _, files in os.walk(directory):
        for file in files:
            with open(os.path.join(root, file)) as f:
                if search_string in f.read():
                    return os.path.join(root, file)
    return None
