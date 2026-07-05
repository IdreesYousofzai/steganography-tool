"""
stego_core.py
Core LSB steganography engine with optional XOR password protection.

LSB (Least Significant Bit) steganography works by replacing the lowest
bit of each colour channel value (R, G, B) in an image with one bit of
the secret message. Because the lowest bit only ever changes a pixel's
colour value by at most 1 out of 255, the change is invisible to the
human eye but fully recoverable by a program that knows where to look.

Message layout embedded in the image (all lengths in BITS unless noted):
    [ 32 bits : message length in BYTES, big-endian unsigned int ]
    [ N bytes : message bytes (XOR-"encrypted" with password if given) ]

The 32-bit length header lets the decoder know exactly how many bits to
read back out, so we don't need any special end-of-message marker.
"""

from PIL import Image


class StegoError(Exception):
    """Raised for any steganography-specific failure (capacity, format, etc.)."""
    pass


# --------------------------------------------------------------------------
# XOR "encryption"
# --------------------------------------------------------------------------
# NOTE ON SECURITY: XOR with a repeating key is NOT strong encryption.
# It is trivially breakable with frequency analysis if an attacker has
# enough ciphertext, and provides no integrity protection at all.
# It is used here purely as an educational demonstration of adding a
# second layer ("you need the password to make sense of what you find")
# on top of the steganography layer. For real confidentiality, the
# message should be encrypted with a proper cipher (e.g. AES-GCM via
# the `cryptography` library) *before* being handed to this tool.

def xor_bytes(data: bytes, password: str) -> bytes:
    """XOR `data` against a repeating key derived from `password`."""
    if not password:
        return data
    key = password.encode("utf-8")
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


# --------------------------------------------------------------------------
# Bit <-> byte helpers
# --------------------------------------------------------------------------

def _bytes_to_bits(data: bytes):
    for byte in data:
        for shift in range(7, -1, -1):
            yield (byte >> shift) & 1


def _bits_to_bytes(bits) -> bytes:
    bits = list(bits)
    out = bytearray()
    for i in range(0, len(bits) - 7, 8):
        byte = 0
        for b in bits[i:i + 8]:
            byte = (byte << 1) | b
        out.append(byte)
    return bytes(out)


def _int_to_bits(value: int, n_bits: int):
    return [(value >> shift) & 1 for shift in range(n_bits - 1, -1, -1)]


# --------------------------------------------------------------------------
# Capacity
# --------------------------------------------------------------------------
def max_capacity_bytes(image: Image.Image) -> int:
    """How many message bytes can fit in this image (1 bit per colour channel)."""
    width, height = image.size
    channels = len(image.getbands())
    total_bits = width * height * channels
    usable_bits = total_bits - 32  # reserve the length header
    return max(usable_bits // 8, 0)


# --------------------------------------------------------------------------
# Encoding
# --------------------------------------------------------------------------
def encode_image(input_path: str, output_path: str, message: str, password: str = None) -> dict:
    """
    Hide `message` inside the image at `input_path`, saving the result to
    `output_path`. Returns a small dict of stats for reporting purposes.
    """
    image = Image.open(input_path)
    image = image.convert("RGB")  # normalise to a predictable 3-channel format

    payload = message.encode("utf-8")
    if password:
        payload = xor_bytes(payload, password)

    capacity = max_capacity_bytes(image)
    if len(payload) > capacity:
        raise StegoError(
            f"Message too large: needs {len(payload)} bytes but image can only "
            f"hold {capacity} bytes. Use a bigger image or a shorter message."
        )

    header_bits = _int_to_bits(len(payload), 32)
    message_bits = list(_bytes_to_bits(payload))
    all_bits = header_bits + message_bits

    pixels = list(image.getdata())
    flat_values = [channel for pixel in pixels for channel in pixel]

    for i, bit in enumerate(all_bits):
        flat_values[i] = (flat_values[i] & ~1) | bit  # clear LSB, then set it

    new_pixels = [
        tuple(flat_values[i:i + 3]) for i in range(0, len(flat_values), 3)
    ]
    image.putdata(new_pixels)
    image.save(output_path, "PNG")  # PNG is lossless -- required for LSB to survive

    return {
        "message_bytes": len(payload),
        "capacity_bytes": capacity,
        "image_size": image.size,
        "output_path": output_path,
    }


# --------------------------------------------------------------------------
# Decoding
# --------------------------------------------------------------------------
def decode_image(input_path: str, password: str = None) -> str:
    """Extract and return the hidden text message from `input_path`."""
    image = Image.open(input_path)
    image = image.convert("RGB")

    pixels = list(image.getdata())
    flat_values = [channel for pixel in pixels for channel in pixel]

    if len(flat_values) < 32:
        raise StegoError("Image is too small to contain a valid message header.")

    header_bits = [v & 1 for v in flat_values[:32]]
    length_bytes = 0
    for bit in header_bits:
        length_bytes = (length_bytes << 1) | bit

    total_bits_needed = 32 + length_bytes * 8
    if total_bits_needed > len(flat_values):
        raise StegoError(
            "Decoded length header is invalid for this image. "
            "This usually means the image has no hidden message, or the "
            "wrong file was supplied."
        )

    message_bits = [v & 1 for v in flat_values[32:total_bits_needed]]
    payload = _bits_to_bytes(message_bits)

    if password:
        payload = xor_bytes(payload, password)

    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        raise StegoError(
            "Could not decode a valid UTF-8 message. "
            "This usually means the password is wrong."
        )
