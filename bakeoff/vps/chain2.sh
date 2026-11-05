#!/usr/bin/env bash
# Second pass: mitigated server/soak runs, then bake-off candidates. Runs ON do6.
set -uo pipefail
cd ~
echo "== start t160 $(date -u +%H:%M:%S)"
( export HELIUM_BIN=~/bin/helium-exp HELIUM_EXP_KOKORO_TOKENS=160 BENCH_TAG=-t160 SOAK_MIN=15
  ./bench.py server; echo "== end server-t160 rc=$?"; ./bench.py soak; echo "== end soak-t160 rc=$?" )
echo "== start swap $(date -u +%H:%M:%S)"
sudo swapoff /swapfile 2>/dev/null; sudo rm -f /swapfile
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap -q /swapfile && sudo swapon /swapfile
free -m | sed -n 3p
( export BENCH_TAG=-swap SOAK_MIN=15
  ./bench.py server; echo "== end server-swap rc=$?"; ./bench.py soak; echo "== end soak-swap rc=$?" )
sudo swapoff /swapfile && sudo rm -f /swapfile
echo "== start cand $(date -u +%H:%M:%S)"
./cand.sh; echo "== end cand rc=$?"
echo "CHAIN2-DONE $(date -u +%H:%M:%S)"
