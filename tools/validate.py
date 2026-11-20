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
  6. Video frames are not blank.
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
    check(10 <= dur <= 60, f"video duration {dur:.1f}s")
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
        times = [0.5, 3, 6, 9, 12, dur - 0.3]
        frames = []
        for i, t in enumerate(times):
            p = f"{td}/f{i}.png"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t}", "-i", str(vid), "-frames:v", "1", p], check=True)
            fr = Image.open(p).convert("RGB"); frames.append(fr)
            check(np.asarray(fr).std() > 10, f"video frame @{t:.1f}s not blank")
        logo_visible(frames[-1], qa["short"]["logo"], "video final frame")
        logo_visible(frames[0], qa["short"]["logo"], "video first frame")
        # contact sheet for human/agent visual review
        sheet = Image.new("RGB", (1080 + 6 * 405, 1350), "white")
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
