#!/usr/bin/env python3
"""Stress bench for helium on a 1 vCPU / 1 GiB box (DigitalOcean $6 shape).
Stdlib only. Usage: bench.py PHASE   (inputs | cli | server | soak | llm | summary)
Each phase writes ~/bench/<phase>.json."""
import json, os, re, statistics, subprocess, sys, threading, time, urllib.error, urllib.request, uuid, wave

H = os.path.expanduser(os.environ.get("HELIUM_BIN", "~/bin/helium"))
B = os.path.expanduser("~/bench")
IN = os.path.join(B, "inputs")
PORT = 7101
URL = f"http://127.0.0.1:{PORT}"
VOICE = "bella"

TEXTS = {
    "short": "Sure, I set a reminder for nine tomorrow morning.",
    "reply": ("Here is the summary you asked for. The meeting moved to Thursday at three, "
              "Priya will bring the budget numbers, and the venue still needs a deposit by Friday. "
              "Want me to remind you about the deposit on Wednesday evening?"),
    "para": ("The old harbour town wakes slowly. Fishing boats come in before sunrise, and by seven the "
             "market is loud with gulls and traders. Visitors usually arrive by the morning ferry, walk the "
             "sea wall, and stop for coffee at the bakery on the square. In the afternoon the light turns gold "
             "over the cliffs, and the narrow lanes fill with the smell of grilled fish and wood smoke. Most "
             "people leave on the last ferry at six, which is a pity, because the evenings are the best part."),
}
TEXTS["long"] = " ".join([TEXTS["para"], TEXTS["reply"], TEXTS["para"].replace("harbour", "river"),
                          TEXTS["reply"].replace("Thursday", "Monday"), TEXTS["para"].replace("ferry", "train")])
GEN = [TEXTS["para"], TEXTS["reply"], TEXTS["para"].replace("harbour", "mountain"),
       TEXTS["reply"].replace("Priya", "Marcus"), TEXTS["para"].replace("fish", "bread")]

def now(): return time.strftime("%Y-%m-%dT%H:%M:%S")

def meminfo():
    d = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":", 1); d[k] = int(v.split()[0]) // 1024
    return d

def oom_kills():
    with open("/proc/vmstat") as f:
        for line in f:
            if line.startswith("oom_kill "): return int(line.split()[1])
    return -1

def psi_full_total():
    try:
        with open("/proc/pressure/memory") as f:
            for line in f:
                if line.startswith("full"): return int(line.rsplit("total=", 1)[1])
    except OSError: pass
    return -1

def wav_seconds(path):
    with wave.open(path) as w: return w.getnframes() / w.getframerate()

def wav_bytes_seconds(data):
    import io
    with wave.open(io.BytesIO(data)) as w: return w.getnframes() / w.getframerate()

def facts():
    m = meminfo()
    return {"time": now(), "nproc": os.cpu_count(), "mem_total_mib": m["MemTotal"],
            "mem_available_mib": m["MemAvailable"], "swap_total_mib": m["SwapTotal"],
            "uname": os.uname().release}

def timed(cmd, timeout=None, stdin=None):
    t0 = time.monotonic(); ooms0 = oom_kills(); psi0 = psi_full_total()
    try:
        p = subprocess.run(["/usr/bin/time", "-v"] + cmd, capture_output=True, text=True, timeout=timeout, stdin=stdin)
        rc, err, out = p.returncode, p.stderr, p.stdout
    except subprocess.TimeoutExpired as e:
        rc, err, out = "timeout", (e.stderr or b"").decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or ""), ""
    wall = time.monotonic() - t0
    m = re.search(r"Maximum resident set size \(kbytes\): (\d+)", err)
    sig = re.search(r"Command terminated by signal (\d+)", err)
    return {"rc": rc, "signal": int(sig.group(1)) if sig else None, "wall_s": round(wall, 3),
            "peak_rss_mib": round(int(m.group(1)) / 1024, 1) if m else None,
            "oom_kills": oom_kills() - ooms0, "psi_full_us": psi_full_total() - psi0,
            "stdout_head": out[:200], "stderr_tail": "" if rc == 0 else err[-800:]}

def save(phase, obj):
    os.makedirs(B, exist_ok=True)
    phase = phase + os.environ.get("BENCH_TAG", "")
    obj["config"] = {"bin": H, "tag": os.environ.get("BENCH_TAG", ""), "env": {k: v for k, v in os.environ.items() if k.startswith("HELIUM_EXP")}}
    with open(os.path.join(B, phase + ".json"), "w") as f: json.dump(obj, f, indent=1)
    print(f"[bench] wrote {phase}.json", file=sys.stderr)

# ── inputs: STT audio made with helium's own TTS (run at full size) ──────────
def concat_wavs(srcs, dst, seconds):
    frames, params = [], None
    for s in srcs:
        with wave.open(s) as w:
            params = params or w.getparams(); frames.append(w.readframes(w.getnframes()))
    rate, width, ch = params.framerate, params.sampwidth, params.nchannels
    gap = b"\x00" * int(0.4 * rate) * width * ch
    blob = gap.join(frames)
    need = int(seconds * rate) * width * ch
    out = b""
    while len(out) < need: out += blob + gap
    with wave.open(dst, "wb") as w:
        w.setnchannels(ch); w.setsampwidth(width); w.setframerate(rate); w.writeframes(out[:need])

def phase_inputs():
    os.makedirs(IN, exist_ok=True)
    srcs = []
    for i, t in enumerate(GEN):
        p = os.path.join(IN, f"gen{i}.wav")
        if not os.path.exists(p): subprocess.run([H, "tts", "--voice", VOICE, "-o", p, t], check=True, capture_output=True)
        srcs.append(p)
    for name, sec in [("note10", 10), ("note30", 30), ("min1", 60), ("min5", 300), ("min20", 1200)]:
        concat_wavs(srcs, os.path.join(IN, name + ".wav"), sec)
    save("inputs", {"facts": facts(), "files": {n: round(wav_seconds(os.path.join(IN, n + ".wav")), 2)
             for n in ["note10", "note30", "min1", "min5", "min20"]}, "source_s": [round(wav_seconds(s), 2) for s in srcs]})

# ── cli: one process per request (cold every time) ──────────────────────────
def phase_cli():
    res = {"facts": facts(), "tts": [], "stt": []}
    out = os.path.join(B, "cli-out.wav")
    for name, runs in [("short", 3), ("reply", 3), ("para", 3), ("long", 1)]:
        for r in range(runs):
            t = timed([H, "tts", "--voice", VOICE, "-o", out, TEXTS[name]], timeout=1800)
            if t["rc"] == 0: t["audio_s"] = round(wav_seconds(out), 2); t["x_realtime"] = round(t["audio_s"] / t["wall_s"], 3)
            t.update(text=name, words=len(TEXTS[name].split()), run=r); res["tts"].append(t)
            print(f"[cli] tts {name} #{r}: {t.get('x_realtime')}x rt, {t['wall_s']}s, {t['peak_rss_mib']} MiB rc={t['rc']}", file=sys.stderr)
    for name, runs in [("note10", 3), ("min1", 3), ("min5", 1), ("min20", 1)]:
        for r in range(runs):
            f = os.path.join(IN, name + ".wav")
            t = timed([H, "stt", f], timeout=3600)
            t["audio_s"] = round(wav_seconds(f), 2)
            if t["rc"] == 0: t["x_realtime"] = round(t["audio_s"] / t["wall_s"], 3)
            t.update(input=name, run=r); res["stt"].append(t)
            print(f"[cli] stt {name} #{r}: {t.get('x_realtime')}x rt, {t['wall_s']}s, {t['peak_rss_mib']} MiB rc={t['rc']}", file=sys.stderr)
    save("cli", res)

# ── server helpers ───────────────────────────────────────────────────────────
class Server:
    def __init__(self, extra=()):
        self.log = open(os.path.join(B, "serve.log"), "a")
        self.p = subprocess.Popen([H, "serve", "--port", str(PORT), *extra], stdout=self.log, stderr=self.log)
        self.samples, self._stop = [], False
        for _ in range(120):
            try:
                urllib.request.urlopen(URL + "/v1/status", timeout=2).read(); break
            except Exception: time.sleep(0.5)
        self.t = threading.Thread(target=self._sample, daemon=True); self.t.start()
    def rss(self):
        try:
            with open(f"/proc/{self.p.pid}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"): return int(line.split()[1]) // 1024
        except OSError: return None
    def _sample(self):
        t0 = time.monotonic()
        while not self._stop:
            m = meminfo()
            self.samples.append((round(time.monotonic() - t0, 2), self.rss(), m["MemAvailable"], m["SwapTotal"] - m["SwapFree"]))
            time.sleep(0.25)
    def alive(self): return self.p.poll() is None
    def stop(self):
        self._stop = True; self.t.join(2)
        if self.alive(): self.p.terminate(); self.p.wait(20)
        return {"exit": self.p.returncode, "rss_max_mib": max([s[1] for s in self.samples if s[1]] or [0]),
                "mem_available_min_mib": min([s[2] for s in self.samples] or [0]),
                "swap_used_max_mib": max([s[3] for s in self.samples] or [0]),
                "timeline": self.samples[::4]}

def post(path, body, ctype, timeout=900):
    req = urllib.request.Request(URL + path, data=body, headers={"Content-Type": ctype}, method="POST")
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: data, code = r.read(), r.status
    except urllib.error.HTTPError as e: data, code = e.read(), e.code
    except Exception as e: data, code = str(e).encode(), "error"
    return code, data, round(time.monotonic() - t0, 3)

def tts_req(text):
    code, data, lat = post("/v1/audio/speech", json.dumps({"input": text, "voice": VOICE}).encode(), "application/json")
    audio = wav_bytes_seconds(data) if code == 200 else 0
    return {"code": code, "latency_s": lat, "audio_s": round(audio, 2), "err": "" if code == 200 else data[:200].decode(errors="replace")}

def stt_req(name):
    f = os.path.join(IN, name + ".wav"); bnd = uuid.uuid4().hex
    with open(f, "rb") as fh: audio = fh.read()
    body = (f"--{bnd}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}.wav\"\r\n"
            f"Content-Type: audio/wav\r\n\r\n").encode() + audio + f"\r\n--{bnd}--\r\n".encode()
    code, data, lat = post("/v1/audio/transcriptions", body, f"multipart/form-data; boundary={bnd}")
    return {"code": code, "latency_s": lat, "audio_s": round(wav_seconds(f), 2),
            "text_len": len(data) if code == 200 else 0, "err": "" if code == 200 else data[:200].decode(errors="replace")}

def burst(fn, arg, n, conc):
    results, lock, idx = [], threading.Lock(), [0]
    def worker():
        while True:
            with lock:
                if idx[0] >= n: return
                idx[0] += 1
            r = fn(arg)
            with lock: results.append(r)
    t0 = time.monotonic()
    ts = [threading.Thread(target=worker) for _ in range(conc)]
    [t.start() for t in ts]; [t.join() for t in ts]
    wall = time.monotonic() - t0
    ok = [r for r in results if r["code"] == 200]; lats = sorted(r["latency_s"] for r in ok)
    codes = {}
    for r in results: codes[str(r["code"])] = codes.get(str(r["code"]), 0) + 1
    return {"n": n, "concurrency": conc, "wall_s": round(wall, 2), "codes": codes,
            "p50_s": round(statistics.median(lats), 2) if lats else None,
            "p95_s": round(lats[min(len(lats) - 1, int(0.95 * len(lats)))], 2) if lats else None,
            "max_s": round(lats[-1], 2) if lats else None,
            "audio_per_wall": round(sum(r["audio_s"] for r in ok) / wall, 3) if ok else 0}

def phase_server():
    res = {"facts": facts(), "ooms_before": oom_kills()}
    s = Server(); time.sleep(3); res["idle_rss_mib"] = s.rss()
    res["tts_seq"] = [tts_req(TEXTS["reply"]) for _ in range(5)]
    res["rss_after_tts_mib"] = s.rss()
    res["stt_seq"] = [stt_req("note10") for _ in range(5)]
    res["rss_after_tts_stt_mib"] = s.rss()
    res["tts_burst"] = [burst(tts_req, TEXTS["short"], 8, c) for c in (1, 2, 4, 8)]
    res["stt_burst"] = [burst(stt_req, "note10", 8, c) for c in (1, 2, 4, 8)]
    cyc = []
    for i in range(5):
        a = stt_req("note10"); b = tts_req(TEXTS["reply"])
        cyc.append({"stt_s": a["latency_s"], "tts_s": b["latency_s"], "reply_audio_s": b["audio_s"], "codes": [a["code"], b["code"]]})
    res["assistant_cycles"] = cyc
    res["stt_long"] = [stt_req("min5")]
    res["server"] = s.stop(); res["ooms_after"] = oom_kills()
    save("server", res)

def phase_soak(minutes=int(os.environ.get("SOAK_MIN", "20")), period=30):
    res = {"facts": facts(), "ooms_before": oom_kills(), "minutes": minutes, "period_s": period, "cycles": []}
    s = Server(); t_end = time.monotonic() + minutes * 60
    while time.monotonic() < t_end and s.alive():
        t0 = time.monotonic()
        a = stt_req("note10"); b = tts_req(TEXTS["reply"])
        res["cycles"].append({"t": round(t0 - (t_end - minutes * 60), 1), "stt_s": a["latency_s"], "tts_s": b["latency_s"],
                              "codes": [a["code"], b["code"]], "rss_mib": s.rss(), "avail_mib": meminfo()["MemAvailable"]})
        time.sleep(max(0, period - (time.monotonic() - t0)))
    res["server"] = s.stop(); res["ooms_after"] = oom_kills()
    save("soak", res)

def phase_llm():
    res = {"facts": facts(), "runs": []}
    prompt = "Answer in one short sentence: what is two plus two?"
    t = timed([H, "llm", "--max-tokens", "16", prompt], timeout=600); t["variant"] = "no swap"; res["runs"].append(t)
    print(f"[llm] no swap: rc={t['rc']} sig={t['signal']} {t['wall_s']}s rss={t['peak_rss_mib']} ooms={t['oom_kills']}", file=sys.stderr)
    save("llm", res)

def phase_summary():
    for ph in ["inputs", "cli", "server", "soak", "llm"]:
        p = os.path.join(B, ph + ".json")
        print(f"== {ph}: {'present' if os.path.exists(p) else 'missing'}")

if __name__ == "__main__":
    {"inputs": phase_inputs, "cli": phase_cli, "server": phase_server, "soak": phase_soak,
     "llm": phase_llm, "summary": phase_summary}[sys.argv[1]]()
