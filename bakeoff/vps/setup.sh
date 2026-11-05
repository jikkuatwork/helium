#!/usr/bin/env bash
# Runs ON the do6 VM at full size (2 vCPU / 8 GiB), before the 1 vCPU / 1 GiB limit.
set -euo pipefail
say() { printf '[setup] %s\n' "$*" >&2; }
say "waiting for cloud-init / apt"
cloud-init status --wait >/dev/null 2>&1 || true
while sudo fuser /var/lib/dpkg/lock-frontend /var/lib/apt/lists/lock >/dev/null 2>&1; do sleep 3; done
sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq build-essential git jq time curl python3 >/dev/null
if ! ~/go-sdk/bin/go version 2>/dev/null | grep -q go1.25.1; then
  say "Go 1.25.1"
  curl -fsSL https://go.dev/dl/go1.25.1.linux-amd64.tar.gz -o /tmp/go.tgz
  rm -rf ~/go-sdk && mkdir -p ~/go-sdk && tar -C ~/go-sdk --strip-components=1 -xzf /tmp/go.tgz && rm /tmp/go.tgz
fi
export PATH="$HOME/go-sdk/bin:$PATH"
mkdir -p ~/bin ~/bench
say "build helium"
(cd ~/work/helium && go build -o ~/bin/helium ./cmd/helium)
~/bin/helium version
say "download tts, stt, llm (from cattery-artefacts)"
~/bin/helium download        >  ~/bench/download.log 2>&1
~/bin/helium download stt    >> ~/bench/download.log 2>&1
~/bin/helium download llm    >> ~/bench/download.log 2>&1
tail -5 ~/bench/download.log
say "facts"
{
  echo "## lscpu"; lscpu | grep -E 'Model name|^CPU\(s\)|Thread|Flags' | sed 's/Flags:.*/&/' | cut -c1-400
  echo "## avx flags"; grep -o -w 'avx2\|avx512f\|avx512_vnni\|avx_vnni\|fma' /proc/cpuinfo | sort | uniq -c
  echo "## disk"; df -h / | tail -1
  echo "## artefacts"; du -sh ~/.helium 2>/dev/null; du -sh ~/.helium/* 2>/dev/null
  echo "## helium status"; ~/bin/helium status 2>&1 | head -30
} > ~/bench/facts.txt 2>&1
say "disk read throughput (uncached, 1 GiB)"
dd if=/dev/zero of=/tmp/ddtest bs=1M count=1024 oflag=direct status=none
sync; echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null
dd if=/tmp/ddtest of=/dev/null bs=1M iflag=direct 2>&1 | tail -1 | tee -a ~/bench/facts.txt
rm -f /tmp/ddtest
say "done"
