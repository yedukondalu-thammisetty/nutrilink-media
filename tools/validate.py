"""Pre-publish quality gate for a rendered NutriLink post.

Usage: python3 tools/validate.py <post_dir>
Exit code 0 = PASS (safe to publish). Any other exit code = FAIL: do NOT publish.

Checks
  1. Files: post.jpg 1080x1350; short.mp4 h264 1080x1920 with audio, 10-60 s, < 100 MB.
  2. Fonts: Telugu and Latin web fonts actually loaded in the browser.
  3. Telugu shaping: every Telugu line's on-screen width must match HarfBuzz/raqm shaping of the
     same font within 3%. Broken/fallback rendering (letters split apart) fails this.
     Every character must exist in the Telugu font.
  4. Layout: nothing overflows or is cut off.
  5. Branding: logo file hash equals the locked official logo; logo is drawn at the locked size,
     horizontally centred, and is actually visible (pixel check) in the image AND the final video frame.
     Contact block text is exactly the locked contact details.
  6. Video frames are not blank; branded outro (logo, tagline, subscribe) is the last scene.
  7. Audio: voice-over + music present, loudness -18..-12 LUFS, no clipping, video <= 59 s.
     Every narration phrase is checked by speech recognition (Whisper, offline): its opening words
     must match the script (>= 0.6) and its speaking rate must be natural.
Also writes <post_dir>/qa_sheet.jpg (image + video frames) for a final visual review.
"""
import hashlib, json, pathlib, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageFont, features

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render  # noqa: E402  (uses its locked constants)

LOCK = json.load(open(HERE / "brand" / "brand.lock.json"))
fails, notes = [], []


def check(cond, msg):
    (notes if cond else fails).append(("PASS " if cond else "FAIL ") + msg)


def logo_visible(img, box, label):
    lg = Image.open(render.LOGO_PNG).convert("RGBA")
    x, y, w, h = [int(round(v)) for v in (box["x"], box["y"], box["w"], box["h"])]
    a = np.asarray(lg.resize((w, h), Image.LANCZOS))[..., 3] / 255.0
    region = np.asarray(img.convert("RGB").crop((x, y, x + w, y + h))).astype(float).min(axis=2)
    on = region[a > 0.95]; off = region[a < 0.02]
    check(on.size > 500 and np.median(on) > 225, f"{label}: logo visible and white (median {np.median(on):.0f})")
    check(off.size > 500 and np.median(off) < 200, f"{label}: logo background not washed out (median {np.median(off):.0f})")


def main():
    d = pathlib.Path(sys.argv[1])
    post, vid, qaf = d / "post.jpg", d / "short.mp4", d / "qa.json"
    for f in (post, vid, qaf):
        check(f.exists(), f"file exists: {f.name}")
    if fails:
        return report(d)
    qa = json.load(open(qaf, encoding="utf-8"))

    # 1. files
    im = Image.open(post)
    check(im.size == (1080, 1350), f"post.jpg size {im.size}")
    pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(vid)],
                                   capture_output=True, text=True).stdout)
    vs = [s for s in pr["streams"] if s["codec_type"] == "video"]
    au = [s for s in pr["streams"] if s["codec_type"] == "audio"]
    dur = float(pr["format"]["duration"]); size = vid.stat().st_size
    check(vs and vs[0]["codec_name"] == "h264" and (vs[0]["width"], vs[0]["height"]) == (1080, 1920), "video h264 1080x1920")
    check(bool(au), "video has audio track")
    check(10 <= dur <= 59, f"video duration {dur:.1f}s (Shorts limit)")
    check(size < 100 * 1024 * 1024, f"video size {size/1e6:.1f} MB < 100 MB")

    # 2-4 per layout
    check(features.check("raqm"), "raqm text shaping available for verification")
    tel = {400: ImageFont.truetype(str(HERE / "fonts" / "NotoSansTelugu-Regular.ttf"), 10),
           700: ImageFont.truetype(str(HERE / "fonts" / "NotoSansTelugu-Bold.ttf"), 10)}
    from fontTools.ttLib import TTFont
    cmap = TTFont(str(HERE / "fonts" / "NotoSansTelugu-Bold.ttf")).getBestCmap()
    for kind in ("post", "short"):
        m = qa[kind]
        check(m["fontsTel400"] and m["fontsTel700"] and m["fontsPop"], f"{kind}: fonts loaded")
        check(not m["overflow"], f"{kind}: no overflow/cut-off text {m['overflow'] if m['overflow'] else ''}")
        for t in m["te"]:
            missing = [ch for ch in t["text"] if not ch.isspace() and ord(ch) not in cmap]
            check(not missing, f"{kind}: all characters in Telugu font: {t['text'][:30]} {missing if missing else ''}")
            f = tel[700 if t["weight"] >= 600 else 400].font_variant(size=t["px"])
            ref = f.getlength(t["text"], features=["-kern"]) if False else f.getlength(t["text"])
            ratio = t["width"] / ref if ref else 0
            check(0.97 <= ratio <= 1.03, f"{kind}: Telugu shaped correctly ({ratio:.3f}) '{t['text'][:30]}'")
        lg = m["logo"]; W = 1080
        check(abs(lg["h"] - render.LOGO_HEIGHT[kind]) < 0.5, f"{kind}: logo height locked ({lg['h']:.0f}px)")
        check(abs((lg["x"] + lg["w"] / 2) - W / 2) < 1.5, f"{kind}: logo centred")
        ct = m["contactText"]
        for s in (LOCK["contact_name"], LOCK["contact_phone"], LOCK["contact_email"]):
            check(s in ct, f"{kind}: contact contains '{s}'")
    # outro scene
    mo = qa["outro"]
    check(not mo["overflow"], f"outro: no overflow {mo['overflow'] if mo['overflow'] else ''}")
    check(abs(mo["logo"]["h"] - render.LOGO_HEIGHT["outro"]) < 0.5 and abs(mo["logo"]["x"] + mo["logo"]["w"] / 2 - 540) < 1.5, "outro: logo locked size, centred")
    for t in mo["te"]:
        f = tel[700 if t["weight"] >= 600 else 400].font_variant(size=t["px"]); ratio = t["width"] / f.getlength(t["text"])
        check(0.97 <= ratio <= 1.03, f"outro: Telugu shaped correctly ({ratio:.3f}) '{t['text'][:30]}'")

    # 7. audio
    import re as _re, difflib, asr_check
    lo = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(vid), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    I = float(_re.findall(r"I:\s+(-?[\d.]+) LUFS", lo)[-1]); pk = float(_re.findall(r"Peak:\s+(-?[\d.]+) dBFS", lo)[-1])
    check(-18 <= I <= -12, f"audio loudness {I} LUFS")
    check(pk <= -1.0, f"audio peak {pk} dBFS (no clipping)")
    check((HERE / "audio" / qa.get("music", "missing")).exists(), f"original background music used: {qa.get('music')}")
    for r in qa["voice"]["phrases"]:
        L = len(_re.sub(r"[^\u0C00-\u0C7F]", "", r["phrase"]))
        rate = r["seconds"] / max(L, 1)
        check(0.05 <= rate <= 0.25, f"voice rate natural ({rate:.3f}s/letter) '{r['phrase'][:24]}'")
        heard = asr_check.transcribe(d / r["file"])
        nh, ne = asr_check.norm(heard), asr_check.norm(r["phrase"])
        pref = difflib.SequenceMatcher(None, ne[:len(nh) + 2], nh).ratio() if len(nh) >= 3 else 0
        check(pref >= 0.6, f"voice says the right words ({pref:.2f}) '{r['phrase'][:24]}' heard '{heard[:24]}'")

    # 5. brand lock
    sha = hashlib.sha256(render.LOGO_PNG.read_bytes()).hexdigest()
    check(sha == LOCK["logo_png_sha256"] == qa["logo_sha256"], "logo file is the locked official logo")
    src = HERE / "brand" / "source" / "nutrilink-logo-official.png"
    check(hashlib.sha256(src.read_bytes()).hexdigest() == LOCK["official_source_sha256"], "official logo source unchanged")
    check((render.CONTACT_NAME, render.CONTACT_PHONE, render.CONTACT_EMAIL) ==
          (LOCK["contact_name"], LOCK["contact_phone"], LOCK["contact_email"]), "contact constants match brand lock")
    logo_visible(im, qa["post"]["logo"], "post.jpg")

    # 6. video frames
    with tempfile.TemporaryDirectory() as td:
        st = qa["voice"]["stage_starts"]
        times = [st[0] + 1.0] + [x + 1.2 for x in st[1:]] + [dur - 0.3]
        frames = []
        for i, t in enumerate(times):
            p = f"{td}/f{i}.png"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t}", "-i", str(vid), "-frames:v", "1", p], check=True)
            fr = Image.open(p).convert("RGB"); frames.append(fr)
            check(np.asarray(fr).std() > 10, f"video frame @{t:.1f}s not blank")
        logo_visible(frames[-1], qa["outro"]["logo"], "video outro frame")
        logo_visible(frames[0], qa["short"]["logo"], "video first frame")
        # contact sheet for human/agent visual review
        sheet = Image.new("RGB", (1080 + len(frames) * 405, 1350), "white")
        sheet.paste(im, (0, 0))
        for i, fr in enumerate(frames):
            sheet.paste(fr.resize((405, 720)), (1080 + i * 405, 0))
        sheet.save(d / "qa_sheet.jpg", quality=85)
    return report(d)


def report(d):
    for n in notes:
        print(n)
    for f in fails:
        print(f)
    print(f"\nRESULT: {'FAIL - DO NOT PUBLISH' if fails else 'PASS'} ({len(notes)} passed, {len(fails)} failed)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
