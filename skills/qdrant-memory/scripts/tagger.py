#!/usr/bin/env python3
"""Tagger (optional): generate lightweight tags + title for a conversation chunk.

Design goals:
- Cheap: run on a smaller model (e.g. Minimax 2.5 or any OpenAI-compatible endpoint).
- Portable: fully env-configured.
- Deterministic-ish: JSON output.

This is intentionally optional. The memory system works without it.

Env (OpenAI-compatible):
  TAGGER_BASE_URL   e.g. https://api.minimax.chat/v1
  TAGGER_API_KEY    token
  TAGGER_MODEL      default: minimax-2.5

Usage:
  python3 tagger.py --text "..." 

Output:
  {"title": "...", "tags": ["..."], "entities": ["..."], "category": "..."}
"""

import argparse
import json
import os
import sys
import urllib.request

BASE_URL = os.getenv("TAGGER_BASE_URL", "").rstrip("/")
API_KEY = os.getenv("TAGGER_API_KEY", "")
MODEL = os.getenv("TAGGER_MODEL", "minimax-2.5")
TIMEOUT = int(os.getenv("TAGGER_TIMEOUT", "30"))

SYSTEM = (
    "You generate compact metadata for retrieving old conversation context. "
    "Return STRICT JSON with keys: title (string), tags (array of short strings), "
    "entities (array of short strings), category (string). "
    "Tags should be lowercase, hyphenated, <= 4 words each. "
    "Prefer 5-12 tags."
)


def call_openai_compat(text: str) -> dict:
    if not BASE_URL or not API_KEY:
        raise RuntimeError("TAGGER_BASE_URL and TAGGER_API_KEY must be set")

    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": text[:12000]},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
    )

    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        resp = json.loads(r.read().decode("utf-8"))

    content = resp["choices"][0]["message"]["content"]
    return json.loads(content)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    args = ap.parse_args()

    try:
        out = call_openai_compat(args.text)
    except Exception as e:
        print(f"[tagger] error: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
