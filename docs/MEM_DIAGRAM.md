# Memory System Architecture Diagrams

**Created:** February 18, 2026  
**Updated:** February 18, 2026 (v2.0 - Added QMD, Task Queue, Session Harvesting, Email Integration)  
**Purpose:** Complete backup of memory system architecture for Google Slides presentations

---

## Table of Contents

1. [Part 1: Built-in Memory System (OpenClaw Default)](#part-1-built-in-memory-system-openclaw-default)
2. [Part 2: Custom Memory System (What We Built)](#part-2-custom-memory-system-what-we-built)
3. [Part 3: Comparison — Built-in vs Custom](#part-3-comparison--built-in-vs-custom)
4. [Part 4: QMD (Query Markdown) — OpenClaw Experimental](#part-4-qmd-query-markdown--openclaw-experimental)
5. [Part 5: Task Queue System](#part-5-task-queue-system)
6. [Part 6: Session Harvesting](#part-6-session-harvesting)
7. [Part 7: Email Integration](#part-7-email-integration)
8. [Part 8: PROJECTNAME.md Workflow](#part-8-projectnamemd-workflow)
9. [Part 9: Complete Infrastructure Reference](#part-9-complete-infrastructure-reference)

---

## Part 1: Built-in Memory System (OpenClaw Default)

### Architecture Diagram

```
┌─────────────────────────────────────┐
│     OpenClaw Gateway Service        │
│  (Manages session state & routing)  │
└──────────────┬──────────────────────┘
               │
        ┌──────▼──────┐
        │   Session   │
        │   Context   │
        │ (In-Memory) │
        └──────┬──────┘
               │
        ┌──────▼──────────────────┐
        │  Message History Buffer │
        │     (Last N messages)   │
        │  Default: 8k-32k tokens │
        └──────┬──────────────────┘
               │
        ┌──────▼────────┐
        │   Model Input │
        │   (LLM Call)  │
        └───────────────┘
```

### How Built-in Memory Works

**Process Flow:**
1. **User sends message** → Added to session context
2. **Context accumulates** in memory (not persistent)
3. **Model receives** last N messages as context
4. **Session ends** → Context is **LOST**

**Key Characteristics:**
- ✅ Works automatically (no setup)
- ✅ Fast (in-memory)
- ❌ **Lost on /new or /reset**
- ❌ **Lost when session expires**
- ❌ No cross-session memory
- ❌ Limited context window (~8k-32k tokens)

### Built-in Limitations

| Feature | Status |
|---------|--------|
| Session Persistence | ❌ NO |
| Cross-Session Memory | ❌ NO |
| User-Centric Storage | ❌ NO |
| Long-Term Memory | ❌ NO |
| Semantic Search | ❌ NO |
| Conversation Threading | ❌ NO |
| Automatic Backup | ❌ NO |

---

## Part 2: Custom Memory System (What We Built)

### Complete Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      MULTI-LAYER MEMORY SYSTEM                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   LAYER 0: Real-Time Session Context (OpenClaw Gateway)             │
│   ┌─────────────────────────────────────────────────────────────┐ │
│   │  Session JSONL → Live context (temporary only)              │ │
│   └─────────────────────────────────────────────────────────────┘ │
│                              │                                       │
│   ┌──────────────────────────▼──────────────────────────────────┐  │
│   │  LAYER 1: Redis Buffer (Fast Short-Term)                     │  │
│   │  ├─ Key: mem:rob                                            │  │
│   │  ├─ Accumulates new turns since last check                 │  │
│   │  ├─ Heartbeat: Append-only (hb_append.py)                  │  │
│   │  ├─ Manual: Full dump (save_mem.py)                        │  │
│   │  └─ Flush: Daily 3:00 AM → Qdrant                          │  │
│   └──────────────────────────┬──────────────────────────────────┘  │
│                              │                                      │
│   ┌──────────────────────────▼──────────────────────────────────┐  │
│   │  LAYER 2: Daily File Logs (.md)                              │  │
│   │  ├─ Location: memory/YYYY-MM-DD.md                         │  │
│   │  ├─ Format: Human-readable Markdown                         │  │
│   │  ├─ Backup: 3:30 AM sliding_backup.sh                       │  │
│   │  └─ Retention: Permanent (git-tracked)                     │  │
│   └──────────────────────────┬──────────────────────────────────┘  │
│                              │                                      │
│   ┌──────────────────────────▼──────────────────────────────────┐  │
│   │  LAYER 3: Qdrant Vector DB (Semantic Long-Term)              │  │
│   │  ├─ Host: 10.0.0.40:6333                                    │  │
│   │  ├─ Embeddings: snowflake-arctic-embed2 (1024-dim)         │  │
│   │  ├─ Collections:                                            │  │
│   │  │   • kimi_memories (conversations)                        │  │
│   │  │   • kimi_kb (knowledge base)                            │  │
│   │  │   • private_court_docs (legal)                          │  │
│   │  ├─ Deduplication: Content hash per user                   │  │
│   │  └─ User-centric: user_id: "rob"                            │  │
│   └─────────────────────────────────────────────────────────────┘  │
│                                                                      │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  CROSS-CUTTING: Task Queue (Redis)                          │   │
│   │  ├─ tasks:pending → tasks:active → tasks:completed         │   │
│   │  └─ Heartbeat worker for background jobs                   │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  CROSS-CUTTING: Email Integration (Gmail)                   │   │
│   │  ├─ hb_check_email.py (Heartbeat)                          │   │
│   │  └─ Authorized senders: mdkrushr/a@gmail.com               │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Detailed Component Breakdown

#### Component 1: Daily File Logs
- **Location:** `/root/.openclaw/workspace/memory/YYYY-MM-DD.md`
- **Format:** Markdown with timestamps
- **Content:** Full conversation history
- **Access:** Direct file read
- **Retention:** Permanent (until deleted)
- **Auto-created:** Yes, every session
- **Backup:** `sliding_backup.sh` at 3:30 AM

#### Component 2: Redis Buffer (mem-redis skill)
- **Host:** `10.0.0.36:6379`
- **Key:** `mem:rob`
- **Type:** List (LPUSH append)
- **Purpose:** Fast access, multi-session accumulation
- **Flush:** Daily at 3:00 AM to Qdrant
- **No TTL:** Data persists until successfully backed up
- **Fail-safe:** If cron fails, data stays in Redis

**Scripts:**
| Script | Purpose |
|--------|---------|
| `hb_append.py` | Heartbeat: Add NEW turns only |
| `save_mem.py` | Manual: Save ALL turns (with --reset option) |
| `cron_backup.py` | Daily: Process Redis → Qdrant → Clear Redis |
| `mem_retrieve.py` | Manual: Retrieve recent turns from Redis |
| `search_mem.py` | Search both Redis (exact) + Qdrant (semantic) |

#### Component 3: Qdrant Vector Database
- **Host:** `http://10.0.0.40:6333`
- **Embeddings Model:** `snowflake-arctic-embed2` at `10.0.0.10:11434`
- **Vector Dimensions:** 1024
- **User-Centric:** All memories tagged with `user_id: "rob"`
- **Cross-Chat Search:** Find info from ANY past conversation

**Collections:**
| Collection | Purpose | Content |
|------------|---------|---------|
| `kimi_memories` | Personal conversations | User + AI messages |
| `kimi_kb` | Knowledge base | Web data, docs, tutorials |
| `private_court_docs` | Legal documents | Court files, legal research |

#### Component 4: Full Context Mode (Mem0-Style)

**3 Embeddings Per Turn:**
1. User message embedding
2. AI response embedding
3. Combined summary embedding

**Threading Metadata:**
- `user_id`: "rob" (persistent identifier)
- `conversation_id`: Groups related turns
- `session_id`: Which chat instance
- `turn_number`: Sequential ordering

#### Deduplication System

**What It Is:**
A content-based duplicate detection system that prevents storing the exact same information multiple times for the same user.

**How It Works:**
1. **Content Hash Generation:** Each memory generates a SHA-256 hash of its content
2. **Per-User Scope:** Deduplication is per-user (same content from different users = allowed)
3. **Pre-Storage Check:** Before storing to Qdrant, check if hash exists for this user
4. **Skip if Duplicate:** If hash exists → skip storage, return "already exists"
5. **Store if New:** If hash doesn't exist → generate embeddings and store

**Deduplication by Layer:**

| Layer | Deduplication | Behavior |
|-------|---------------|----------|
| **Daily Files** | ❌ No | All turns appended (intentional — audit trail) |
| **Redis Buffer** | ❌ No | All turns stored (temporary, flushed daily) |
| **Qdrant (kimi_memories)** | ✅ Yes | Per-user content hash check |
| **Qdrant (kimi_kb)** | ✅ Yes | Per-collection content hash check |

### Complete Script Reference

```
/root/.openclaw/workspace/
├── memory/
│   └── YYYY-MM-DD.md (daily logs)
│
├── skills/
│   ├── mem-redis/
│   │   └── scripts/
│   │       ├── hb_append.py (heartbeat: new turns only)
│   │       ├── save_mem.py (manual: all turns)
│   │       ├── cron_backup.py (daily flush to Qdrant)
│   │       ├── mem_retrieve.py (read from Redis)
│   │       └── search_mem.py (search Redis + Qdrant)
│   │
│   ├── qdrant-memory/
│   │   └── scripts/
│   │       ├── auto_store.py (immediate Qdrant storage)
│   │       ├── background_store.py (async storage)
│   │       ├── q_save.py (quick save trigger)
│   │       ├── daily_conversation_backup.py (file → Qdrant)
│   │       ├── get_conversation_context.py (retrieve threads)
│   │       ├── search_memories.py (semantic search)
│   │       ├── harvest_sessions.py (bulk import old sessions)
│   │       ├── harvest_newest.py (specific sessions)
│   │       ├── hb_check_email.py (email integration)
│   │       ├── sliding_backup.sh (file backup)
│   │       ├── kb_store.py / kb_search.py (knowledge base)
│   │       └── court_store.py / court_search.py (legal docs)
│   │
│   └── task-queue/
│       └── scripts/
│           ├── heartbeat_worker.py (process tasks)
│           ├── add_task.py (add background task)
│           └── list_tasks.py (view queue status)
│
└── MEMORY_DEF/
    ├── README.md
    ├── daily-backup.md
    └── agent-messaging.md
```

### Technical Flow

#### Real-Time (Every Message)
```
User Input → AI Response
     ↓
Redis Buffer (fast append)
     ↓
File Log (persistent)
     ↓
[Optional: "save q"] → Qdrant (semantic)
```

#### Heartbeat (Every ~30-60 min)
```
hb_append.py → Check for new turns → Append to Redis
hb_check_email.py → Check Gmail → Process new emails
heartbeat_worker.py → Check task queue → Execute tasks
```

#### Daily Backup (3:00 AM & 3:30 AM)
```
3:00 AM: Redis Buffer → Flush → Qdrant (kimi_memories)
         └─> Clear Redis after successful write

3:30 AM: Daily Files → sliding_backup.sh → Archive
         └─> daily_conversation_backup.py → Qdrant
```

#### On Retrieval ("search q" or "q <topic>")
```
Search Query
     ↓
search_mem.py
     ├──► Redis (exact text match, recent)
     └──► Qdrant (semantic similarity, long-term)
     ↓
Combined Results (Redis first, then Qdrant)
     ↓
Return context-enriched response
```

---

## Part 3: Comparison — Built-in vs Custom

### Feature Comparison Table

| Feature | Built-in | Custom System |
|---------|----------|---------------|
| **Session Persistence** | ❌ Lost on reset | ✅ Survives forever |
| **Cross-Session Memory** | ❌ None | ✅ All sessions linked |
| **User-Centric** | ❌ Session-based | ✅ User-based (Mem0-style) |
| **Semantic Search** | ❌ None | ✅ Full semantic retrieval |
| **Conversation Threading** | ❌ Linear only | ✅ Thread-aware |
| **Long-Term Storage** | ❌ Hours only | ✅ Permanent (disk + vector) |
| **Backup & Recovery** | ❌ None | ✅ Multi-layer redundancy |
| **Privacy** | ⚠️ Cloud dependent | ✅ Fully local/self-hosted |
| **Speed** | ✅ Fast (RAM) | ✅ Fast (Redis) + Deep (Qdrant) |
| **Cost** | ❌ OpenAI API tokens | ✅ Free (local infrastructure) |
| **Embeddings** | ❌ None | ✅ 1024-dim (snowflake) |
| **Cross-Reference** | ❌ None | ✅ Links related memories |
| **Task Queue** | ❌ None | ✅ Background job processing |
| **Email Integration** | ❌ None | ✅ Gmail via Pub/Sub |
| **Deduplication** | ❌ None | ✅ Content hash-based |

### Why It's Better — Key Advantages

#### 1. Mem0-Style Architecture
- Memories follow the **USER**, not the session
- Ask "what did I say about X?" → finds from **ANY** past conversation
- Persistent identity across all chats

#### 2. Hybrid Storage Strategy
- **Redis:** Speed (real-time access)
- **Files:** Durability (never lost, human-readable)
- **Qdrant:** Intelligence (semantic search, similarity)

#### 3. Multi-Modal Retrieval
- **Exact match:** File grep, exact text search
- **Semantic search:** Vector similarity, conceptual matching
- **Thread reconstruction:** Conversation_id grouping

#### 4. Local-First Design
- No cloud dependencies
- No API costs (except initial setup)
- Full privacy control
- Works offline
- Self-hosted infrastructure

#### 5. Triple Redundancy
| Layer | Purpose | Persistence |
|-------|---------|-------------|
| Redis | Speed | Temporary (daily flush) |
| Files | Durability | Permanent |
| Qdrant | Intelligence | Permanent |

---

## Part 4: QMD (Query Markdown) — OpenClaw Experimental

### What is QMD?

**QMD** = **Query Markdown** — OpenClaw's experimental local-first memory backend that replaces the built-in SQLite indexer.

**Key Difference:**
- Current system: SQLite + vector embeddings
- QMD: **BM25 + vectors + reranking** in a standalone binary

### QMD Architecture

```
┌─────────────────────────────────────────────┐
│  QMD Sidecar (Experimental)                 │
│  ├─ BM25 (exact token matching)            │
│  ├─ Vector similarity (semantic)           │
│  └─ Reranking (smart result ordering)      │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────▼──────────┐
        │  Markdown Source    │
        │  memory/*.md        │
        │  MEMORY.md          │
        └─────────────────────┘
```

### QMD vs Current System

| Feature | Current (Qdrant) | QMD (Experimental) |
|---------|------------------|-------------------|
| **Storage** | Qdrant server (10.0.0.40) | Local SQLite + files |
| **Network** | Requires network | Fully offline |
| **Search** | Vector only | Hybrid (BM25 + vector) |
| **Exact tokens** | Weak | Strong (BM25) |
| **Embeddings** | snowflake-arctic-embed2 | Local GGUF models |
| **Git-friendly** | ❌ Opaque vectors | ✅ Markdown source |
| **Explainable** | Partial | Full (file.md#L12 citations) |
| **Status** | Production | Experimental |

### When QMD Might Be Better

✅ **Use QMD if:**
- You want **full offline** operation (no 10.0.0.40 dependency)
- You frequently search for **exact tokens** (IDs, function names, error codes)
- You want **human-editable** memory files
- You want **git-tracked** memory that survives system rebuilds

❌ **Stick with Qdrant if:**
- Your current system is stable
- You need **multi-device** access to same memory
- You're happy with **semantic-only** search
- You need **production reliability**

### QMD Configuration (OpenClaw)

```json5
memory: {
  backend: "qmd",
  citations: "auto",
  qmd: {
    includeDefaultMemory: true,
    update: { interval: "5m", debounceMs: 15000 },
    limits: { maxResults: 6, timeoutMs: 4000 },
    paths: [
      { name: "docs", path: "~/notes", pattern: "**/*.md" }
    ]
  }
}
```

### QMD Prerequisites

```bash
# Install QMD binary
bun install -g https://github.com/tobi/qmd

# Install SQLite with extensions (macOS)
brew install sqlite

# QMD auto-downloads GGUF models on first run (~0.6GB)
```

---

## Part 5: Task Queue System

### Architecture

```
┌─────────────────────────────────────────────┐
│  Redis Task Queue                          │
│  ├─ tasks:pending (FIFO)                 │
│  ├─ tasks:active (currently running)     │
│  ├─ tasks:completed (history)              │
│  └─ task:{id} (hash with details)         │
└──────────────────┬────────────────────────┘
                   │
        ┌──────────▼──────────┐
        │  Heartbeat Worker   │
        │  heartbeat_worker.py│
        └─────────────────────┘
```

### Task Fields
- `id` - Unique task ID
- `description` - What to do
- `status` - pending/active/completed/failed
- `created_at` - Timestamp
- `created_by` - Who created the task
- `result` - Output from execution

### Usage

```bash
# Add a task
python3 skills/task-queue/scripts/add_task.py "Check server disk space"

# List tasks
python3 skills/task-queue/scripts/list_tasks.py

# Heartbeat auto-executes pending tasks
python3 skills/task-queue/scripts/heartbeat_worker.py
```

---

## Part 6: Session Harvesting

### What is Session Harvesting?

Bulk import of historical OpenClaw session JSONL files into Qdrant memory.

### When to Use

- After setting up new memory system → backfill existing sessions
- After discovering missed backups → recover data
- Periodically → if cron jobs missed data

### Scripts

| Script | Purpose |
|--------|---------|
| `harvest_sessions.py` | Auto-harvest (limited by memory) |
| `harvest_newest.py` | Specific sessions (recommended) |

### Usage

```bash
# Harvest specific sessions (recommended)
python3 harvest_newest.py --user-id rob session-1.jsonl session-2.jsonl

# Find newest sessions to harvest
ls -t /root/.openclaw/agents/main/sessions/*.jsonl | head -20

# Auto-harvest with limit
python3 harvest_sessions.py --user-id rob --limit 10
```

### How It Works

1. **Parse** → Reads JSONL session file
2. **Pair** → Matches user message with AI response
3. **Embed** → Generates 3 embeddings (user, AI, summary)
4. **Deduplicate** → Checks content_hash before storing
5. **Store** → Upserts to Qdrant with user_id, conversation_id

---

## Part 7: Email Integration

### Architecture

```
┌─────────────────────────────────────────────┐
│  Gmail Inbox                               │
│  (mdkrushr@gmail.com, mdkrusha@gmail.com) │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────▼──────────┐
        │  hb_check_email.py  │
        │  (Heartbeat)         │
        └─────────────────────┘
```

### Authorized Senders
- `mdkrushr@gmail.com` (Rob)
- `mdkrusha@gmail.com` (Jennifer)

### Usage

```bash
# Check emails (runs automatically in heartbeat)
python3 skills/qdrant-memory/scripts/hb_check_email.py
```

### How It Works
1. Polls Gmail for new messages
2. Filters by authorized senders
3. Reads subject and body
4. Searches Qdrant for context
5. Responds with helpful reply
6. Stores email + response to Qdrant

---

## Part 8: PROJECTNAME.md Workflow

*See original document for full details — this is a summary reference.*

### Purpose
Preserve context, decisions, and progress across sessions.

### The Golden Rule — Append Only
**NEVER Overwrite. ALWAYS Append.**

### File Structure Template
```markdown
# PROJECTNAME.md

## Project Overview
- **Goal:** What we're achieving
- **Scope:** What's in/out
- **Success Criteria:** How we know it's done

## Current Status
- [x] Completed tasks
- [ ] In progress
- [ ] Upcoming

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-02-18 | Use X over Y | Because of Z |

## Technical Details
- Infrastructure specs
- Code snippets
- Configuration

## Blockers & Risks
- What's blocking progress
- Known issues

## Next Steps
- Immediate actions
- Questions to resolve
```

### Real Examples

| File | Project | Status |
|------|---------|--------|
| `MEM_DIAGRAM.md` | Memory system documentation | ✅ Active |
| `AUDIT-PLAN.md` | OpenClaw infrastructure audit | ✅ Completed |
| `YOUTUBE_UPDATE.md` | Video description optimization | 🔄 Ongoing |

---

## Part 9: Complete Infrastructure Reference

### Hardware/Network Topology

```
┌────────────────────────────────────────────────────────────────┐
│                     PROXMOX CLUSTER                            │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │  Ollama      │  │  Qdrant      │  │  Redis       │        │
│  │  10.0.0.10   │  │  10.0.0.40   │  │  10.0.0.36   │        │
│  │  GPU Node     │  │  LXC          │  │  LXC          │        │
│  │  Embeddings   │  │  Vector DB    │  │  Task Queue   │        │
│  │  11434        │  │  6333         │  │  6379         │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │  SearXNG     │  │  Kokoro TTS  │  │  OpenClaw    │        │
│  │  10.0.0.8    │  │  10.0.0.228  │  │  Workspace   │        │
│  │  Search       │  │  Voice        │  │  Kimi         │        │
│  │  8888         │  │  8880         │  │               │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### Service Reference

| Service | Purpose | Address | Model/Version |
|---------|---------|---------|-------------|
| Qdrant | Vector database | 10.0.0.40:6333 | v1.x |
| Redis | Buffer + tasks | 10.0.0.36:6379 | v7.x |
| Ollama | Embeddings | 10.0.0.10:11434 | snowflake-arctic-embed2 |
| SearXNG | Search | 10.0.0.8:8888 | Local |
| Kokoro TTS | Voice | 10.0.0.228:8880 | TTS |

### Daily Automation Schedule

| Time | Task | Script |
|------|------|--------|
| 3:00 AM | Redis → Qdrant flush | `cron_backup.py` |
| 3:30 AM | File-based sliding backup | `sliding_backup.sh` |
| Every 30-60 min | Heartbeat checks | `hb_append.py`, `hb_check_email.py` |

### Manual Triggers

| Command | What It Does |
|---------|--------------|
| `"save mem"` | Save ALL context to Redis + File |
| `"save q"` | Immediate Qdrant storage |
| `"q <topic>"` | Semantic search |
| `"search q <topic>"` | Full semantic search |
| `"remember this"` | Quick note to daily file |
| `"check messages"` | Check Redis for agent messages |
| `"send to Max"` | Send message to Max via Redis |

### Environment Variables

```bash
# Qdrant
QDRANT_URL=http://10.0.0.40:6333

# Redis
REDIS_HOST=10.0.0.36
REDIS_PORT=6379

# Ollama
OLLAMA_URL=http://10.0.0.10:11434

# User
DEFAULT_USER_ID=rob
```

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-18 | 1.0 | Initial documentation |
| 2026-02-18 | 2.0 | Added QMD, Task Queue, Session Harvesting, Email Integration, complete script reference |

---

## Quick Reference Card

### Memory Commands
```
save mem      → Redis + File (all turns)
save q        → Qdrant (semantic, embeddings)
q <topic>     → Search Qdrant
remember this → Quick note to file
```

### Architecture Layers
```
Layer 0: Session Context (temporary)
Layer 1: Redis Buffer (fast, 3:00 AM flush)
Layer 2: File Logs (permanent, human-readable)
Layer 3: Qdrant (semantic, searchable)
```

### Key Files
```
memory/YYYY-MM-DD.md     → Daily conversation logs
MEMORY.md                → Curated long-term memory
MEMORY_DEF/*.md          → System documentation
skills/*/scripts/*.py    → Automation scripts
```

### Infrastructure
```
10.0.0.40:6333 → Qdrant (vectors)
10.0.0.36:6379 → Redis (buffer + tasks)
10.0.0.10:11434 → Ollama (embeddings)
```

---

*This document serves as the complete specification for the memory system.*
*For questions or updates, see MEMORY.md or the SKILL.md files in each skill directory.*
