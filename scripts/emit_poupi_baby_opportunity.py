"""Emit one real Poupi Baby runtime opportunity into Business OS evidence."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.business_os.poupi_baby_bridge import emit_poupi_baby_runtime_opportunity


def _read_payload(path: str) -> dict:
    text = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise SystemExit("payload must be a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("payload", help="JSON file path, or '-' for stdin")
    parser.add_argument("--observed-at")
    args = parser.parse_args()
    record = emit_poupi_baby_runtime_opportunity(
        _read_payload(args.payload),
        observed_at=args.observed_at,
    )
    print(json.dumps(record, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
