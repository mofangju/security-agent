#!/usr/bin/env bash
# Fix SafeLine tengine for WSL2 — switch from host network to bridge mode
# Usage: sudo bash scripts/fix_tengine_wsl.sh
set -euo pipefail

COMPOSE="/data/safeline/compose.yaml"

if [ ! -f "$COMPOSE" ]; then
  echo "❌ SafeLine compose.yaml not found at $COMPOSE"
  exit 1
fi

echo "📋 Backing up compose.yaml..."
cp "$COMPOSE" "${COMPOSE}.bak"

echo "🔧 Patching tengine: host → bridge network mode..."

# Use python for reliable YAML editing
python3 << 'PYEOF'
import re

with open("/data/safeline/compose.yaml") as f:
    content = f.read()

# 1. Remove network_mode: host from tengine
content = content.replace("    network_mode: host\n", "")

# 2. Update ports from 80:80 to 8888:8888
content = content.replace('      - "80:80"', '      - "8888:8888"')

# 3. Add networks block after ulimits block in tengine
# Find the tengine ulimits section and add networks after it
content = content.replace(
    "    ulimits:\n      nofile: 131072\n  luigi:",
    "    ulimits:\n      nofile: 131072\n    networks:\n      safeline-ce:\n        ipv4_address: ${SUBNET_PREFIX}.6\n  luigi:"
)

with open("/data/safeline/compose.yaml", "w") as f:
    f.write(content)

print("✅ compose.yaml patched successfully")
PYEOF

echo ""
echo "🔄 Restarting SafeLine..."
cd /data/safeline
docker compose down tengine 2>/dev/null || true
docker compose up -d

echo ""
echo "⏳ Waiting for services to start..."
sleep 5

echo ""
echo "📡 Checking ports..."
ss -tlnp | grep -E ":8888|:9443|:8080" || echo "⚠️  Port 8888 not detected yet, wait a few more seconds"

echo ""
echo "✅ Done! Test with: curl -s http://localhost:8888/ -H 'Host: petshop.local'"
