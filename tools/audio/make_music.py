"""Generate NutriLink's original, royalty-free background music (made from scratch, no samples).

Usage: python3 tools/audio/make_music.py   -> writes tools/audio/track{1,2,3}.m4a (70 s each)
Tracks are committed; render.py picks one per day. Re-running is deterministic.
"""
import pathlib, subprocess, tempfile
import numpy as np

SR = 44100
OUT = pathlib.Path(__file__).resolve().parent
NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}


def hz(name, octave):
    return 440.0 * 2 ** ((NOTE[name] + 12 * (octave + 1) - 69) / 12)


CHORDS = {  # (root, quality)
    1: [("C", "maj"), ("G", "maj"), ("A", "min"), ("F", "maj")],
    2: [("D", "maj"), ("A", "maj"), ("B", "min"), ("G", "maj")],
    3: [("F", "maj"), ("C", "maj"), ("D", "min"), ("A#", "maj")],
}
TEMPO = {1: 96, 2: 100, 3: 92}


def triad(root, q):
    r = NOTE[root]; third = 4 if q == "maj" else 3
    return [r, r + third, r + 7]


def tone(f, dur, kind="pad"):
    t = np.arange(int(dur * SR)) / SR
    if kind == "pad":
        w = np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 1.003 * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t)
        env = np.minimum(1, t / 0.6) * np.minimum(1, (dur - t) / 0.6)
    elif kind == "pluck":
        w = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t) + 0.12 * np.sin(2 * np.pi * 3 * f * t)
        env = np.exp(-t * 6) * np.minimum(1, t / 0.005)
    elif kind == "bass":
        w = np.sin(2 * np.pi * f * t) + 0.2 * np.sin(2 * np.pi * 2 * f * t)
        env = np.minimum(1, t / 0.02) * np.exp(-t * 1.2)
    return w * env


def place(buf, sig, start):
    i = int(start * SR); j = min(len(buf), i + len(sig))
    if j <= i:
        return
    buf[i:j] += sig[: j - i]


def track(n, seconds=70):
    rng = np.random.default_rng(n)
    beat = 60 / TEMPO[n]; bar = 4 * beat
    L = int(seconds * SR)
    pad, arp, bass, perc = (np.zeros(L) for _ in range(4))
    prog = CHORDS[n]
    nbars = int(seconds / bar) + 1
    for b in range(nbars):
        root, q = prog[b % 4]
        notes = triad(root, q)
        t0 = b * bar
        for s in notes:
            place(pad, tone(440 * 2 ** ((s + 48 - 69) / 12) * 1.0, bar + 0.4, "pad"), t0)
        place(bass, tone(440 * 2 ** ((notes[0] + 36 - 69) / 12), bar, "bass"), t0)
        pattern = [0, 1, 2, 1, 0, 2, 1, 2] if n != 2 else [0, 2, 1, 2, 0, 1, 2, 1]
        for k in range(8):
            s = notes[pattern[k]] + 60 + (12 if k in (3, 7) else 0)
            place(arp, tone(440 * 2 ** ((s - 69) / 12), beat * 1.5, "pluck") * (0.9 if k % 2 == 0 else 0.6), t0 + k * beat / 2)
        for k in range(4):  # soft kick on 1 & 3, shaker on off-beats
            if k in (0, 2):
                tk = np.arange(int(0.25 * SR)) / SR
                place(perc, np.sin(2 * np.pi * (50 + 60 * np.exp(-tk * 30)) * tk) * np.exp(-tk * 14) * 0.9, t0 + k * beat)
            ns = rng.standard_normal(int(0.06 * SR)) * np.exp(-np.arange(int(0.06 * SR)) / SR * 70)
            place(perc, np.diff(ns, prepend=0) * 0.18, t0 + k * beat + beat / 2)
    mix = 0.22 * pad / 3 + 0.28 * arp + 0.35 * bass + 0.5 * perc
    # simple stereo reverb/width
    ir = rng.standard_normal(int(1.2 * SR)) * np.exp(-np.arange(int(1.2 * SR)) / SR * 4) * 0.02
    wet_l = np.convolve(mix, ir)[:L]; wet_r = np.convolve(mix, ir[::-1] * 0.9)[:L]
    left, right = mix + wet_l, mix + wet_r
    fade = np.minimum(1, np.arange(L) / (SR * 1.0)) * np.minimum(1, (L - np.arange(L)) / (SR * 2.0))
    st = np.stack([left * fade, right * fade], 1)
    st /= np.abs(st).max() / 0.89
    return st


def main():
    for n in (1, 2, 3):
        st = track(n)
        with tempfile.NamedTemporaryFile(suffix=".raw") as f:
            f.write((st * 32767).astype("<i2").tobytes()); f.flush()
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", str(SR), "-ac", "2", "-i", f.name,
                            "-af", "loudnorm=I=-18:TP=-2:LRA=7", "-ar", str(SR), "-c:a", "aac", "-b:a", "160k", str(OUT / f"track{n}.m4a")], check=True)
        print("wrote", OUT / f"track{n}.m4a")


if __name__ == "__main__":
    main()
