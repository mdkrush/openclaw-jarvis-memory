#!/usr/bin/env python3
"""
Cron Capture: Append NEW session transcript messages to Redis (no LLM / no heartbeat).

Goal: minimize token spend by capturing context out-of-band.

- Tracks per-session file offsets (byte position) in a JSON state file.
- No-ops if the transcript file hasn't changed since last run.
- Stores user/assistant visible text to Redis (chronological order via RPUSH).
- Optionally stores model "thinking" separately (disabled by default) so it can be
  queried only when explicitly needed.

Usage:
  python3 cron_capture.py [--user-id rob] [--include-thinking]

Suggested cron (every 5 minutes):
  */5 * * * * cd ~/.openclaw/workspace && python3 skills/mem-redis/scripts/cron_capture.py --user-id $USER

Env:
  OPENCLAW_WORKSPACE: override workspace path (default: ~/.openclaw/workspace)
  OPENCLAW_SESSIONS_DIR: override sessions dir (default: ~/.openclaw/agents/main/sessions)
  REDIS_HOST / REDIS_PORT / USER_ID
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import redis

REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
USER_ID = os.getenv("USER_ID", "rob")

DEFAULT_WORKSPACE = Path(os.getenv("OPENCLAW_WORKSPACE", str(Path.home() / ".openclaw" / "workspace")))
DEFAULT_SESSIONS_DIR = Path(os.getenv("OPENCLAW_SESSIONS_DIR", str(Path.home() / ".openclaw" / "agents" / "main" / "sessions")))

STATE_FILE = DEFAULT_WORKSPACE / ".mem_capture_state.json"


@dataclass
class ParsedMessage:
    role: str  # user|assistant
    text: str
    thinking: Optional[str]
    timestamp: str
    session_id: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_latest_transcript(sessions_dir: Path) -> Optional[Path]:
    files = list(sessions_dir.glob("*.jsonl"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def load_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def save_state(state: Dict[str, Any]) -> None:
    try:
        STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True))
    except Exception as e:
        print(f"[cron_capture] Warning: could not write state: {e}", file=sys.stderr)


def extract_text_and_thinking(content: Any) -> Tuple[str, Optional[str]]:
    """Extract visible text and optional thinking from OpenClaw message content."""
    if isinstance(content, str):
        return content, None

    text_parts: List[str] = []
    thinking_parts: List[str] = []

    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            if "text" in item and isinstance(item["text"], str):
                text_parts.append(item["text"])
            if "thinking" in item and isinstance(item["thinking"], str):
                thinking_parts.append(item["thinking"])

    text = "".join(text_parts).strip()
    thinking = "\n".join(thinking_parts).strip() if thinking_parts else None
    return text, thinking


def parse_new_messages(transcript_path: Path, start_offset: int, include_thinking: bool) -> Tuple[List[ParsedMessage], int]:
    """Parse messages from transcript_path starting at byte offset."""
    session_id = transcript_path.stem
    msgs: List[ParsedMessage] = []

    with transcript_path.open("rb") as f:
        f.seek(start_offset)
        while True:
            line = f.readline()
            if not line:
                break
            try:
                entry = json.loads(line.decode("utf-8", errors="replace").strip())
            except Exception:
                continue

            if entry.get("type") != "message" or "message" not in entry:
                continue
            msg = entry.get("message") or {}
            role = msg.get("role")
            if role not in ("user", "assistant"):
                continue

            # Skip tool results explicitly
            if role == "toolResult":
                continue

            text, thinking = extract_text_and_thinking(msg.get("content"))
            if not text and not (include_thinking and thinking):
                continue

            msgs.append(
                ParsedMessage(
                    role=role,
                    text=text[:8000],
                    thinking=(thinking[:16000] if (include_thinking and thinking) else None),
                    timestamp=entry.get("timestamp") or _now_iso(),
                    session_id=session_id,
                )
            )

        end_offset = f.tell()

    return msgs, end_offset


def append_to_redis(user_id: str, messages: List[ParsedMessage]) -> int:
    if not messages:
        return 0

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    key = f"mem:{user_id}"
    thinking_key = f"mem_thinking:{user_id}"

    # RPUSH keeps chronological order.
    for m in messages:
        payload: Dict[str, Any] = {
            "role": m.role,
            "content": m.text,
            "timestamp": m.timestamp,
            "user_id": user_id,
            "session": m.session_id,
        }
        r.rpush(key, json.dumps(payload))

        if m.thinking:
            t_payload = {
                "role": m.role,
                "thinking": m.thinking,
                "timestamp": m.timestamp,
                "user_id": user_id,
                "session": m.session_id,
            }
            r.rpush(thinking_key, json.dumps(t_payload))

    return len(messages)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cron capture: append new transcript messages to Redis")
    parser.add_argument("--user-id", default=USER_ID)
    parser.add_argument("--include-thinking", action="store_true", help="Store thinking into mem_thinking:<user>")
    parser.add_argument("--sessions-dir", default=str(DEFAULT_SESSIONS_DIR))
    args = parser.parse_args()

    sessions_dir = Path(args.sessions_dir)
    transcript = find_latest_transcript(sessions_dir)
    if not transcript:
        print("[cron_capture] No session transcripts found")
        return

    st = load_state()
    key = str(transcript)
    info = st.get(key, {})
    last_offset = int(info.get("offset", 0))
    last_size = int(info.get("size", 0))

    cur_size = transcript.stat().st_size
    if cur_size == last_size and last_offset > 0:
        print("[cron_capture] No changes")
        return

    messages, end_offset = parse_new_messages(transcript, last_offset, include_thinking=args.include_thinking)
    if not messages:
        # Still update size/offset so we don't re-read noise lines.
        st[key] = {"offset": end_offset, "size": cur_size, "updated_at": _now_iso()}
        save_state(st)
        print("[cron_capture] No new user/assistant messages")
        return

    count = append_to_redis(args.user_id, messages)

    st[key] = {"offset": end_offset, "size": cur_size, "updated_at": _now_iso()}
    save_state(st)

    print(f"[cron_capture] Appended {count} messages to Redis mem:{args.user_id}")


if __name__ == "__main__":
    main()
