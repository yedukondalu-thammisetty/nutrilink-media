"""Render a NutriLink daily post (image + short video) from a content JSON.

Usage: python3 tools/render.py <content.json> <out_dir>

content.json:
{
  "title_te": "...", "title_en": "...",
  "tips": [{"te": "...", "en": "..."}, ...],   # exactly 3 tips
  "cta_te": "...", "cta_en": "...",
  "theme": "brand" | "navy"   (optional; both use only official brand colours)
}

Outputs in out_dir:
  post.jpg   1080x1350  Instagram feed image
  short.mp4  1080x1920  YouTube Shorts video (~16s)
  qa.json    measurements used by tools/validate.py (fonts loaded, text shaping, overflow, logo)

Always run tools/validate.py on out_dir afterwards. Never publish if it fails.
"""
import base64, hashlib, json, os, subprocess, sys, tempfile, pathlib
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent

# ---------------- LOCKED BRAND IDENTITY (never change per post) ----------------
# Official logo supplied by the owner: tools/brand/source/nutrilink-logo-official.png
# tools/brand/logo.png is the white mark + "NutriLink / by NutriGlow" extracted from it.
# Its sha256 is pinned in tools/brand/brand.lock.json and checked by validate.py.
LOGO_PNG = HERE / "brand" / "logo.png"
LOGO_HEIGHT = {"post": 190, "short": 250}  # px; fixed
BRAND_COLORS = {"teal": "#10A9A6", "blue": "#1F72E0", "green": "#8BD54E", "navy": "#131C2B", "white": "#FFFFFF"}
CONTACT_NAME = "Wellness Coach Venkteswarlu.P"
CONTACT_PHONE = "+91 8008978350"
CONTACT_EMAIL = "p.venkateswarlu333@gmail.com"
# ------------------------------------------------------------------------------

THEMES = {
    "brand": f"linear-gradient(150deg,{BRAND_COLORS['teal']} 0%,#1690C4 55%,{BRAND_COLORS['blue']} 100%)",
    "navy": f"radial-gradient(circle at 20% 0%,rgba(16,169,166,.45) 0,transparent 55%),"
            f"radial-gradient(circle at 100% 100%,rgba(31,114,224,.45) 0,transparent 55%),{BRAND_COLORS['navy']}",
}

FONT_FILES = {
    ("Tel", 400): "NotoSansTelugu-Regular.ttf",
    ("Tel", 700): "NotoSansTelugu-Bold.ttf",
    ("Pop", 400): "poppins-latin-400-normal.woff2",
    ("Pop", 600): "poppins-latin-600-normal.woff2",
    ("Pop", 700): "poppins-latin-700-normal.woff2",
}


def _b64(p):
    return base64.b64encode(pathlib.Path(p).read_bytes()).decode()


def font_css():
    out = []
    for (fam, wt), fn in FONT_FILES.items():
        fmt, mime = ("truetype", "font/ttf") if fn.endswith(".ttf") else ("woff2", "font/woff2")
        out.append(f"@font-face{{font-family:{fam};font-weight:{wt};"
                   f"src:url(data:{mime};base64,{_b64(HERE/'fonts'/fn)}) format('{fmt}')}}")
    return "\n".join(out)


def html(c, w, h, stage, kind):
    tall = kind == "short"
    bg = THEMES.get(c.get("theme", "brand"), THEMES["brand"])
    g, navy = BRAND_COLORS["green"], BRAND_COLORS["navy"]
    tips = "".join(
        f"""<div class="tip {'show' if i < stage else ''}">
              <div class="num">{i+1}</div>
              <div class="tx"><div class="te">{t['te']}</div><div class="en">{t['en']}</div></div>
            </div>""" for i, t in enumerate(c["tips"]))
    cta_show = "show" if stage > len(c["tips"]) else ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
{font_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{w}px;height:{h}px;font-family:Pop,sans-serif;color:#fff;background:{bg};
  display:flex;flex-direction:column;align-items:stretch;padding:{90 if tall else 50}px 72px {80 if tall else 50}px;overflow:hidden}}
.te{{font-family:Tel}}
.logo{{display:block;height:{LOGO_HEIGHT[kind]}px;width:auto;margin:0 auto}}
.title{{margin-top:{70 if tall else 34}px;text-align:center}}
.title .te{{font-weight:700;font-size:{70 if tall else 56}px;line-height:1.5}}
.title .en{{font-size:{36 if tall else 30}px;font-weight:600;margin-top:6px;color:{g}}}
.tips{{margin-top:{60 if tall else 30}px;display:flex;flex-direction:column;gap:{30 if tall else 18}px}}
.tip{{display:flex;gap:24px;align-items:center;background:rgba(19,28,43,.28);border-radius:26px;
  padding:{28 if tall else 18}px 28px;opacity:0}}
.tip.show{{opacity:1}}
.num{{flex:none;width:60px;height:60px;border-radius:50%;background:{g};color:{navy};font-weight:700;
  font-size:32px;display:flex;align-items:center;justify-content:center}}
.tx{{min-width:0}}
.tip .te{{font-weight:700;font-size:{42 if tall else 34}px;line-height:1.55}}
.tip .en{{font-size:{27 if tall else 23}px;opacity:.92;margin-top:2px}}
.cta{{margin-top:auto;opacity:0;text-align:center}} .cta.show{{opacity:1}}
.cta .te{{font-weight:700;font-size:{40 if tall else 32}px;line-height:1.55}}
.cta .en{{font-size:{26 if tall else 22}px;opacity:.95}}
.contact{{margin-top:{30 if tall else 16}px;background:#fff;color:{navy};border-radius:24px;padding:{26 if tall else 18}px 30px;text-align:center}}
.contact .n{{font-weight:700;font-size:{34 if tall else 28}px}}
.contact .d{{font-size:{28 if tall else 23}px;margin-top:4px;font-weight:600}}
</style></head><body>
<img class="logo" id="logo" src="data:image/png;base64,{_b64(LOGO_PNG)}">
<div class="title"><div class="te">{c['title_te']}</div><div class="en">{c['title_en']}</div></div>
<div class="tips">{tips}</div>
<div class="cta {cta_show}"><div class="te">{c['cta_te']}</div><div class="en">{c['cta_en']}</div>
<div class="contact" id="contact"><div class="n">{CONTACT_NAME}</div>
<div class="d">Call / WhatsApp: {CONTACT_PHONE}</div><div class="d">{CONTACT_EMAIL}</div></div></div>
</body></html>"""


MEASURE_JS = """() => {
  const r = {fontsTel400: document.fonts.check('400 40px Tel', 'తెలుగు'),
             fontsTel700: document.fonts.check('700 40px Tel', 'తెలుగు'),
             fontsPop: document.fonts.check('700 40px Pop', 'Nutri'), te: [], overflow: []};
  for (const el of document.querySelectorAll('.te')) {
    const cs = getComputedStyle(el);
    const s = document.createElement('span');
    s.style.cssText = `font-family:${cs.fontFamily};font-weight:${cs.fontWeight};font-size:${cs.fontSize};white-space:nowrap;position:absolute;left:-99999px`;
    s.textContent = el.textContent; document.body.appendChild(s);
    r.te.push({text: el.textContent, px: parseFloat(cs.fontSize), weight: parseInt(cs.fontWeight), width: s.getBoundingClientRect().width});
    s.remove();
  }
  const W = document.body.clientWidth, H = document.body.clientHeight;
  for (const el of document.querySelectorAll('.logo,.title,.tip,.cta,.contact,.te,.en')) {
    const b = el.getBoundingClientRect();
    if (b.left < 0 || b.top < 0 || b.right > W + 0.5 || b.bottom > H + 0.5 || el.scrollWidth > el.clientWidth + 1)
      r.overflow.push({cls: el.className, text: (el.textContent||'').slice(0,40), box: [b.left,b.top,b.right,b.bottom]});
  }
  const L = document.getElementById('logo').getBoundingClientRect();
  r.logo = {x: L.left, y: L.top, w: L.width, h: L.height};
  r.contactText = document.getElementById('contact').innerText;
  return r;
}"""


def shot(page, c, w, h, stage, kind, path):
    page.set_viewport_size({"width": w, "height": h})
    page.set_content(html(c, w, h, stage, kind))
    page.evaluate("async () => { await Promise.all([...document.fonts].map(f => f.load())); await document.fonts.ready; }")
    page.wait_for_timeout(300)
    page.screenshot(path=path, type="png")
    return page.evaluate(MEASURE_JS)


def main():
    c = json.load(open(sys.argv[1], encoding="utf-8"))
    out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    n = len(c["tips"])
    qa = {"logo_sha256": hashlib.sha256(LOGO_PNG.read_bytes()).hexdigest()}
    with tempfile.TemporaryDirectory() as td, sync_playwright() as p:
        exe = "/usr/bin/google-chrome" if os.path.exists("/usr/bin/google-chrome") else None
        b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        page = b.new_page()
        qa["post"] = shot(page, c, 1080, 1350, n + 1, "post", f"{td}/post.png")
        frames = []
        for s in range(0, n + 2):
            f = f"{td}/f{s}.png"
            m = shot(page, c, 1080, 1920, s, "short", f)
            frames.append(f)
        qa["short"] = m  # final (full) frame
        b.close()
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{td}/post.png", "-q:v", "2", str(out / "post.jpg")], check=True)
        durs = [2.0] + [3.0] * n + [5.0]
        args = ["ffmpeg", "-y", "-loglevel", "error"]
        for f, d in zip(frames, durs):
            args += ["-loop", "1", "-t", str(d + 0.5), "-i", f]
        args += ["-f", "lavfi", "-t", str(sum(durs) + 0.5), "-i", "anullsrc=r=44100:cl=stereo"]
        chain, prev, off = [], "[0:v]", 0.0
        for i in range(1, len(frames)):
            off += durs[i - 1]
            chain.append(f"{prev}[{i}:v]xfade=transition=fade:duration=0.5:offset={off:.2f}[v{i}]")
            prev = f"[v{i}]"
        chain.append(f"{prev}format=yuv420p,fps=30[vout]")
        args += ["-filter_complex", ";".join(chain), "-map", "[vout]", "-map", f"{len(frames)}:a",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-shortest",
                 "-movflags", "+faststart", str(out / "short.mp4")]
        subprocess.run(args, check=True)
    json.dump(qa, open(out / "qa.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("rendered", out)


if __name__ == "__main__":
    main()
