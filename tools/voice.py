"""Telugu voice-over for NutriLink shorts.

Voice: AI4Bharat Indic-TTS (IIT Madras) Telugu FastPitch + HiFiGAN speaks the words, then kNN-VC
(WavLM + HiFiGAN, voice conversion) turns it into the owner-approved brand voice, copied from the
reference recording in tools/audio/voice_ref/ (approved 2026-11-25).
Setup (once per machine, ~10 min):  bash tools/setup_voice.sh
"""
import json, os, pathlib, re

MODEL_DIR = pathlib.Path(os.environ.get("INDICTTS_DIR", "/opt/indictts/te"))
VOICE = "male"   # LOCKED base speaker for the brand voice (owner-approved voice copy, 2026-11-25)
REF_DIR = pathlib.Path(__file__).parent / "audio" / "voice_ref"   # LOCKED reference recording
KNNVC_DIR = pathlib.Path(os.environ.get("KNNVC_DIR", "/opt/knnvc"))

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


SPEED = 1.12   # LOCKED: >1 = slower; owner asked for slightly faster than the approved 1.15 test (2026-11-25)
# LOCKED smoothing for the brand voice: rumble cut, gentle top, light compression
SMOOTH = ("highpass=f=70,lowpass=f=7000,"
          "acompressor=threshold=-22dB:ratio=2:attack=15:release=250:makeup=2")

_vc = None


def _load_vc():
    """kNN-VC model plus the matching set built once from the reference recording."""
    global _vc
    if _vc is None:
        import sys, torch
        sys.path.insert(0, str(KNNVC_DIR / "code"))
        ck = KNNVC_DIR / "hub" / "checkpoints"; ck.mkdir(parents=True, exist_ok=True)
        for f in ("WavLM-Large.pt", "prematch_g_02500000.pt"):
            if not (ck / f).exists():
                (ck / f).symlink_to(KNNVC_DIR / f)
        torch.hub.set_dir(str(KNNVC_DIR / "hub"))
        from hubconf import knn_vc
        m = knn_vc(pretrained=True, progress=False, prematched=True, device="cpu")
        refs = sorted(str(p) for p in REF_DIR.glob("*.flac"))
        _vc = (m, m.get_matching_set(refs))
    return _vc


def convert(src, dst):
    """Turn a 16 kHz mono wav into the brand voice."""
    import torchaudio
    m, ms = _load_vc()
    w = m.match(m.get_features(str(src)), ms, topk=4)
    torchaudio.save(str(dst), w[None], 16000)


CACHE_DIR = pathlib.Path(__file__).parent / "audio" / "voice_cache"   # pre-checked recordings of the fixed brand lines


def cache_key(text):
    import hashlib
    return hashlib.sha256(f"{VOICE}|{SPEED}|{text}".encode()).hexdigest()[:16]


def synth(text, path):
    import subprocess, shutil, wave
    hit = CACHE_DIR / (cache_key(text) + ".wav")
    if hit.exists():   # fixed brand line: reuse the recording that already passed the speech check
        shutil.copy(hit, path)
        with wave.open(str(hit)) as w:
            return w.getnframes() / w.getframerate()
    s = _load()
    s.tts_model.length_scale = SPEED
    wav = s.tts(text, speaker_name=VOICE)
    raw = str(path) + ".raw.wav"; r16 = str(path) + ".16k.wav"; vc = str(path) + ".vc.wav"
    s.save_wav(wav, raw)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-ac", "1", "-ar", "16000", r16], check=True)
    convert(r16, vc)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", vc, "-af", SMOOTH, "-ar", "22050", str(path)], check=True)
    for f in (raw, r16, vc):
        os.remove(f)
    return len(wav) / s.output_sample_rate
