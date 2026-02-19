#!/bin/bash
# OpenClaw Jarvis-Like Memory System - Installation Script
# This script sets up the complete memory system from scratch

set -e

echo "═══════════════════════════════════════════════════════════════"
echo "  OpenClaw Jarvis-Like Memory System - Installer"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
WORKSPACE_DIR="${WORKSPACE_DIR:-$HOME/.openclaw/workspace}"
USER_ID="${USER_ID:-$(whoami)}"
REDIS_HOST="${REDIS_HOST:-10.0.0.36}"
REDIS_PORT="${REDIS_PORT:-6379}"
QDRANT_URL="${QDRANT_URL:-http://10.0.0.40:6333}"
OLLAMA_URL="${OLLAMA_URL:-http://10.0.0.10:11434}"

echo "Configuration:"
echo "  Workspace: $WORKSPACE_DIR"
echo "  User ID: $USER_ID"
echo "  Redis: $REDIS_HOST:$REDIS_PORT"
echo "  Qdrant: $QDRANT_URL"
echo "  Ollama: $OLLAMA_URL"
echo ""

# Step 1: Check Python version
echo -e "${YELLOW}[1/8] Checking Python...${NC}"
if command -v python3 &>/dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo "  ✓ Python $PYTHON_VERSION found"
else
    echo -e "${RED}  ✗ Python 3 not found. Please install Python 3.8+${NC}"
    exit 1
fi

# Step 2: Create directory structure
echo -e "${YELLOW}[2/8] Creating directory structure...${NC}"
mkdir -p "$WORKSPACE_DIR"/{skills/{mem-redis,qdrant-memory,task-queue}/scripts,memory,MEMORY_DEF}
touch "$WORKSPACE_DIR/memory/.gitkeep"
echo "  ✓ Directories created"

# Step 3: Install Python dependencies
echo -e "${YELLOW}[3/8] Installing Python dependencies...${NC}"
pip3 install --user redis qdrant-client requests urllib3 2>/dev/null || pip3 install redis qdrant-client requests urllib3
echo "  ✓ Dependencies installed"

# Step 4: Test infrastructure connectivity
echo -e "${YELLOW}[4/8] Testing infrastructure...${NC}"

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

# Step 5: Create environment configuration
echo -e "${YELLOW}[5/8] Creating environment configuration...${NC}"
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

# Step 6: Initialize Qdrant collections
echo -e "${YELLOW}[6/8] Initializing Qdrant collections...${NC}"
python3 <<EOF
import sys
sys.path.insert(0, "$WORKSPACE_DIR/skills/qdrant-memory/scripts")
from init_kimi_memories import init_collection
init_collection()
print("  ✓ kimi_memories collection ready")
EOF

# Step 7: Set up cron jobs
echo -e "${YELLOW}[7/8] Setting up cron jobs...${NC}"
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

# Step 8: Create HEARTBEAT.md template
echo -e "${YELLOW}[8/8] Creating HEARTBEAT.md...${NC}"
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

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo -e "${GREEN}  Installation Complete!${NC}"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "  1. Source the environment: source $WORKSPACE_DIR/.memory_env"
echo "  2. Test the system: python3 $WORKSPACE_DIR/skills/mem-redis/scripts/save_mem.py --user-id $USER_ID"
echo "  3. Add to your HEARTBEAT.md to enable automatic saving"
echo ""
echo "Documentation:"
echo "  - $WORKSPACE_DIR/docs/MEM_DIAGRAM.md"
echo "  - $WORKSPACE_DIR/skills/mem-redis/SKILL.md"
echo "  - $WORKSPACE_DIR/skills/qdrant-memory/SKILL.md"
echo ""
echo "Happy building! 🚀"
