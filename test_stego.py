"""
test_stego.py
Exercises the full encode -> decode cycle across several images and
messages, including password-protected and edge-case scenarios, and
verifies the encoded image is visually identical to the original.
"""

import os
import random

from PIL import Image
import numpy as np

from stego_core import encode_image, decode_image, max_capacity_bytes, StegoError

OUT_DIR = "test_output"

os.makedirs(OUT_DIR, exist_ok=True)


def make_test_image(path, size=(300, 200), seed=0):
    """Create a reproducible, colourful test PNG (no external image needed)."""
    rng = np.random.default_rng(seed)
    # Smooth gradient + noise so it looks like a "real" photo-ish image
    x = np.linspace(0, 255, size[0])
    
    y = np.linspace(0, 255, size[1])
    xv, yv = np.meshgrid(x, y)
    r = xv.astype(np.uint8)
    g = yv.astype(np.uint8)
    b = ((xv + yv) / 2).astype(np.uint8)
    noise = rng.integers(0, 15, size=(size[1], size[0], 3), dtype=np.uint8)
    arr = np.stack([r, g, b], axis=-1).astype(np.uint16)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    Image.fromarray(arr, "RGB").save(path)
    return path


def max_channel_diff(path_a, path_b):
    """Largest absolute per-channel pixel difference between two images."""
    a = np.array(Image.open(path_a).convert("RGB"), dtype=np.int16)
    b = np.array(Image.open(path_b).convert("RGB"), dtype=np.int16)
    return int(np.max(np.abs(a - b)))


def run_case(name, image_path, message, password=None):
    encoded_path = os.path.join(OUT_DIR, f"{name}_encoded.png")
    print(f"\n--- Case: {name} ---")
    print(f"Original message: {message!r}")
    if password:
        print(f"Password: {password!r}")

    stats = encode_image(image_path, encoded_path, message, password)
    print(f"Encoded -> {encoded_path} "
          f"({stats['message_bytes']}/{stats['capacity_bytes']} bytes used)")

    recovered = decode_image(encoded_path, password)
    assert recovered == message, f"MISMATCH: {recovered!r} != {message!r}"
    print("Decode matches original message. [PASS]")

    diff = max_channel_diff(image_path, encoded_path)
    print(f"Max per-channel pixel difference: {diff} / 255 "
          f"({'invisible to the eye' if diff <= 1 else 'CHECK'})")
    assert diff <= 1, "LSB encoding should never change a channel value by more than 1"

    return encoded_path


def run_wrong_password_case(image_path):
    print("\n--- Case: wrong password ---")
    encoded_path = os.path.join(OUT_DIR, "wrongpass_encoded.png")
    original = "Top secret rendezvous at dawn."
    encode_image(image_path, encoded_path, original, password="tr0ub4dor&3")
    try:
        recovered = decode_image(encoded_path, password="hunter2")
        assert recovered != original
        print(f"Wrong password did not crash, but produced garbage (as expected for XOR): {recovered!r}")
        print("[PASS] (Note: this is exactly why XOR is NOT real encryption -- see README.")
    except StegoError as e:
        print(f"Wrong password correctly raised a UTF-8 decode error: {e}")
        print("[PASS] (Whether you get garbage text or an error depends on byte luck --")
        print(" this inconsistency is itself evidence XOR is not a real security layer.)")


def run_capacity_overflow_case(image_path):
    print("\n--- Case: message too big for image should raise StegoError ---")
    image = Image.open(image_path)
    capacity = max_capacity_bytes(image.convert("RGB"))
    too_big_message = "A" * (capacity + 100)
    try:
        encode_image(image_path, os.path.join(OUT_DIR, "overflow.png"), too_big_message)
        print("[FAIL] Expected StegoError for oversized message")
    except StegoError as e:
        print(f"Correctly rejected oversized message: {e}")


def main():
    img1 = make_test_image(os.path.join(OUT_DIR, "sample1.png"), size=(300, 200), seed=1)
    img2 = make_test_image(os.path.join(OUT_DIR, "sample2.png"), size=(500, 350), seed=2)

    run_case("short_message", img1, "Hello, this is hidden!")
    run_case("long_message", img2,
              "This is a much longer secret message used to test that the LSB "
              "steganography encoder can handle multi-sentence payloads without "
              "corrupting the image or losing any bytes during extraction. " * 3)
    run_case("password_protected", img1, "Meet at the old bridge at midnight.", password="hunter2")
    run_case("unicode_message", img2, "Encrypted note: café, naïve, 日本語, emoji 🔒🕵️")
    run_case("empty_ish_message", img1, "hi")

    run_wrong_password_case(img2)
    run_capacity_overflow_case(img1)

    print("\nAll test cases completed.")


if __name__ == "__main__":
    main()
