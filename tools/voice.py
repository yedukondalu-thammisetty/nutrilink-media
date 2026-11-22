"""Telugu voice-over for NutriLink shorts.

Voice: AI4Bharat Indic-TTS (IIT Madras) Telugu FastPitch + HiFiGAN, open model.
Setup (once per machine, ~5 min):  bash tools/setup_voice.sh
"""
import json, os, pathlib, re

MODEL_DIR = pathlib.Path(os.environ.get("INDICTTS_DIR", "/opt/indictts/te"))
VOICE = "female"   # LOCKED brand voice (soft female Telugu voice, chosen 2026-11-22)

# ---------------- LOCKED BRAND LINES (spoken) ----------------
BRAND_OUTRO_TE = ("ఇది న్యూట్రిలింక్ బై న్యూట్రిగ్లో. "
                  "రోజూ ఆరోగ్య చిట్కాల కోసం, మా ఛానెల్‌ని సబ్‌స్క్రైబ్ చేయండి.")
CONTACT_TE = "వెల్‌నెస్ కోచ్ వెంకటేశ్వర్లు గారికి కాల్ చేయండి."
# --------------------------------------------------------------

ONES = ["సున్నా", "ఒకటి", "రెండు", "మూడు", "నాలుగు", "ఐదు", "ఆరు", "ఏడు", "ఎనిమిది", "తొమ్మిది", "పది",
        "పదకొండు", "పన్నెండు", "పదమూడు", "పద్నాలుగు", "పదిహేను", "పదహారు", "పదిహేడు", "పద్దెనిమిది", "పందొమ్మిది"]
TENS = {20: "ఇరవై", 30: "ముప్పై", 40: "నలభై", 50: "యాభై", 60: "అరవై", 70: "డెబ్బై", 80: "ఎనభై", 90: "తొంభై"}


def num_te(n):
    if n < 20:
        return ONES[n]
    if n < 100:
        t, o = divmod(n, 10)
        return TENS[t * 10] + ("" if o == 0 else " " + ONES[o])
    if n == 100:
        return "వంద"
    if n < 1000:
        h, r = divmod(n, 100)
        head = "వంద" if h == 1 else ONES[h] + " వందల"
        return head + ("" if r == 0 else " " + num_te(r))
    return str(n)


def speakable(text):
    """Make on-screen Telugu text speakable by the model (numbers to words, drop symbols it can't read)."""
    t = re.sub(r"(\d+)\s*[–-]\s*(\d+)", lambda m: f"{num_te(int(m.group(1)))} నుండి {num_te(int(m.group(2)))}", text)
    t = re.sub(r"\d+", lambda m: num_te(int(m.group(0))), t)
    t = t.replace("‌", "").replace("–", ", ").replace("—", ", ").replace("%", " శాతం")
    t = re.sub(r"[^ఀ-౿\s!',.:;?]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if t and t[-1] not in ".!?":
        t += "."
    return t


def script(c):
    """Narration segments, one per video stage: title, [answer,] tip1..3, CTA+contact, brand outro."""
    segs = [c.get("say_title_te") or c["title_te"]]
    if "answer_te" in c:   # conversation-style short: the coach answers the question
        segs.append("నా సలహా, " + (c.get("say_answer_te") or c["answer_te"]))
    ordinal = ["మొదటిది", "రెండవది", "మూడవది", "నాలుగవది"]
    for i, t in enumerate(c["tips"]):
        segs.append(f"{ordinal[i]}, " + (t.get("say_te") or t["te"]))
    segs.append((c.get("say_cta_te") or c["cta_te"]).rstrip(".!") + ". " + CONTACT_TE)
    segs.append(BRAND_OUTRO_TE)
    return [speakable(s) for s in segs]


def phrases(text):
    """Split a segment into short phrases (sentences; long sentences split at commas)."""
    L = lambda t: len(re.sub(r"[^\u0C00-\u0C7F]", "", t))
    out = []
    for sent in [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]:
        if L(sent) <= 30:
            out.append(sent); continue
        cur = ""
        for part in [p.strip() for p in re.split(r"(?<=,)\s+", sent) if p.strip()]:
            cur = (cur + " " + part).strip() if cur and L(cur) < 10 else (out.append(cur) or part) if cur else part
        if cur:
            out.append(cur)
    return out


_synth = None


def _load():
    global _synth
    if _synth is None:
        from TTS.utils.synthesizer import Synthesizer
        cfg = json.load(open(MODEL_DIR / "fastpitch" / "config.json"))
        spk = str(MODEL_DIR / "fastpitch" / "speakers.pth")
        cfg["speakers_file"] = spk
        cfg.setdefault("model_args", {})["speakers_file"] = spk
        fixed = MODEL_DIR / "fastpitch" / "config.fixed.json"
        json.dump(cfg, open(fixed, "w"))
        _synth = Synthesizer(tts_checkpoint=str(MODEL_DIR / "fastpitch" / "best_model.pth"), tts_config_path=str(fixed),
                             tts_speakers_file=spk, vocoder_checkpoint=str(MODEL_DIR / "hifigan" / "best_model.pth"),
                             vocoder_config=str(MODEL_DIR / "hifigan" / "config.json"), use_cuda=False)
    return _synth


SPEED = 1.35   # LOCKED: >1 = slower, calmer delivery (chosen 2026-11-22)
# LOCKED smoothing: gentle EQ, de-essing, light compression and a small room so the voice sounds softer
SMOOTH = ("highpass=f=80,lowpass=f=6500,deesser=i=0.5,"
          "acompressor=threshold=-22dB:ratio=2.5:attack=15:release=250:makeup=2,"
          "equalizer=f=250:t=q:w=1.2:g=2.5,equalizer=f=4000:t=q:w=1.5:g=-4")


def synth(text, path):
    import subprocess
    s = _load()
    s.tts_model.length_scale = SPEED
    wav = s.tts(text, speaker_name=VOICE)
    raw = str(path) + ".raw.wav"
    s.save_wav(wav, raw)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", SMOOTH, str(path)], check=True)
    os.remove(raw)
    return len(wav) / s.output_sample_rate
