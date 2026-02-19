# Manual Backup & Restore Guide

> **Peace of mind**: Every file modified by the installer is backed up before changes are made.

## 📁 Where Backups Are Stored

Backups are stored in:
```
~/.openclaw/workspace/.backups/
```

Each installation creates a unique timestamped backup set:
```
.backups/
├── install_20260219_083012_crontab.bak.rush
├── install_20260219_083012_HEARTBEAT.md.bak.rush
├── install_20260219_083012_memory_env.bak.rush
└── install_20260219_083012_MANIFEST.txt
```

## 📋 What Gets Backed Up

| File | Why It's Backed Up | Restore Command |
|------|-------------------|-----------------|
| **Crontab** | Installer adds 2 cron jobs for daily backups | `crontab .backups/install_*_crontab.bak.rush` |
| **HEARTBEAT.md** | Installer creates/modifies automation config | `cp .backups/install_*_HEARTBEAT.md.bak.rush HEARTBEAT.md` |
| **.memory_env** | Installer creates environment variables | `cp .backups/install_*_memory_env.bak.rush .memory_env` |

## 🔄 How to Restore

### Quick Restore (One Command)

Each backup includes a `MANIFEST.txt` with exact restore commands:

```bash
cd ~/.openclaw/workspace/.backups
cat install_20260219_083012_MANIFEST.txt
```

### Step-by-Step Restore

#### 1. Find Your Backup

```bash
ls -la ~/.openclaw/workspace/.backups/
```

Look for files with pattern: `install_YYYYMMDD_HHMMSS_*.bak.rush`

#### 2. Restore Crontab (removes auto-backup jobs)

```bash
# List current crontab
crontab -l

# Restore from backup
crontab ~/.openclaw/workspace/.backups/install_20260219_083012_crontab.bak.rush

# Verify
crontab -l
```

#### 3. Restore HEARTBEAT.md

```bash
# Backup current first (just in case)
cp ~/.openclaw/workspace/HEARTBEAT.md ~/.openclaw/workspace/HEARTBEAT.md.manual_backup

# Restore from installer backup
cp ~/.openclaw/workspace/.backups/install_20260219_083012_HEARTBEAT.md.bak.rush \
   ~/.openclaw/workspace/HEARTBEAT.md
```

#### 4. Restore .memory_env

```bash
# Restore environment file
cp ~/.openclaw/workspace/.backups/install_20260219_083012_memory_env.bak.rush \
   ~/.openclaw/workspace/.memory_env

# Re-source it
source ~/.openclaw/workspace/.memory_env
```

## 🛡️ Creating Your Own Backups

Before making changes manually, create your own backup:

```bash
cd ~/.openclaw/workspace

# Backup everything important
tar -czf my_backup_$(date +%Y%m%d).tar.gz \
  HEARTBEAT.md \
  .memory_env \
  .backups/ \
  memory/

# Store it somewhere safe
cp my_backup_20260219.tar.gz ~/Documents/
```

## ⚠️ When to Restore

| Situation | Action |
|-----------|--------|
| Cron jobs causing issues | Restore crontab |
| HEARTBEAT.md corrupted | Restore HEARTBEAT.md |
| Wrong environment settings | Restore .memory_env |
| Complete removal wanted | Run `uninstall.sh` instead |
| Something broke | Check backup manifest, restore specific file |

## 🔧 Full System Restore Example

```bash
# 1. Go to workspace
cd ~/.openclaw/workspace

# 2. Identify your backup timestamp
BACKUP_DATE="20260219_083012"

# 3. Restore all files
crontab .backups/install_${BACKUP_DATE}_crontab.bak.rush
cp .backups/install_${BACKUP_DATE}_HEARTBEAT.md.bak.rush HEARTBEAT.md
cp .backups/install_${BACKUP_DATE}_memory_env.bak.rush .memory_env

# 4. Source the restored environment
source .memory_env

# 5. Verify
echo "Crontab:"
crontab -l | grep -E "(Memory System|cron_backup|sliding_backup)"

echo ""
echo "HEARTBEAT.md exists:"
ls -la HEARTBEAT.md

echo ""
echo ".memory_env:"
cat .memory_env
```

## 📝 Backup Naming Convention

| Pattern | Meaning |
|---------|---------|
| `install_YYYYMMDD_HHMMSS_*.bak.rush` | Automatic backup from installer |
| `*.manual_backup` | User-created manual backup |
| `*_crontab.bak.rush` | Crontab backup |
| `*_HEARTBEAT.md.bak.rush` | HEARTBEAT.md backup |
| `*_memory_env.bak.rush` | Environment file backup |

## 🗑️ Cleaning Up Old Backups

Backups don't auto-delete. Clean up periodically:

```bash
# List all backups
ls -la ~/.openclaw/workspace/.backups/

# Remove backups older than 30 days
find ~/.openclaw/workspace/.backups/ -name "*.bak.rush" -mtime +30 -delete

# Or remove specific timestamp
rm ~/.openclaw/workspace/.backups/install_20260219_083012_*
```

## ❓ FAQ

**Q: Will the installer overwrite my existing HEARTBEAT.md?**
A: It will backup the existing file first (as `HEARTBEAT.md.bak.rush`), then create the new one.

**Q: Can I run the installer multiple times?**
A: Yes! Each run creates new backups. The installer is idempotent (safe to run again).

**Q: What if I don't have a crontab yet?**
A: No problem - the installer detects this and won't try to backup a non-existent file.

**Q: Are my memories (Qdrant data) backed up?**
A: No - these backups are for configuration files only. Your actual memories stay in Qdrant until you explicitly delete them via `uninstall.sh`.

**Q: Where is the backup manifest?**
A: Each backup set includes a `install_YYYYMMDD_HHMMSS_MANIFEST.txt` with exact restore commands.

---

*Remember: When in doubt, backup first!* 🛡️
