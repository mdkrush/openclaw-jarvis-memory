# Qdrant Memory Skill

Vector database storage for long-term semantic memory.

## What It Does

Stores conversations with embeddings for semantic search.

## Commands

```bash
# Initialize collections
python3 scripts/init_kimi_memories.py
python3 scripts/init_kimi_kb.py

# Store immediately
python3 scripts/auto_store.py

# Search memories
python3 scripts/search_memories.py "your query"

# Harvest old sessions
python3 scripts/harvest_sessions.py --limit 10
```

## Heartbeat Integration

Add to HEARTBEAT.md:
```bash
python3 /path/to/skills/qdrant-memory/scripts/daily_conversation_backup.py
```

## Cron

```bash
# Daily backup at 3:30 AM
30 3 * * * scripts/sliding_backup.sh
```

## Collections

- `kimi_memories` - Conversations
- `kimi_kb` - Knowledge base
- `private_court_docs` - Legal docs

## Files

- `auto_store.py` - Store with embeddings
- `search_memories.py` - Semantic search
- `init_*.py` - Collection initialization
- `harvest_*.py` - Session harvesting
- `daily_conversation_backup.py` - Daily cron
- `sliding_backup.sh` - File backup
