# Changelog

All notable changes to the OpenClaw Jarvis-Like Memory System blueprint.

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
