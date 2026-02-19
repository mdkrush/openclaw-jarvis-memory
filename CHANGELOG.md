# Changelog

All notable changes to the OpenClaw Jarvis-Like Memory System blueprint.

## [1.5.0] - 2026-02-19

### Added (Community PR #1 by ecomm-michael)
- **cron_capture.py** - Token-free transcript capture via cron (no LLM calls, saves money)
- **Safer Redis→Qdrant flush** - Only clears Redis if ALL user turns stored successfully
- **Auto-dependency installation** - install.sh now auto-installs Docker, Python, Redis if missing
- **llm_router.py** - Routes to cheap LLMs (Minimax) via OpenRouter with fallback
- **metadata_and_compact.py** - Auto-generates tags, titles, summaries using cheap LLM
- **tagger.py** - Content tagging for better organization
- **Portable defaults** - Changed hardcoded 10.0.0.x IPs to localhost (127.0.0.1) with env overrides
- **PEP 668 compliance** - Creates Python venv if pip --user blocked

### Changed
- **cron_backup.py** - Better error handling, preserves Redis on Qdrant failure
- **hb_append.py** - Doesn't store thinking in main buffer (separate mem_thinking key)
- **auto_store.py** - Uses SHA256 instead of MD5 for content hashing (portable)
- **init_kimi_memories.py** - Env-driven config with defaults
- **task-queue scripts** - Removed hardcoded SSH credentials (security cleanup)
- **docker-compose.yml** - Disabled container healthcheck (qdrant image lacks curl)

### Security
- Changed default USER_ID from "rob" to "yourname" in all scripts (privacy)
- Removed hardcoded credentials from task-queue

### Contributors
- **ecomm-michael** - Major contribution: portability, cron capture, safer backups, metadata pipeline

---

## [1.4.0] - 2026-02-19

### Added
- **Compaction threshold recommendation** - Added guide to set OpenClaw to 90% to reduce timing window
- **Manual setup steps** - Clear instructions (not automated) for adjusting compaction setting
- **Explanation** - Why 90% helps and how it relates to the known timing issue

### Changed
- README Known Issues section expanded with "Adjust Compaction Threshold" subsection
- Added manual configuration steps that users should do post-installation

---

## [1.3.0] - 2026-02-19

### Added
- **Complete command reference** in README - documents all 4 memory commands with usage
- **Known Issues section** - documents the compaction timing window issue
- Command table showing what each command does, which layer it hits, and when to use it

### Changed
- README Memory Commands section expanded with detailed reference table
- Added data flow diagrams for both manual and automated memory storage

---

## [1.2.0] - 2026-02-19

### Added
- **Automatic backup functionality** in `install.sh` - backs up all modified files before changes
- **RESTORE.md** - Complete manual backup/restore documentation
- **Version tracking** - Added version number to README and this CHANGELOG

### Changed
- `install.sh` now creates `.backups/` directory with timestamped `.bak.rush` files
- `install.sh` generates `MANIFEST.txt` with exact restore commands
- README now documents every single file that gets modified or created

### Files Modified in This Release
- `install.sh` - Added backup functionality (Step 5)
- `README.md` - Added version header, file inventory section
- `MANIFEST.md` - Updated component list, added RESTORE.md

### Files Added in This Release
- `RESTORE.md` - Complete restore documentation
- `CHANGELOG.md` - This file

---

## [1.1.0] - 2026-02-19

### Added
- **uninstall.sh** - Interactive recovery/uninstall script
- Uninstall script removes: cron jobs, Redis buffer, Qdrant collections (optional), config files

### Changed
- `README.md` - Added uninstall section
- `MANIFEST.md` - Added uninstall.sh to file list

### Files Added in This Release
- `uninstall.sh` - Recovery script

---

## [1.0.0] - 2026-02-18

### Added
- Initial release of complete Jarvis-like memory system
- **52 Python scripts** across 3 skills:
  - mem-redis (5 scripts) - Fast buffer layer
  - qdrant-memory (43 scripts) - Vector database layer  
  - task-queue (3 scripts) - Background job processing
- **install.sh** - One-command installer
- **docker-compose.yml** - Complete infrastructure setup (Qdrant, Redis, Ollama)
- **README.md** - Complete documentation
- **TUTORIAL.md** - YouTube video script
- **MANIFEST.md** - File index
- **docs/MEM_DIAGRAM.md** - Architecture documentation
- **.gitignore** - Excludes cache files, credentials

### Features
- Three-layer memory architecture (Redis → Files → Qdrant)
- User-centric storage (not session-based)
- Semantic search with 1024-dim embeddings
- Automatic daily backups via cron
- Deduplication via content hashing
- Conversation threading with metadata

### Infrastructure
- Qdrant at 10.0.0.40:6333
- Redis at 10.0.0.36:6379
- Ollama at 10.0.0.10:11434 with snowflake-arctic-embed2

---

## Version History Summary

| Version | Date | Key Changes |
|---------|------|-------------|
| 1.2.0 | 2026-02-19 | Auto-backup, RESTORE.md, version tracking |
| 1.1.0 | 2026-02-19 | uninstall.sh recovery script |
| 1.0.0 | 2026-02-18 | Initial release, 52 scripts, full tutorial |

---

## Version Numbering

We follow [Semantic Versioning](https://semver.org/):
- **MAJOR** (X.0.0) - Breaking changes, major architecture changes
- **MINOR** (x.X.0) - New features, backwards compatible
- **PATCH** (x.x.X) - Bug fixes, small improvements

---

*Last updated: February 19, 2026*
