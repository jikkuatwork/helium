#!/usr/bin/env bash
# Boot the VM as a 1 vCPU / 1 GiB machine (DigitalOcean $6 Basic shape). MODE=off restores.
set -euo pipefail
MEM="${MEM:-1G}"; CPUS="${CPUS:-1}"
f=/etc/default/grub.d/99-do6-shape.cfg
if [ "${MODE:-on}" = off ]; then sudo rm -f "$f"; else
  printf 'GRUB_CMDLINE_LINUX_DEFAULT="$GRUB_CMDLINE_LINUX_DEFAULT mem=%s nr_cpus=%s"\n' "$MEM" "$CPUS" | sudo tee "$f" >/dev/null
fi
sudo update-grub >/dev/null 2>&1
grep -o 'mem=[^ ]* nr_cpus=[^ ]*' /boot/grub/grub.cfg | head -1 || echo "(no limit in grub.cfg)"
sudo systemctl reboot || true
