"""Transcribe Telugu narration with Whisper (sherpa-onnx, offline) and score it against the script."""
import difflib, os, re, subprocess, tempfile, wave
import numpy as np

ASR_DIR = os.environ.get("ASR_DIR", "/opt/asr/sherpa-onnx-whisper-turbo")
_rec = None


def _load():
    global _rec
    if _rec is None:
        import sherpa_onnx
        _rec = sherpa_onnx.OfflineRecognizer.from_whisper(
            encoder=f"{ASR_DIR}/turbo-encoder.int8.onnx", decoder=f"{ASR_DIR}/turbo-decoder.int8.onnx",
            tokens=f"{ASR_DIR}/turbo-tokens.txt", language="te", task="transcribe", num_threads=4)
    return _rec


def transcribe(path):
    with tempfile.NamedTemporaryFile(suffix=".wav") as t:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", "16000", t.name], check=True)
        with wave.open(t.name) as w:
            x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    r = _load(); s = r.create_stream(); s.accept_waveform(16000, x); r.decode_stream(s)
    return s.result.text.strip()


def norm(t):
    t = t.replace("‌", "")
    t = re.sub(r"[^ఀ-౿]", "", t)          # Telugu letters only
    return re.sub(r"[ా-్ంః]", "", t)  # compare base consonants/vowels (ASR often slips on vowel signs)


def similarity(expected, heard):
    return difflib.SequenceMatcher(None, norm(expected), norm(heard)).ratio()
