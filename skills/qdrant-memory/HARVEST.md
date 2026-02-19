# Session Harvest Instructions

## What is Session Harvesting?

Session harvesting extracts conversation turns from OpenClaw session JSONL files and stores them to Qdrant long-term memory with proper embeddings and user_id linking.

## When to Use

- **After setting up a new memory system** — harvest existing sessions
- **After discovering missed backups** — recover data from session files
- **Periodically** — if cron jobs missed any data

## Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `harvest_sessions.py` | Harvest all sessions (auto-sorts by mtime) | Limited by memory, may timeout |
| `harvest_newest.py` | Harvest specific sessions by name | Recommended for batch control |

## Location

```
/root/.openclaw/workspace/skills/qdrant-memory/scripts/
├── harvest_sessions.py   # Auto-harvest (use --limit to control)
└── harvest_newest.py     # Manual batch (specify session names)
```

## Usage

### Method 1: Auto-Harvest with Limit

```bash
# Harvest oldest 10 sessions (default sort)
python3 harvest_sessions.py --user-id rob --limit 10

# Dry run to see what would be stored
python3 harvest_sessions.py --user-id rob --dry-run --limit 5
```

### Method 2: Batch by Session Name (Recommended)

```bash
# Harvest specific sessions (newest first recommended)
python3 harvest_newest.py --user-id rob \
  session-uuid-1.jsonl \
  session-uuid-2.jsonl \
  session-uuid-3.jsonl
```

### Finding Newest Sessions

```bash
# List 20 newest session files
ls -t /root/.openclaw/agents/main/sessions/*.jsonl | head -20

# Get just filenames for copy-paste
ls -t /root/.openclaw/agents/main/sessions/*.jsonl | head -20 | xargs -I{} basename {}
```

## How It Works

1. **Parse** — Reads JSONL session file, extracts user/AI turns
2. **Pair** — Matches user message with next AI response
3. **Embed** — Generates 3 embeddings (user, AI, summary) via Ollama
4. **Deduplicate** — Checks content_hash before storing
5. **Store** — Upserts to Qdrant with user_id, conversation_id, turn_number

## Deduplication

- Uses MD5 hash of `user_message::ai_response`
- Checks Qdrant for existing `user_id + content_hash`
- Skips if already stored (returns "duplicate")
- Safe to run multiple times on same sessions

## Output Format

```
[1] session-uuid.jsonl
  Stored: 10, Skipped: 6

Total: 44 stored, 6 skipped
```

- **Stored** = New memories added to Qdrant
- **Skipped** = Duplicates (already in Qdrant)

## Troubleshooting

### Timeout / SIGKILL

The embedding process is CPU-intensive. If killed:

```bash
# Use smaller batches
python3 harvest_newest.py --user-id rob session1.jsonl session2.jsonl
```

### Check Qdrant Status

```bash
curl -s http://10.0.0.40:6333/collections/kimi_memories | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result']['points_count'])"
```

### Check Session Content

```bash
# Count turns in a session
python3 -c "
import json
from pathlib import Path
f = Path('/root/.openclaw/agents/main/sessions/YOUR-SESSION.jsonl')
count = sum(1 for line in open(f) if 'user' in line or 'assistant' in line)
print(f'~{count} messages')
"
```

## Memory Architecture

```
Session JSONL (raw)
       │
       ▼
  harvest_*.py
       │
       ├──► Embeddings (Ollama snowflake-arctic-embed2)
       │
       ▼
  Qdrant kimi_memories
       │
       └──► Searchable via user_id: "rob"
```

---

**Created:** February 17, 2026  
**Author:** Kimi (audit session)
