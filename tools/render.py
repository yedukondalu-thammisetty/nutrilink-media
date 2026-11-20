"""Render a NutriLink daily post (image + short video) from a content JSON.

Usage: python3 tools/render.py <content.json> <out_dir>

content.json:
{
  "title_te": "...", "title_en": "...",
  "tips": [{"te": "...", "en": "..."}, ...],   # 3 tips works best
  "cta_te": "...", "cta_en": "...",
  "theme": "green" | "orange" | "blue" | "purple"   (optional)
}

Outputs: post.jpg (1080x1350, Instagram feed) and short.mp4 (1080x1920, ~14s, YouTube Shorts / Reels)
"""
import base64, json, os, subprocess, sys, tempfile, pathlib
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent


class _Fonts:
    """Fonts are embedded as data URIs (file:// URLs don't load inside set_content)."""
    def __truediv__(self, name):
        return name

    def __format__(self, spec):
        return "FONTDIR"


FONTS = _Fonts()


def _embed_fonts(doc):
    import re
    def rep(m):
        data = base64.b64encode((HERE / "fonts" / m.group(1)).read_bytes()).decode()
        return f"url(data:font/woff2;base64,{data}) format('woff2')"
    return re.sub(r"url\(FONTDIR/([^)]+)\)", rep, doc)

CONTACT_NAME = "Wellness Coach Venkteswarlu.P"
CONTACT_PHONE = "+91 8008978350"
CONTACT_EMAIL = "p.venkateswarlu333@gmail.com"

THEMES = {
    "green":  ("#0f5132", "#2e8b57", "#e8f5e9", "#ffd166"),
    "orange": ("#7a2e0b", "#e76f24", "#fff3e6", "#ffe08a"),
    "blue":   ("#0b3b5c", "#1f7ab8", "#e6f2fb", "#ffd166"),
    "purple": ("#3d1a5b", "#7b3fa8", "#f3eafa", "#ffd166"),
}


def html(c, w, h, stage):
    dark, mid, light, accent = THEMES.get(c.get("theme", "green"), THEMES["green"])
    tall = h > 1500
    tips = "".join(
        f"""<div class="tip {'show' if i < stage else ''}">
              <div class="num">{i+1}</div>
              <div><div class="te">{t['te']}</div><div class="en">{t['en']}</div></div>
            </div>"""
        for i, t in enumerate(c["tips"])
    )
    cta_show = "show" if stage > len(c["tips"]) else ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:Tel,Pop;font-weight:400;src:url({FONTS}/noto-sans-telugu-telugu-400-normal.woff2)}}
@font-face{{font-family:Tel,Pop;font-weight:700;src:url({FONTS}/noto-sans-telugu-telugu-700-normal.woff2)}}
@font-face{{font-family:Pop;font-weight:400;src:url({FONTS}/poppins-latin-400-normal.woff2)}}
@font-face{{font-family:Pop;font-weight:600;src:url({FONTS}/poppins-latin-600-normal.woff2)}}
@font-face{{font-family:Pop;font-weight:700;src:url({FONTS}/poppins-latin-700-normal.woff2)}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{w}px;height:{h}px;font-family:Pop,Tel,sans-serif;color:#fff;
  background:radial-gradient(circle at 85% 10%,{mid} 0,transparent 45%),linear-gradient(160deg,{mid},{dark} 70%);
  display:flex;flex-direction:column;padding:{110 if tall else 64}px 72px {80 if tall else 56}px;overflow:hidden}}
.brand{{display:flex;align-items:center;gap:18px;font-weight:700;font-size:38px;letter-spacing:.5px}}
.leaf{{width:58px;height:58px;border-radius:0 50% 0 50%;background:{accent};box-shadow:inset -10px -10px 0 rgba(0,0,0,.12)}}
.brand small{{display:block;font-weight:400;font-size:24px;opacity:.85}}
.title{{margin-top:{90 if tall else 50}px}}
.title .te{{font-family:Tel,Pop;font-weight:700;font-size:{78 if tall else 64}px;line-height:1.45;color:{accent}}}
.title .en{{font-size:{38 if tall else 32}px;font-weight:600;margin-top:10px;opacity:.95}}
.tips{{margin-top:{70 if tall else 40}px;display:flex;flex-direction:column;gap:{34 if tall else 22}px}}
.tip{{display:flex;gap:26px;align-items:flex-start;background:rgba(255,255,255,.12);border-radius:28px;
  padding:{30 if tall else 22}px 30px;opacity:0;transform:translateY(20px)}}
.tip.show{{opacity:1;transform:none}}
.num{{flex:none;width:64px;height:64px;border-radius:50%;background:{light};color:{dark};font-weight:700;
  font-size:34px;display:flex;align-items:center;justify-content:center}}
.tip .te{{font-family:Tel,Pop;font-weight:700;font-size:{44 if tall else 36}px;line-height:1.5}}
.tip .en{{font-size:{28 if tall else 24}px;opacity:.88;margin-top:4px}}
.cta{{margin-top:auto;opacity:0}} .cta.show{{opacity:1}}
.cta .te{{font-family:Tel,Pop;font-weight:700;font-size:{40 if tall else 32}px;line-height:1.5;color:{accent}}}
.cta .en{{font-size:{26 if tall else 22}px;opacity:.9}}
.contact{{margin-top:{36 if tall else 22}px;background:{light};color:{dark};border-radius:26px;padding:{28 if tall else 20}px 32px}}
.contact .n{{font-weight:700;font-size:{34 if tall else 28}px}}
.contact .d{{font-size:{28 if tall else 24}px;margin-top:6px;font-weight:600}}
</style></head><body>
<div class="brand"><div class="leaf"></div><div>NutriLink<small>By NutriiGlow</small></div></div>
<div class="title"><div class="te">{c['title_te']}</div><div class="en">{c['title_en']}</div></div>
<div class="tips">{tips}</div>
<div class="cta {cta_show}"><div class="te">{c['cta_te']}</div><div class="en">{c['cta_en']}</div>
<div class="contact"><div class="n">{CONTACT_NAME}</div>
<div class="d">Call / WhatsApp: {CONTACT_PHONE}</div><div class="d">{CONTACT_EMAIL}</div></div></div>
</body></html>"""


def shot(page, c, w, h, stage, path):
    page.set_viewport_size({"width": w, "height": h})
    page.set_content(_embed_fonts(html(c, w, h, stage)))
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(300)
    page.screenshot(path=path, type="png")


def main():
    c = json.load(open(sys.argv[1], encoding="utf-8"))
    out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    n = len(c["tips"])
    with tempfile.TemporaryDirectory() as td, sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome") if os.path.exists("/usr/bin/google-chrome") else p.chromium.launch()
        page = b.new_page()
        shot(page, c, 1080, 1350, n + 1, f"{td}/post.png")
        frames = []
        for s in range(0, n + 2):
            f = f"{td}/f{s}.png"; shot(page, c, 1080, 1920, s, f); frames.append(f)
        b.close()
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{td}/post.png", "-q:v", "2", str(out / "post.jpg")], check=True)
        # durations: intro 2s, each tip 3s, final 5s; 0.5s crossfades
        durs = [2.0] + [3.0] * n + [5.0]
        args = ["ffmpeg", "-y", "-loglevel", "error"]
        for f, d in zip(frames, durs):
            args += ["-loop", "1", "-t", str(d + 0.5), "-i", f]
        args += ["-f", "lavfi", "-t", str(sum(durs) + 0.5), "-i", "anullsrc=r=44100:cl=stereo"]
        chain, prev, off = [], "[0:v]", 0.0
        for i in range(1, len(frames)):
            off += durs[i - 1]
            lbl = f"[v{i}]"
            chain.append(f"{prev}[{i}:v]xfade=transition=fade:duration=0.5:offset={off:.2f}{lbl}")
            prev = lbl
        chain.append(f"{prev}format=yuv420p,fps=30[vout]")
        args += ["-filter_complex", ";".join(chain), "-map", "[vout]", "-map", f"{len(frames)}:a",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-shortest",
                 "-movflags", "+faststart", str(out / "short.mp4")]
        subprocess.run(args, check=True)
    print("done", out)


if __name__ == "__main__":
    main()
