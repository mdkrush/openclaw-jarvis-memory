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

# Optional toggles (avoid touching host config during tests)
SKIP_CRON="${SKIP_CRON:-0}"
SKIP_HEARTBEAT="${SKIP_HEARTBEAT:-0}"
SKIP_QDRANT_INIT="${SKIP_QDRANT_INIT:-0}"

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

# Helpers
have_cmd() { command -v "$1" >/dev/null 2>&1; }

need_sudo() {
  if [ "$(id -u)" -eq 0 ]; then
    return 1
  fi
  return 0
}

run_root() {
  if need_sudo; then
    sudo "$@"
  else
    "$@"
  fi
}

install_pkg_debian() {
  local pkgs=("$@")
  run_root apt-get update -y
  run_root apt-get install -y "${pkgs[@]}"
}

install_docker_debian() {
  # Prefer distro packages for speed/simplicity.
  install_pkg_debian ca-certificates curl gnupg lsb-release
  if ! have_cmd docker; then
    install_pkg_debian docker.io
    run_root systemctl enable --now docker >/dev/null 2>&1 || true
  fi
  # docker compose v2 plugin (preferred)
  if ! docker compose version >/dev/null 2>&1; then
    install_pkg_debian docker-compose-plugin || true
  fi
  # fallback: docker-compose v1
  if ! docker compose version >/dev/null 2>&1 && ! have_cmd docker-compose; then
    install_pkg_debian docker-compose || true
  fi
}

# Step 1: Check/install system dependencies
echo -e "${YELLOW}[1/10] Checking system dependencies...${NC}"

if ! have_cmd curl; then
  echo "  • Installing curl"
  if have_cmd apt-get; then
    install_pkg_debian curl
  else
    echo -e "${RED}  ✗ Missing curl and no supported package manager detected.${NC}"
    exit 1
  fi
fi

if ! have_cmd python3; then
  echo "  • Installing python3"
  if have_cmd apt-get; then
    install_pkg_debian python3 python3-pip
  else
    echo -e "${RED}  ✗ Python 3 not found. Please install Python 3.8+${NC}"
    exit 1
  fi
fi

if ! have_cmd pip3; then
  echo "  • Installing pip3"
  if have_cmd apt-get; then
    install_pkg_debian python3-pip
  else
    echo -e "${RED}  ✗ pip3 not found. Please install python3-pip${NC}"
    exit 1
  fi
fi

# Docker is optional but recommended (used by docker-compose.yml)
if ! have_cmd docker; then
  echo "  • Docker not found — installing"
  if have_cmd apt-get; then
    install_docker_debian
  else
    echo -e "${RED}  ✗ Docker not found and no supported package manager detected.${NC}"
    echo "    Install Docker manually, then re-run install.sh"
    exit 1
  fi
else
  echo "  ✓ Docker found"
fi

# Docker compose (v2 plugin preferred)
if docker compose version >/dev/null 2>&1; then
  echo "  ✓ docker compose (v2) found"
elif have_cmd docker-compose; then
  echo "  ✓ docker-compose (v1) found"
else
  echo "  • docker compose not found — attempting install"
  if have_cmd apt-get; then
    install_docker_debian
  fi
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "  ✓ Python $PYTHON_VERSION found"

# Step 2: Create directory structure
echo -e "${YELLOW}[2/10] Creating directory structure...${NC}"
mkdir -p "$WORKSPACE_DIR"/{skills/{mem-redis,qdrant-memory,task-queue}/scripts,memory,MEMORY_DEF}
touch "$WORKSPACE_DIR/memory/.gitkeep"
echo "  ✓ Directories created"

# Step 3: Install Python dependencies (PEP 668-safe)
echo -e "${YELLOW}[3/10] Installing Python dependencies...${NC}"
REQ_FILE="$(dirname "$0")/requirements.txt"
PYTHON_BIN="python3"

pip_user_install() {
  if [ -f "$REQ_FILE" ]; then
    pip3 install --user -r "$REQ_FILE"
  else
    pip3 install --user redis qdrant-client requests urllib3
  fi
}

pip_venv_install() {
  local venv_dir="$WORKSPACE_DIR/.venv"
  python3 -m venv "$venv_dir"
  "$venv_dir/bin/pip" install --upgrade pip setuptools wheel >/dev/null 2>&1 || true
  if [ -f "$REQ_FILE" ]; then
    "$venv_dir/bin/pip" install -r "$REQ_FILE"
  else
    "$venv_dir/bin/pip" install redis qdrant-client requests urllib3
  fi
  PYTHON_BIN="$venv_dir/bin/python"
}

# Try user install first (fast path)
if pip_user_install >/dev/null 2>&1; then
  echo "  ✓ Dependencies installed (pip --user)"
else
  echo "  ℹ️  pip --user install blocked (PEP 668). Creating venv in $WORKSPACE_DIR/.venv"
  pip_venv_install
  echo "  ✓ Dependencies installed (venv)"
fi

# Step 4: Test infrastructure connectivity
echo -e "${YELLOW}[4/10] Testing infrastructure...${NC}"

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
echo -e "${YELLOW}[5/10] Creating backups of existing files...${NC}"
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
echo -e "${YELLOW}[6/10] Creating environment configuration...${NC}"
cat > "$WORKSPACE_DIR/.memory_env" <<EOF
# Memory System Environment Variables
export WORKSPACE_DIR="$WORKSPACE_DIR"
export USER_ID="$USER_ID"
export REDIS_HOST="$REDIS_HOST"
export REDIS_PORT="$REDIS_PORT"
export QDRANT_URL="$QDRANT_URL"
export OLLAMA_URL="$OLLAMA_URL"
export MEMORY_PYTHON="$PYTHON_BIN"
export MEMORY_INITIALIZED="true"
EOF
echo "  ✓ Created $WORKSPACE_DIR/.memory_env"

# Step 7: Initialize Qdrant collections
echo -e "${YELLOW}[7/10] Initializing Qdrant collections...${NC}"
if [ "$SKIP_QDRANT_INIT" = "1" ]; then
  echo "  ℹ️  SKIP_QDRANT_INIT=1 set; skipping Qdrant collection init"
else
  "$PYTHON_BIN" <<EOF
import sys
sys.path.insert(0, "$WORKSPACE_DIR/skills/qdrant-memory/scripts")
from init_kimi_memories import init_collection
init_collection()
print("  ✓ kimi_memories collection ready")
EOF
fi

# Step 8: Set up cron jobs
echo -e "${YELLOW}[8/10] Setting up cron jobs...${NC}"
if [ "$SKIP_CRON" = "1" ]; then
  echo "  ℹ️  SKIP_CRON=1 set; skipping crontab modifications"
else
  CRON_FILE=$(mktemp)
  crontab -l 2>/dev/null > "$CRON_FILE" || true

  # Add memory backup cron jobs if not present
  if ! grep -q "cron_backup.py" "$CRON_FILE" 2>/dev/null; then
      echo "" >> "$CRON_FILE"
      echo "# Memory System - Daily backup (3:00 AM)" >> "$CRON_FILE"
      echo "0 3 * * * cd $WORKSPACE_DIR && $PYTHON_BIN skills/mem-redis/scripts/cron_backup.py >> /var/log/memory-backup.log 2>&1 || true" >> "$CRON_FILE"
  fi

  if ! grep -q "sliding_backup.sh" "$CRON_FILE" 2>/dev/null; then
      echo "" >> "$CRON_FILE"
      echo "# Memory System - File backup (3:30 AM)" >> "$CRON_FILE"
      echo "30 3 * * * $WORKSPACE_DIR/skills/qdrant-memory/scripts/sliding_backup.sh >> /var/log/memory-backup.log 2>&1 || true" >> "$CRON_FILE"
  fi

  crontab "$CRON_FILE"
  rm "$CRON_FILE"
  echo "  ✓ Cron jobs configured"
fi

# Step 9: Create HEARTBEAT.md template
echo -e "${YELLOW}[9/10] Creating HEARTBEAT.md...${NC}"
if [ "$SKIP_HEARTBEAT" = "1" ]; then
  echo "  ℹ️  SKIP_HEARTBEAT=1 set; skipping HEARTBEAT.md write"
else
  cat > "$WORKSPACE_DIR/HEARTBEAT.md" <<'EOF'
# HEARTBEAT.md - Memory System Automation

## Memory Buffer (Every Heartbeat)

Saves current session context to Redis buffer:

```bash
python3 ~/.openclaw/workspace/skills/mem-redis/scripts/save_mem.py --user-id YOUR_USER_ID
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
fi

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
echo "  2. Test the system: $PYTHON_BIN $WORKSPACE_DIR/skills/mem-redis/scripts/save_mem.py --user-id $USER_ID"
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
