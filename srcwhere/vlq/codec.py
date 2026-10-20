ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def encode_number(value: int) -> str:
    """Encode a signed integer as a base64 VLQ stream."""
    encoded = ((-value << 1) | 1) if value < 0 else value << 1
    groups: list[str] = []

    while encoded >= 32:
        groups.append(ALPHABET[(encoded & 31) | 32])
        encoded >>= 5

    groups.append(ALPHABET[encoded])
    return "".join(groups)
