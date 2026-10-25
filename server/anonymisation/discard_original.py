"""Best-effort application buffer cleanup, not guaranteed secure memory erasure."""


def discard_original(buffer: bytearray) -> None:
    """Overwrite the owned request buffer before releasing it.

    Python and third-party libraries may have made other immutable copies.
    This does not guarantee full memory sanitisation.
    """
    for index in range(len(buffer)):
        buffer[index] = 0
    buffer.clear()
