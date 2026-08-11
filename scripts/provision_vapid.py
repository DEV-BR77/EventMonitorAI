"""Provision persistent Web Push VAPID keys in the local Docker environment."""

import base64
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env.docker"


def encoded(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def set_value(lines: list[str], name: str, value: str) -> list[str]:
    replacement = f"{name}={value}"
    for index, line in enumerate(lines):
        if line.startswith(f"{name}="):
            lines[index] = replacement
            return lines
    lines.append(replacement)
    return lines


def main() -> None:
    if not ENV_FILE.exists():
        raise SystemExit(".env.docker fehlt")
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    values = {line.partition("=")[0]: line.partition("=")[2] for line in lines if "=" in line}
    if values.get("VAPID_PRIVATE_KEY") and values.get("VAPID_PUBLIC_KEY"):
        print("VAPID-Schlüssel sind bereits provisioniert.")
        return

    private_key = ec.generate_private_key(ec.SECP256R1())
    private_value = private_key.private_numbers().private_value.to_bytes(32, "big")
    public_value = private_key.public_key().public_bytes(
        Encoding.X962,
        PublicFormat.UncompressedPoint,
    )
    lines = set_value(lines, "VAPID_PRIVATE_KEY", encoded(private_value))
    lines = set_value(lines, "VAPID_PUBLIC_KEY", encoded(public_value))
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Persistentes VAPID-Schlüsselpaar in .env.docker provisioniert.")


if __name__ == "__main__":
    main()
