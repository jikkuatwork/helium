#!/usr/bin/env bash
#
# hvm-host-init.sh — runs ON the remote host (via `scripts/hvm init`).
# Idempotent. Brings a fresh Ubuntu VM to toolchain parity with the operator:
# mise (ruby/node/go at the operator's versions), pi, harnex, pi-config.
#
# Inputs (env): PI_VERSION HARNEX_VERSION RUBY_VERSION_WANT NODE_VERSION_WANT
#               GO_VERSION_WANT GIT_NAME GIT_EMAIL

set -euo pipefail
say() { printf '\033[1;36m[host]\033[0m %s\n' "$*" >&2; }

say "waiting for cloud-init / apt…"
cloud-init status --wait >/dev/null 2>&1 || true
while sudo fuser /var/lib/dpkg/lock-frontend /var/lib/apt/lists/lock >/dev/null 2>&1; do sleep 3; done

say "base packages"
sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  build-essential git tmux jq curl unzip rsync python3-venv python3-pip pkg-config \
  autoconf bison libssl-dev libyaml-dev zlib1g-dev libffi-dev libreadline-dev \
  libgdbm-dev libncurses-dev >/dev/null

# PATH + secrets must load for non-interactive ssh commands too, so they go
# above Ubuntu's "not interactive → return" guard in ~/.bashrc.
if ! grep -q '# hvm:begin' ~/.bashrc; then
  say "shell profile (PATH, mise shims, key file)"
  tmp="$(mktemp)"
  cat > "$tmp" <<'EOF'
# hvm:begin — loaded for interactive AND non-interactive (ssh CMD) shells
export PATH="$HOME/.local/share/mise/shims:$HOME/.local/bin:$PATH"
[ -f "$HOME/.config/hvm/env" ] && . "$HOME/.config/hvm/env"
# hvm:end
EOF
  cat ~/.bashrc >> "$tmp"; mv "$tmp" ~/.bashrc
fi
export PATH="$HOME/.local/share/mise/shims:$HOME/.local/bin:$PATH"

if ! command -v mise >/dev/null 2>&1; then
  say "installing mise"
  curl -fsSL https://mise.run | sh >/dev/null
fi

say "toolchain: ruby $RUBY_VERSION_WANT · node $NODE_VERSION_WANT · go $GO_VERSION_WANT"
cat > ~/.tool-versions <<EOF
ruby $RUBY_VERSION_WANT
nodejs $NODE_VERSION_WANT
golang $GO_VERSION_WANT
EOF
MAKE_OPTS="-j$(nproc)" mise install --yes >/dev/null
mise reshim

if [ "$(pi --version 2>/dev/null | tail -1)" != "$PI_VERSION" ]; then
  say "pi $PI_VERSION"
  npm install -g --ignore-scripts --silent "@earendil-works/pi-coding-agent@$PI_VERSION" >/dev/null
  mise reshim
fi

if ! harnex --version 2>/dev/null | grep -q " $HARNEX_VERSION "; then
  say "harnex $HARNEX_VERSION"
  gem install --no-document harnex -v "$HARNEX_VERSION" >/dev/null
  mise reshim
fi

if [ -x ~/src/pi-config/install.sh ]; then
  say "pi-config sync"
  (cd ~/src/pi-config && ./install.sh --sync >/dev/null)
fi

git config --global init.defaultBranch main
[ -n "${GIT_NAME:-}" ] && git config --global user.name "$GIT_NAME"
[ -n "${GIT_EMAIL:-}" ] && git config --global user.email "$GIT_EMAIL"

mkdir -p ~/work ~/.config/hvm; chmod 700 ~/.config/hvm
[ -f ~/.config/hvm/env ] || { : > ~/.config/hvm/env; chmod 600 ~/.config/hvm/env; }

say "versions: pi $(pi --version 2>/dev/null | tail -1) · $(harnex --version) · $(ruby -v | cut -d' ' -f1-2) · node $(node -v) · $(go version | cut -d' ' -f3)"
say "cores $(nproc) · mem $(free -g | awk '/Mem:/{print $2}') GB · disk $(df -h ~ | awk 'NR==2{print $4}') free"
