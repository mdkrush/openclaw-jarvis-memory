#!/bin/bash
# OpenClaw Jarvis-Like Memory System - Installation Script
# This script sets up the complete memory system from scratch

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
WORKSPACE_DIR="${WORKSPACE_DIR:-$HOME/.openclaw/workspace}"
USER_ID="${USER_ID:-$(whoami)}"
REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
REDIS_PORT="${REDIS_PORT:-6379}"
QDRANT_URL="${QDRANT_URL:-http://127.0.0.1:6333}"
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"

# Backup directory
BACKUP_DIR="$WORKSPACE_DIR/.backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PREFIX="$BACKUP_DIR/install_${TIMESTAMP}"

echo "═══════════════════════════════════════════════════════════════"
echo "  OpenClaw Jarvis-Like Memory System - Installer"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo -e "${BLUE}Backup Location: $BACKUP_DIR${NC}"
echo ""

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Function to backup a file before modifying
backup_file() {
    local file="$1"
    local backup_name="$2"
    if [ -f "$file" ]; then
        cp "$file" "$backup_name"
        echo -e "${GREEN}  ✓ Backed up: $(basename $file) → $(basename $backup_name)${NC}"
        return 0
    fi
    return 1
}

# Step 1: Check Python version
echo -e "${YELLOW}[1/9] Checking Python...${NC}"
if command -v python3 &>/dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo "  ✓ Python $PYTHON_VERSION found"
else
    echo -e "${RED}  ✗ Python 3 not found. Please install Python 3.8+${NC}"
    exit 1
fi

# Step 2: Create directory structure
echo -e "${YELLOW}[2/9] Creating directory structure...${NC}"
mkdir -p "$WORKSPACE_DIR"/{skills/{mem-redis,qdrant-memory,task-queue}/scripts,memory,MEMORY_DEF}
touch "$WORKSPACE_DIR/memory/.gitkeep"
echo "  ✓ Directories created"

# Step 3: Install Python dependencies
echo -e "${YELLOW}[3/9] Installing Python dependencies...${NC}"
pip3 install --user redis qdrant-client requests urllib3 2>/dev/null || pip3 install redis qdrant-client requests urllib3
echo "  ✓ Dependencies installed"

# Step 4: Test infrastructure connectivity
echo -e "${YELLOW}[4/9] Testing infrastructure...${NC}"

# Test Redis
if python3 -c "import redis; r=redis.Redis(host='$REDIS_HOST', port=$REDIS_PORT); r.ping()" 2>/dev/null; then
    echo "  ✓ Redis connection OK"
else
    echo -e "${RED}  ✗ Redis connection failed ($REDIS_HOST:$REDIS_PORT)${NC}"
    echo "    Make sure Redis is running and accessible"
fi

# Test Qdrant
if curl -s "$QDRANT_URL/collections" >/dev/null 2>&1; then
    echo "  ✓ Qdrant connection OK"
else
    echo -e "${RED}  ✗ Qdrant connection failed ($QDRANT_URL)${NC}"
    echo "    Make sure Qdrant is running and accessible"
fi

# Test Ollama
if curl -s "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
    echo "  ✓ Ollama connection OK"
else
    echo -e "${RED}  ✗ Ollama connection failed ($OLLAMA_URL)${NC}"
    echo "    Make sure Ollama is running with snowflake-arctic-embed2 model"
fi

# Step 5: Backup existing files before modifying
echo ""
echo -e "${YELLOW}[5/9] Creating backups of existing files...${NC}"
BACKUP_COUNT=0

# Backup existing crontab
if crontab -l 2>/dev/null >/dev/null; then
    crontab -l > "${BACKUP_PREFIX}_crontab.bak.rush" 2>/dev/null
    echo -e "${GREEN}  ✓ Backed up crontab → .backups/install_${TIMESTAMP}_crontab.bak.rush${NC}"
    ((BACKUP_COUNT++))
else
    echo "  ℹ️  No existing crontab to backup"
fi

# Backup existing HEARTBEAT.md
if backup_file "$WORKSPACE_DIR/HEARTBEAT.md" "${BACKUP_PREFIX}_HEARTBEAT.md.bak.rush"; then
    ((BACKUP_COUNT++))
fi

# Backup existing .memory_env
if backup_file "$WORKSPACE_DIR/.memory_env" "${BACKUP_PREFIX}_memory_env.bak.rush"; then
    ((BACKUP_COUNT++))
fi

if [ $BACKUP_COUNT -eq 0 ]; then
    echo "  ℹ️  No existing files to backup (fresh install)"
else
    echo -e "${GREEN}  ✓ $BACKUP_COUNT file(s) backed up to $BACKUP_DIR${NC}"
fi

# Step 6: Create environment configuration
echo ""
echo -e "${YELLOW}[6/9] Creating environment configuration...${NC}"
cat > "$WORKSPACE_DIR/.memory_env" <<EOF
# Memory System Environment Variables
export WORKSPACE_DIR="$WORKSPACE_DIR"
export USER_ID="$USER_ID"
export REDIS_HOST="$REDIS_HOST"
export REDIS_PORT="$REDIS_PORT"
export QDRANT_URL="$QDRANT_URL"
export OLLAMA_URL="$OLLAMA_URL"
export MEMORY_INITIALIZED="true"
EOF
echo "  ✓ Created $WORKSPACE_DIR/.memory_env"

# Step 7: Initialize Qdrant collections
echo -e "${YELLOW}[7/9] Initializing Qdrant collections...${NC}"
python3 <<EOF
import sys
sys.path.insert(0, "$WORKSPACE_DIR/skills/qdrant-memory/scripts")
from init_kimi_memories import init_collection
init_collection()
print("  ✓ kimi_memories collection ready")
EOF

# Step 8: Set up cron jobs
echo -e "${YELLOW}[8/9] Setting up cron jobs...${NC}"
CRON_FILE=$(mktemp)
crontab -l 2>/dev/null > "$CRON_FILE" || true

# Add memory backup cron jobs if not present
if ! grep -q "cron_backup.py" "$CRON_FILE" 2>/dev/null; then
    echo "" >> "$CRON_FILE"
    echo "# Memory System - Daily backup (3:00 AM)" >> "$CRON_FILE"
    echo "0 3 * * * cd $WORKSPACE_DIR && python3 skills/mem-redis/scripts/cron_backup.py >> /var/log/memory-backup.log 2>&1 || true" >> "$CRON_FILE"
fi

if ! grep -q "sliding_backup.sh" "$CRON_FILE" 2>/dev/null; then
    echo "" >> "$CRON_FILE"
    echo "# Memory System - File backup (3:30 AM)" >> "$CRON_FILE"
    echo "30 3 * * * $WORKSPACE_DIR/skills/qdrant-memory/scripts/sliding_backup.sh >> /var/log/memory-backup.log 2>&1 || true" >> "$CRON_FILE"
fi

crontab "$CRON_FILE"
rm "$CRON_FILE"
echo "  ✓ Cron jobs configured"

# Step 9: Create HEARTBEAT.md template
echo -e "${YELLOW}[9/9] Creating HEARTBEAT.md...${NC}"
cat > "$WORKSPACE_DIR/HEARTBEAT.md" <<'EOF'
# HEARTBEAT.md - Memory System Automation

## Memory Buffer (Every Heartbeat)

Saves current session context to Redis buffer:

```bash
python3 /root/.openclaw/workspace/skills/mem-redis/scripts/save_mem.py --user-id YOUR_USER_ID
```

## Daily Backup Schedule

- **3:00 AM**: Redis buffer → Qdrant flush
- **3:30 AM**: File-based sliding backup

## Manual Commands

| Command | Action |
|---------|--------|
| `save mem` | Save all context to Redis |
| `save q` | Store immediately to Qdrant |
| `q <topic>` | Search memories |

EOF
echo "  ✓ HEARTBEAT.md created"

# Create backup manifest
echo ""
echo -e "${YELLOW}Creating backup manifest...${NC}"
MANIFEST_FILE="${BACKUP_PREFIX}_MANIFEST.txt"
cat > "$MANIFEST_FILE" <<EOF
OpenClaw Jarvis Memory - Installation Backup Manifest
======================================================
Date: $(date)
Timestamp: $TIMESTAMP
Backup Directory: $BACKUP_DIR

Files Backed Up:
EOF

# List backed up files
for file in "$BACKUP_DIR"/install_${TIMESTAMP}_*.bak.rush; do
    if [ -f "$file" ]; then
        basename "$file" >> "$MANIFEST_FILE"
    fi
done

cat >> "$MANIFEST_FILE" <<EOF

To Restore Files Manually:
==========================

1. Restore crontab:
   crontab "$BACKUP_DIR/install_${TIMESTAMP}_crontab.bak.rush"

2. Restore HEARTBEAT.md:
   cp "$BACKUP_DIR/install_${TIMESTAMP}_HEARTBEAT.md.bak.rush" "$WORKSPACE_DIR/HEARTBEAT.md"

3. Restore .memory_env:
   cp "$BACKUP_DIR/install_${TIMESTAMP}_memory_env.bak.rush" "$WORKSPACE_DIR/.memory_env"

All backups are stored in: $BACKUP_DIR
EOF

echo -e "${GREEN}  ✓ Backup manifest created: ${BACKUP_PREFIX}_MANIFEST.txt${NC}"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo -e "${GREEN}  Installation Complete!${NC}"
echo "═══════════════════════════════════════════════════════════════"
echo ""
if [ $BACKUP_COUNT -gt 0 ]; then
    echo -e "${BLUE}Backups created:${NC} $BACKUP_COUNT file(s) in $BACKUP_DIR"
    echo "  Timestamp: install_${TIMESTAMP}_*.bak.rush"
    echo ""
fi
echo "Next steps:"
echo "  1. Source the environment: source $WORKSPACE_DIR/.memory_env"
echo "  2. Test the system: python3 $WORKSPACE_DIR/skills/mem-redis/scripts/save_mem.py --user-id $USER_ID"
echo "  3. Add to your HEARTBEAT.md to enable automatic saving"
echo ""
echo "To undo installation:"
echo "  ./uninstall.sh"
echo ""
echo "To restore from backup:"
echo "  See $BACKUP_DIR/install_${TIMESTAMP}_MANIFEST.txt"
echo ""
echo "Documentation:"
echo "  - $WORKSPACE_DIR/docs/MEM_DIAGRAM.md"
echo "  - $WORKSPACE_DIR/skills/mem-redis/SKILL.md"
echo "  - $WORKSPACE_DIR/skills/qdrant-memory/SKILL.md"
echo ""
echo "Happy building! 🚀"
