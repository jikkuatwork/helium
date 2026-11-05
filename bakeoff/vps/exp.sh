#!/usr/bin/env bash
# Throwaway Kokoro memory experiment on the 1 vCPU / 1 GiB box. Never committed.
set -uo pipefail
export PATH="$HOME/go-sdk/bin:$PATH"
OUT=~/bench/exp; mkdir -p "$OUT"
if [ ! -x ~/bin/helium-exp ]; then
  rm -rf ~/exp-src && mkdir -p ~/exp-src && git -C ~/work/helium archive HEAD | tar -x -C ~/exp-src
  python3 ~/exp_patch.py ~/exp-src
  (cd ~/exp-src && GOFLAGS=-p=1 go build -o ~/bin/helium-exp ./cmd/helium) || { echo "[exp] build failed"; exit 1; }
fi
PARA=$(python3 -c 'import sys; sys.path.insert(0, "."); import importlib.util as u; s=u.spec_from_file_location("b", "'$HOME'/bench.py"); m=u.module_from_spec(s); s.loader.exec_module(m); print(m.TEXTS["para"])')
LONG=$(python3 -c 'import importlib.util as u; s=u.spec_from_file_location("b", "'$HOME'/bench.py"); m=u.module_from_spec(s); s.loader.exec_module(m); print(m.TEXTS["long"])')
REPLY=$(python3 -c 'import importlib.util as u; s=u.spec_from_file_location("b", "'$HOME'/bench.py"); m=u.module_from_spec(s); s.loader.exec_module(m); print(m.TEXTS["reply"])')
run() { # label tokens arena text-name text
  local label=$1 tok=$2 arena=$3 tname=$4 text=$5 f="$OUT/$1-$4"
  /usr/bin/time -v -o "$f.time" env HELIUM_EXP_KOKORO_TOKENS="$tok" HELIUM_EXP_NO_ARENA="$arena" \
    ~/bin/helium-exp tts --voice bella -o "$f.wav" "$text" > "$f.log" 2>&1
  local rc=$? rss wall audio
  rss=$(grep -o 'Maximum resident set size (kbytes): [0-9]*' "$f.time" | grep -o '[0-9]*$')
  wall=$(grep 'Elapsed (wall clock)' "$f.time" | awk '{print $NF}')
  audio=$(python3 -c "import wave; w=wave.open('$f.wav'); print(round(w.getnframes()/w.getframerate(),2))" 2>/dev/null || echo 0)
  echo "[exp] $label $tname tokens=$tok no_arena=$arena rc=$rc rss=$((rss/1024))MiB wall=$wall audio=${audio}s"
}
for cfg in "base 480 0" "noarena 480 1" "t240 240 0" "t160 160 0" "t160na 160 1" "t100 100 0"; do
  set -- $cfg
  run "$1" "$2" "$3" para "$PARA"
done
for cfg in "t160 160 0" "t160na 160 1"; do set -- $cfg; run "$1" "$2" "$3" long "$LONG"; run "$1" "$2" "$3" reply "$REPLY"; done
echo "[exp] EXP-DONE"
