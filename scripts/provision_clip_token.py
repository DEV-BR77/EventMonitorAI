from __future__ import annotations

import argparse
import hashlib
import re
import secrets
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRETS_HEADER = ROOT / "firmware" / "eventmonitor-esp32s3-udp" / "include" / "secrets.h"
DEFINE_PATTERN = re.compile(r'^#define CLIP_UPLOAD_TOKEN "([^"]+)"$', re.MULTILINE)


def ensure_local_token() -> str:
    content = SECRETS_HEADER.read_text(encoding="utf-8")
    existing = DEFINE_PATTERN.search(content)
    if existing:
        return existing.group(1)
    token = secrets.token_urlsafe(36)
    if not content.endswith("\n"):
        content += "\n"
    content += f'#define CLIP_UPLOAD_TOKEN "{token}"\n'
    SECRETS_HEADER.write_text(content, encoding="utf-8")
    return token


def provision_remote(target: str, token: str) -> None:
    remote_script = f"""
import os, pathlib, sys
path = pathlib.Path('/home/admin/yamnet/eventmonitor.env')
token = {token!r}
lines = path.read_text().splitlines() if path.exists() else []
lines = [line for line in lines if not line.startswith('EVENTMONITOR_CLIP_TOKEN=')]
lines.append('EVENTMONITOR_CLIP_TOKEN=' + token)
path.write_text('\\n'.join(lines) + '\\n')
os.chmod(path, 0o600)
"""
    subprocess.run(
        ["ssh", target, "python3 -"],
        input=remote_script,
        text=True,
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ssh-target", help="Optional target such as admin@192.168.178.64")
    args = parser.parse_args()
    token = ensure_local_token()
    if args.ssh_target:
        provision_remote(args.ssh_target, token)
    fingerprint = hashlib.sha256(token.encode()).hexdigest()[:12]
    print(f"Clip token provisioned (SHA-256 prefix: {fingerprint}).")


if __name__ == "__main__":
    main()
