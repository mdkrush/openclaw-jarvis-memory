# OpenClaw Jarvis-Like Memory System

> **Build an AI assistant that actually remembers you.**

This is a complete blueprint for implementing a production-grade, multi-layer memory system for OpenClaw that provides persistent, searchable, cross-session context — just like Jarvis from Iron Man.

[![YouTube Tutorial](https://img.shields.io/badge/YouTube-Tutorial-red)](https://youtube.com)
[![License](https://img.shields.io/badge/License-MIT-blue)]()

## 🎯 What This Builds

A three-layer memory architecture:

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1: Redis Buffer (Fast Short-Term)                   │
│  • Real-time accumulation                                  │
│  • Multi-session persistence                               │
│  • Daily flush to Qdrant                                   │
├─────────────────────────────────────────────────────────────┤
│  LAYER 2: Daily File Logs (.md)                           │
│  • Human-readable audit trail                              │
│  • Git-tracked, never lost                                 │
│  • Always accessible                                       │
├─────────────────────────────────────────────────────────────┤
│  LAYER 3: Qdrant Vector DB (Semantic Long-Term)           │
│  • 1024-dim embeddings (snowflake-arctic-embed2)         │
│  • Semantic search across ALL conversations                │
│  • User-centric (Mem0-style architecture)                  │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

```bash
# 1. Clone/copy this blueprint to your workspace
cp -r blueprint/* ~/.openclaw/workspace/

# 2. Run the installer
cd ~/.openclaw/workspace
chmod +x install.sh
./install.sh

# 3. Source the environment
source .memory_env

# 4. Test it
python3 skills/mem-redis/scripts/save_mem.py --user-id yourname
```

## 📋 Prerequisites

### Required Infrastructure

| Service | Purpose | Install |
|---------|---------|---------|
| **Qdrant** | Vector database | `docker run -p 6333:6333 qdrant/qdrant` |
| **Redis** | Fast buffer | `docker run -p 6379:6379 redis` |
| **Ollama** | Embeddings | [ollama.ai](https://ollama.ai) + `ollama pull snowflake-arctic-embed2` |

### Software Requirements

- Python 3.8+
- OpenClaw (obviously)
- `pip3 install redis qdrant-client requests`

## 🏗️ Architecture

### Memory Commands

```
User: "save mem"     → Redis + File (all turns)
User: "save q"       → Qdrant (semantic, embeddings)
User: "q <topic>"    → Semantic search
User: "remember this" → Quick note to file
```

### Data Flow

```
Every Message
     ↓
Redis Buffer (fast)
     ↓
File Log (permanent)
     ↓
[Optional: "save q"] → Qdrant (semantic)

Daily 3:00 AM
     ↓
Redis Buffer → Flush → Qdrant
     ↓
Clear Redis

Daily 3:30 AM
     ↓
Daily Files → Backup → Archive
```

## 📁 Project Structure

```
blueprint/
├── install.sh              # One-command installer
├── README.md               # This file
├── docker-compose.yml      # Spin up all infrastructure
├── requirements.txt        # Python dependencies
├── skills/
│   ├── mem-redis/          # Redis buffer skill
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       ├── hb_append.py
│   │       ├── save_mem.py
│   │       ├── cron_backup.py
│   │       ├── mem_retrieve.py
│   │       └── search_mem.py
│   └── qdrant-memory/      # Qdrant storage skill
│       ├── SKILL.md
│       ├── HARVEST.md
│       └── scripts/
│           ├── auto_store.py
│           ├── q_save.py
│           ├── search_memories.py
│           ├── daily_conversation_backup.py
│           ├── harvest_sessions.py
│           ├── init_*.py
│           └── sliding_backup.sh
├── config/
│   └── HEARTBEAT.md.template
└── docs/
    └── MEM_DIAGRAM.md      # Complete architecture docs
```

## 🔧 Manual Setup (Without install.sh)

### Step 1: Create Directory Structure

```bash
mkdir -p ~/.openclaw/workspace/{skills/{mem-redis,qdrant-memory}/scripts,memory}
```

### Step 2: Copy Scripts

See `skills/` directory in this blueprint.

### Step 3: Configure Environment

Create `~/.openclaw/workspace/.memory_env`:

```bash
export USER_ID="yourname"
export REDIS_HOST="10.0.0.36"
export REDIS_PORT="6379"
export QDRANT_URL="http://10.0.0.40:6333"
export OLLAMA_URL="http://10.0.0.10:11434"
```

### Step 4: Initialize Qdrant Collections

```bash
cd ~/.openclaw/workspace/skills/qdrant-memory/scripts
python3 init_kimi_memories.py
python3 init_kimi_kb.py
python3 init_private_court_docs.py
```

### Step 5: Set Up Cron

```bash
# 3:00 AM - Redis to Qdrant flush
0 3 * * * cd ~/.openclaw/workspace && python3 skills/mem-redis/scripts/cron_backup.py

# 3:30 AM - File backup
30 3 * * * ~/.openclaw/workspace/skills/qdrant-memory/scripts/sliding_backup.sh
```

### Step 6: Configure Heartbeat

Add to `HEARTBEAT.md`:

```markdown
## Memory Buffer (Every Heartbeat)

```bash
python3 /root/.openclaw/workspace/skills/mem-redis/scripts/save_mem.py --user-id yourname
```
```

## 🎥 YouTube Video Outline

If you're making a video about this:

1. **Introduction** (0-2 min)
   - The problem: AI that forgets everything
   - The solution: Multi-layer memory

2. **Demo** (2-5 min)
   - "What did we talk about yesterday?"
   - Semantic search in action

3. **Architecture** (5-10 min)
   - Show the three layers
   - Why each layer exists

4. **Live Build** (10-25 min)
   - Set up Qdrant + Redis
   - Install the scripts
   - Test the commands

5. **Advanced Features** (25-30 min)
   - Session harvesting
   - Email integration
   - Task queue

6. **Wrap-up** (30-32 min)
   - Recap
   - GitHub link
   - Call to action

## 🔍 How It Works

### Deduplication

Each memory generates a SHA-256 content hash. Before storing to Qdrant, the system checks if this user already has this exact content — preventing duplicates while allowing the same content for different users.

### Embeddings

Every turn generates **3 embeddings**:
1. User message embedding
2. AI response embedding  
3. Combined summary embedding

This enables searching by user query, AI response, or overall concept.

### Threading

Memories are tagged with:
- `user_id`: Persistent identity
- `conversation_id`: Groups related turns
- `session_id`: Which chat instance
- `turn_number`: Sequential ordering

## 🛠️ Customization

### Change Embedding Model

Edit `skills/qdrant-memory/scripts/auto_store.py`:

```python
# Change this line
EMBEDDING_MODEL = "snowflake-arctic-embed2"  # or your preferred model
```

### Add New Collections

Copy `init_kimi_memories.py` and modify:

```python
COLLECTION_NAME = "my_custom_collection"
```

### Adjust Cron Schedule

Edit your crontab:

```bash
# Every 6 hours instead of daily
0 */6 * * * python3 skills/mem-redis/scripts/cron_backup.py
```

## 📊 Monitoring

### Check System Status

```bash
# Redis buffer size
redis-cli -h 10.0.0.36 LLEN mem:yourname

# Qdrant collection size
curl -s http://10.0.0.40:6333/collections/kimi_memories | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['points_count'])"

# Recent memories
python3 skills/mem-redis/scripts/mem_retrieve.py --limit 10
```

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| "Redis connection failed" | Check Redis is running: `redis-cli ping` |
| "Qdrant connection failed" | Check Qdrant: `curl http://10.0.0.40:6333/collections` |
| "Embedding failed" | Ensure Ollama has snowflake-arctic-embed2 loaded |
| "No memories found" | Run `save q` first, or check collection exists |
| Cron not running | Check logs: `tail /var/log/memory-backup.log` |

## 🤝 Contributing

This is a community blueprint! If you improve it:

1. Fork the repo
2. Make your changes
3. Submit a PR
4. Share your video/tutorial!

## 📜 License

MIT License — use this however you want. Attribution appreciated but not required.

## 🙏 Credits

- OpenClaw community
- Mem0 for the user-centric memory architecture inspiration
- Qdrant for the amazing vector database

---

**Ready to build?** Run `./install.sh` and let's make AI that actually remembers! 🚀
