#!/usr/bin/env bash
# One-time setup on a fresh Ubuntu 24.04 server. Run as root:
#   curl -fsSL https://raw.githubusercontent.com/louiseivan/seo-content-machine-via-claude-by-louise/main/ryder-shopify-autopilot/deploy/setup.sh | bash
# Installs Python, cairo, Node and Claude Code; creates the `ryder` user;
# clones the repo; sets the clock to Asia/Tokyo. Installs no credentials
# and no crontab (see DEPLOY.md for those steps).
set -euo pipefail
REPO="https://github.com/louiseivan/seo-content-machine-via-claude-by-louise.git"

timedatectl set-timezone Asia/Tokyo

# Small droplets (1-2 GB RAM): add 2 GB swap so Claude Code + image
# generation don't run out of memory.
if [ "$(awk '/MemTotal/{print $2}' /proc/meminfo)" -lt 3000000 ] && ! swapon --show | grep -q .; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -yq \
  git curl rsync cron python3 python3-pip python3-venv \
  libcairo2 libpango-1.0-0 fonts-dejavu-core ca-certificates
pip3 install --break-system-packages -q Pillow cairosvg markdown google-auth requests

# Node 22 LTS + Claude Code
if ! command -v node >/dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -yq nodejs
fi
npm install -g @anthropic-ai/claude-code

id ryder >/dev/null 2>&1 || useradd -m -s /bin/bash ryder
if [ -d /root/.ssh ] && [ ! -d /home/ryder/.ssh ]; then
  cp -r /root/.ssh /home/ryder/.ssh && chown -R ryder:ryder /home/ryder/.ssh
fi
sudo -u ryder bash -c "[ -d ~/CodingStudio/.git ] || git clone -q $REPO ~/CodingStudio"
sudo -u ryder bash -c "chmod +x ~/CodingStudio/ryder-shopify-autopilot/deploy/*.sh"
systemctl enable --now cron
echo "setup done. Next: DEPLOY.md step 3 (copy secrets and drafts from the Mac)."
