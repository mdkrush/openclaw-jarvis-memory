# OpenClaw Jarvis-Like Memory System

> **Build an AI assistant that actually remembers you.**
> 
> **GitHub:** https://github.com/mdkrush/openclaw-jarvis-memory
> 
> **Version: 1.5.0** (February 19, 2026)
> 
> **Changelog:**
> - v1.5.0: Merged community PR #1 - cron capture (token-free), safer backups, auto-dependencies, portable defaults
> - v1.4.0: Added compaction threshold recommendation (90%) with manual setup steps
> - v1.3.0: Added complete command reference, documented known issues with compaction timing
> - v1.2.0: Added automatic backup to installer, RESTORE.md documentation
> - v1.1.0: Added uninstall.sh recovery script
> - v1.0.0: Initial release with 52 scripts, complete tutorial

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

# 2. Run the installer (automatically backs up existing files)
cd ~/.openclaw/workspace
chmod +x install.sh
./install.sh

# 3. Source the environment
source .memory_env

# 4. Test it
python3 skills/mem-redis/scripts/save_mem.py --user-id yourname
```

**🔒 The installer automatically backs up** your existing `HEARTBEAT.md`, `.memory_env`, and crontab before making changes. Backups are stored in `.backups/` with timestamps.

**See [RESTORE.md](RESTORE.md)** for how to restore from backups manually.

---

## 📋 Files Modified by Installer

When you run `./install.sh`, the following files in your OpenClaw workspace are **modified** (backed up first as `.bak.rush` files):

### Files That Get Modified (with Backup)

| File | Location | What Installer Does | Backup Location |
|------|----------|---------------------|-----------------|
| **crontab** | System crontab | Adds 2 daily cron jobs for backups | `.backups/install_*_crontab.bak.rush` |
| **HEARTBEAT.md** | `~/.openclaw/workspace/HEARTBEAT.md` | Creates or overwrites with memory automation | `.backups/install_*_HEARTBEAT.md.bak.rush` |
| **.memory_env** | `~/.openclaw/workspace/.memory_env` | Creates environment variables file | `.backups/install_*_memory_env.bak.rush` |

### Files That Get Created (New)

| File | Location | Purpose |
|------|----------|---------|
| **52 Python scripts** | `~/.openclaw/workspace/skills/mem-redis/scripts/` (5 files)<br>`~/.openclaw/workspace/skills/qdrant-memory/scripts/` (43 files)<br>`~/.openclaw/workspace/skills/task-queue/scripts/` (3 files) | Core memory system functionality |
| **SKILL.md** | `~/.openclaw/workspace/skills/mem-redis/SKILL.md` | Redis skill documentation |
| **SKILL.md** | `~/.openclaw/workspace/skills/qdrant-memory/SKILL.md` | Qdrant skill documentation |
| **SKILL.md** | `~/.openclaw/workspace/skills/task-queue/SKILL.md` | Task queue documentation |
| **memory/** | `~/.openclaw/workspace/memory/` | Daily markdown log files directory |
| **.gitkeep** | `~/.openclaw/workspace/memory/.gitkeep` | Keeps memory dir in git |
| **Backup Manifest** | `~/.openclaw/workspace/.backups/install_*_MANIFEST.txt` | Lists all backups with restore commands |

### Full Path List for Manual Restore

If you need to restore manually without using the uninstaller, here's every single file path:

**Configuration Files (Modified):**
```
~/.openclaw/workspace/HEARTBEAT.md          # Automation config
~/.openclaw/workspace/.memory_env           # Environment variables
~/.openclaw/workspace/.mem_last_turn        # State tracking (created)
```

**Skill Files (Created - 52 total scripts):**
```
# Redis Buffer (5 scripts)
~/.openclaw/workspace/skills/mem-redis/scripts/hb_append.py
~/.openclaw/workspace/skills/mem-redis/scripts/save_mem.py
~/.openclaw/workspace/skills/mem-redis/scripts/cron_backup.py
~/.openclaw/workspace/skills/mem-redis/scripts/mem_retrieve.py
~/.openclaw/workspace/skills/mem-redis/scripts/search_mem.py
~/.openclaw/workspace/skills/mem-redis/SKILL.md

# Qdrant Memory (43 scripts - key ones listed)
~/.openclaw/workspace/skills/qdrant-memory/scripts/auto_store.py
~/.openclaw/workspace/skills/qdrant-memory/scripts/q_save.py
~/.openclaw/workspace/skills/qdrant-memory/scripts/search_memories.py
~/.openclaw/workspace/skills/qdrant-memory/scripts/init_kimi_memories.py
~/.openclaw/workspace/skills/qdrant-memory/scripts/init_kimi_kb.py
~/.openclaw/workspace/skills/qdrant-memory/scripts/init_private_court_docs.py
~/.openclaw/workspace/skills/qdrant-memory/scripts/daily_conversation_backup.py
~/.openclaw/workspace/skills/qdrant-memory/scripts/harvest_sessions.py
~/.openclaw/workspace/skills/qdrant-memory/scripts/sliding_backup.sh
~/.openclaw/workspace/skills/qdrant-memory/scripts/store_conversation.py
~/.openclaw/workspace/skills/qdrant-memory/SKILL.md
~/.openclaw/workspace/skills/qdrant-memory/HARVEST.md
# ... (33 more scripts - see skills/qdrant-memory/scripts/)

# Task Queue (3 scripts)
~/.openclaw/workspace/skills/task-queue/scripts/add_task.py
~/.openclaw/workspace/skills/task-queue/scripts/heartbeat_worker.py
~/.openclaw/workspace/skills/task-queue/scripts/list_tasks.py
~/.openclaw/workspace/skills/task-queue/SKILL.md
```

**Directories Created:**
```
~/.openclaw/workspace/skills/mem-redis/scripts/
~/.openclaw/workspace/skills/qdrant-memory/scripts/
~/.openclaw/workspace/skills/task-queue/scripts/
~/.openclaw/workspace/memory/
~/.openclaw/workspace/.backups/
```

---

### 🧹 Uninstall/Recovery

If you need to remove the memory system:

```bash
./uninstall.sh
```

This interactive script will:
- Remove cron jobs
- Clear Redis buffer
- Optionally delete Qdrant collections (your memories)
- Remove configuration files
- Optionally remove all skill files

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

### Memory Commands Reference

These are the commands you can use once the memory system is installed:

| Command | What It Does | Data Layer | When to Use |
|---------|--------------|------------|-------------|
| **`save mem`** | Saves ALL conversation turns to Redis buffer + daily file | Layer 1 (Redis) + Layer 2 (Files) | When you want to capture current session |
| **`save q`** | Stores current exchange to Qdrant with embeddings | Layer 3 (Qdrant) | When you want immediate long-term searchable memory |
| **`q <topic>`** | Semantic search across all stored memories | Layer 3 (Qdrant) | Find past conversations by meaning, not keywords |
| **`remember this`** | Quick note to daily file (manual note) | Layer 2 (Files) | Important facts you want to log |

**Data Flow:**
```
User: "save mem"     → Redis Buffer + File Log (fast, persistent)
User: "save q"       → Qdrant Vector DB (semantic, searchable)
User: "q <topic>"    → Searches embeddings for similar content
```

### Automated Flow

```
Every Message (capture option A: heartbeat, capture option B: cron capture)
     ↓
Redis Buffer (fast, survives session reset)
     ↓
File Log (permanent, human-readable markdown)
     ↓
[Optional: User says "save q"] → Qdrant (semantic search)

Cost note: cron capture avoids LLM heartbeats entirely and is the recommended default for token savings.

Cron capture quick test (no Redis required):
```bash
python3 skills/mem-redis/scripts/cron_capture.py --dry-run --user-id yourname
```

Daily 3:00 AM (cron)
     ↓
Redis Buffer → Flush → Qdrant (with embeddings)
     ↓
Clear Redis (ready for new day)

Daily 3:30 AM (cron)
     ↓
Daily Files → Sliding Backup → Archive
```

### Cron Capture (Token-Free Alternative)

**New in v1.5.0:** `cron_capture.py` provides a **zero-token** alternative to heartbeat capture.

**Why use it:**
- **Saves money** - No LLM calls to capture transcripts
- **Runs every 5 minutes** via cron (no session API needed)
- **Tracks file position** - Only reads NEW content since last run
- **Optional thinking capture** - Store model thinking separately

**Setup:**
```bash
# Add to crontab (runs every 5 minutes)
*/5 * * * * cd ~/.openclaw/workspace/blueprint && python3 skills/mem-redis/scripts/cron_capture.py --user-id yourname
```

**Test it:**
```bash
# Dry run (shows what would be captured)
python3 skills/mem-redis/scripts/cron_capture.py --dry-run --user-id yourname

# Run for real
python3 skills/mem-redis/scripts/cron_capture.py --user-id yourname
```

**Capture Options Comparison:**

| Method | Token Cost | Trigger | Best For |
|--------|------------|---------|----------|
| **Heartbeat** | ~1K tokens/turn | Every OpenClaw message | Real-time, always-on |
| **Cron Capture** | **FREE** | Every 5 minutes | Cost-conscious, periodic |
| **Manual `save mem`** | FREE | On demand | Important sessions |

**Note:** You can use BOTH - cron capture for background accumulation, heartbeat for real-time critical sessions.

---

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
export REDIS_HOST="127.0.0.1"
export REDIS_PORT="6379"
export QDRANT_URL="http://127.0.0.1:6333"
export OLLAMA_URL="http://127.0.0.1:11434"
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

## ⚠️ Known Issues

### Gap Between Heartbeat/Save and Compaction

**The Issue:**  
There is a small timing window where data can be lost:

1. OpenClaw session JSONL files get "compacted" (rotated/archived) periodically
2. If a heartbeat or `save mem` runs *after* compaction but *before* a new session starts, it may miss the last few turns
3. The Redis buffer tracks turns by number, but the source file has changed

**Impact:**  
- Low - happens only during active session compaction
- Affects only the most recent turns if timing is unlucky
- Daily file logs usually still have the data

**Workaround:**  
- Run `save mem` manually before ending important sessions
- The cron job at 3:00 AM catches anything missed during the day
- Use `save q` for critical exchanges (goes directly to Qdrant immediately)

### Recommendation: Adjust Compaction Threshold

To reduce how often this issue occurs, **set OpenClaw's session compaction threshold to 90%** (default is often lower). This makes compaction happen less frequently, shrinking the timing window.

**Manual Steps (Not in Installer):**

1. **Locate your OpenClaw config:**
   ```bash
   # Find your OpenClaw configuration file
   ls ~/.openclaw/config/  # or wherever your config lives
   ```

2. **Edit the compaction setting:**
   ```bash
   # Look for session or compaction settings
   # Add or modify:
   # "session_compaction_threshold": 90
   ```

3. **Alternative - via environment variable:**
   ```bash
   # Add to your shell profile or .memory_env:
   export OPENCLAW_COMPACTION_THRESHOLD=90
   ```

4. **Restart OpenClaw gateway:**
   ```bash
   openclaw gateway restart
   ```

**Why 90%?**
- Default is often 50-70%, causing frequent compactions
- 90% means files grow larger before rotation
- Less frequent compaction = smaller timing window for data loss
- Still protects disk space from runaway log files

**Note:** The installer does NOT change this setting automatically, as it requires OpenClaw gateway restart and may vary by installation. This is a manual optimization step.

---

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
