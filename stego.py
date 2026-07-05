"""
stego.py -- CLI steganography tool (LSB encoding + optional XOR password)

Usage:
    python3 stego.py encode -i input.png -o output.png -m "secret message"
    python3 stego.py encode -i input.png -o output.png -m "secret message" -p mypassword
    python3 stego.py encode -i input.png -o output.png -f message.txt

    python3 stego.py decode -i output.png
    python3 stego.py decode -i output.png -p mypassword

    python3 stego.py capacity -i input.png
"""

import argparse
import getpass
import sys

from stego_core import encode_image, decode_image, max_capacity_bytes, StegoError
from PIL import Image


def cmd_encode(args):
    message = args.message
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            message = f.read()
    if message is None:
        message = input("Enter the secret message to hide: ")

    password = args.password
    if args.ask_password and not password:
        password = getpass.getpass("Password (used to XOR-protect the message): ")

    try:
        stats = encode_image(args.input, args.output, message, password)
    except (StegoError, FileNotFoundError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    print("[OK] Message hidden successfully.")
    print(f"     Input image : {args.input}")
    print(f"     Output image: {stats['output_path']}")
    print(f"     Image size  : {stats['image_size'][0]}x{stats['image_size'][1]}")
    print(f"     Message size: {stats['message_bytes']} bytes "
          f"(capacity: {stats['capacity_bytes']} bytes)")
    if password:
        print("     Password protection: ENABLED (XOR)")


def cmd_decode(args):
    password = args.password
    if args.ask_password and not password:
        password = getpass.getpass("Password: ")

    try:
        message = decode_image(args.input, password)
    except (StegoError, FileNotFoundError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    print("[OK] Hidden message recovered:")
    print("-" * 50)
    print(message)
    print("-" * 50)


def cmd_capacity(args):
    try:
        
        image = Image.open(args.input)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    capacity = max_capacity_bytes(image.convert("RGB"))
    print(f"Image: {args.input} ({image.size[0]}x{image.size[1]}, mode={image.mode})")
    print(f"Maximum message capacity: {capacity} bytes (~{capacity // 1024} KB)")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Hide and extract secret text messages inside PNG images using LSB steganography."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_enc = sub.add_parser("encode", help="Hide a message inside an image")
    p_enc.add_argument("-i", "--input", required=True, help="Path to the source PNG/JPG/etc image")
    p_enc.add_argument("-o", "--output", required=True, help="Path to save the resulting PNG image")
    group = p_enc.add_mutually_exclusive_group()
    group.add_argument("-m", "--message", help="Secret message text")
    group.add_argument("-f", "--file", help="Path to a text file containing the secret message")
    p_enc.add_argument("-p", "--password", help="Password to XOR-protect the message")
    p_enc.add_argument("--ask-password", action="store_true",
                        help="Prompt for a password interactively (hidden input)")
    p_enc.set_defaults(func=cmd_encode)

    p_dec = sub.add_parser("decode", help="Extract a hidden message from an image")
    p_dec.add_argument("-i", "--input", required=True, help="Path to the image containing a hidden message")
    p_dec.add_argument("-p", "--password", help="Password used to XOR-protect the message")
    p_dec.add_argument("--ask-password", action="store_true",
                        help="Prompt for a password interactively (hidden input)")
    p_dec.set_defaults(func=cmd_decode)

    p_cap = sub.add_parser("capacity", help="Show how many bytes an image can hide")
    p_cap.add_argument("-i", "--input", required=True, help="Path to the image")
    
    p_cap.set_defaults(func=cmd_capacity)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
