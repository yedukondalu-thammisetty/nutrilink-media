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
LOGO_HEIGHT = {"post": 190, "short": 250, "outro": 420}  # px; fixed
BRAND_COLORS = {"teal": "#10A9A6", "blue": "#1F72E0", "green": "#8BD54E", "navy": "#131C2B", "white": "#FFFFFF"}
CONTACT_NAME = "Wellness Coach Venkteswarlu.P"
CONTACT_PHONE = "+91 8008978350"
CONTACT_EMAIL = "p.venkateswarlu333@gmail.com"
TAGLINE = "Nourish · Transform · Glow"
IG_HANDLE = "@nutrilink.wellness"
SUBSCRIBE_TE = "రోజూ ఆరోగ్య చిట్కాల కోసం సబ్‌స్క్రైబ్ చేయండి"
SUBSCRIBE_EN = "Subscribe for daily Telugu health tips"
MUSIC_DB = -21   # music level under the voice (dB); voice stays clearly on top
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


def outro_html(c, w, h):
    g, navy = BRAND_COLORS["green"], BRAND_COLORS["navy"]
    bg = THEMES["brand"]  # logo always sits on the official teal-to-blue gradient
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
{font_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{w}px;height:{h}px;font-family:Pop,sans-serif;color:#fff;background:{bg};display:flex;flex-direction:column;
  align-items:center;justify-content:center;padding:80px 72px;overflow:hidden;text-align:center}}
.te{{font-family:Tel}}
.logo{{display:block;height:{LOGO_HEIGHT['outro']}px;width:auto}}
.tag{{margin-top:40px;font-size:40px;font-weight:600;color:{g}}}
.sub{{margin-top:90px;background:#fff;color:{navy};border-radius:60px;padding:30px 44px}}
.sub .te{{font-weight:700;font-size:40px;line-height:1.55}}
.sub .en{{font-size:28px;font-weight:600;margin-top:4px}}
.handle{{margin-top:36px;font-size:30px;font-weight:600}}
</style></head><body>
<img class="logo" id="logo" src="data:image/png;base64,{_b64(LOGO_PNG)}">
<div class="tag">{TAGLINE}</div>
<div class="sub"><div class="te">{SUBSCRIBE_TE}</div><div class="en">{SUBSCRIBE_EN}</div></div>
<div class="handle">Instagram {IG_HANDLE}</div>
<div id="contact" style="display:none">{CONTACT_NAME} {CONTACT_PHONE} {CONTACT_EMAIL}</div>
</body></html>"""


def html(c, w, h, stage, kind):
    tall = kind == "short"
    bg = THEMES["brand"]  # logo always sits on the official teal-to-blue gradient
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
.follow{{margin-top:{0 if tall else 12}px;font-size:22px;font-weight:600}}
</style></head><body>
<img class="logo" id="logo" src="data:image/png;base64,{_b64(LOGO_PNG)}">
<div class="title"><div class="te">{c['title_te']}</div><div class="en">{c['title_en']}</div></div>
<div class="tips">{tips}</div>
<div class="cta {cta_show}"><div class="te">{c['cta_te']}</div><div class="en">{c['cta_en']}</div>
<div class="contact" id="contact"><div class="n">{CONTACT_NAME}</div>
<div class="d">Call / WhatsApp: {CONTACT_PHONE}</div><div class="d">{CONTACT_EMAIL}</div></div>
<div class="follow">{'Follow ' + IG_HANDLE + ' for daily Telugu health tips' if not tall else ''}</div></div>
</body></html>"""


def convo_html(c, w, h, stage):
    """Conversation-style Short (used when content.json has "answer_te"): a viewer asks the question,
    the coach answers in a chat bubble, then the steps and the DM keyword + contact card build up.
    Stages: 0 question, 1 answer, 2..n+1 tips, n+2 CTA+contact."""
    bg = THEMES["brand"]  # logo always sits on the official teal-to-blue gradient
    g, navy, teal = BRAND_COLORS["green"], BRAND_COLORS["navy"], BRAND_COLORS["teal"]
    n = len(c["tips"])
    sh = lambda cond: "show" if cond else ""
    from icons import icon_uri
    pic = lambda e, px: f'<img class="pic" src="{icon_uri(e)[0]}" style="width:{px}px;height:{px}px">'
    tips = "".join(
        f"""<div class="tip {sh(stage >= i + 2)}">{pic(t['icon'], 84) if t.get('icon') else f'<div class="num">{i+1}</div>'}
              <div class="tx"><div class="te">{t['te']}</div><div class="en">{t['en']}</div></div></div>""" for i, t in enumerate(c["tips"]))
    kw = c.get("carousel", {}).get("dm_keyword", "")
    dm = f'DM or comment “{kw}” · ' if kw else ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
{font_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{w}px;height:{h}px;font-family:Pop,sans-serif;color:#fff;background:{bg};
  display:flex;flex-direction:column;align-items:stretch;padding:80px 64px 70px;overflow:hidden}}
.te{{font-family:Tel}}
.logo{{display:block;height:{LOGO_HEIGHT['short']}px;width:auto;margin:0 auto}}
.who{{font-size:26px;font-weight:600;opacity:.9;margin-bottom:10px}}
.who .te{{font-weight:700;font-size:28px}}
.title{{margin-top:36px;align-self:flex-start;max-width:900px}}
.bub{{border-radius:34px;padding:26px 34px}}
.q{{background:#fff;color:{navy};border-top-left-radius:8px}}
.q .te{{font-weight:700;font-size:58px;line-height:1.5}}
.q .en{{font-size:26px;font-weight:600;color:{teal};margin-top:4px}}
.answer{{margin-top:26px;align-self:flex-end;max-width:900px;text-align:right;opacity:0}} .answer.show{{opacity:1}}
.a{{background:{g};color:{navy};border-top-right-radius:8px;text-align:left}}
.a .te{{font-weight:700;font-size:54px;line-height:1.5}}
.a .en{{font-size:25px;font-weight:600;margin-top:2px}}
.hero{{display:flex;justify-content:center;align-items:flex-end;gap:16px;margin-top:22px;opacity:0}} .hero.show{{opacity:1}}
.pic{{display:block;flex:none;filter:drop-shadow(0 10px 14px rgba(0,0,0,.25))}}
.tips{{margin-top:26px;display:flex;flex-direction:column;gap:20px}}
.tip{{display:flex;gap:20px;align-items:center;background:rgba(19,28,43,.30);border-radius:24px;padding:22px 26px;opacity:0}}
.tip.show{{opacity:1}}
.num{{flex:none;width:54px;height:54px;border-radius:50%;background:{g};color:{navy};font-weight:700;font-size:28px;display:flex;align-items:center;justify-content:center}}
.tx{{min-width:0}}
.tip .te{{font-weight:700;font-size:40px;line-height:1.5}}
.tip .en{{font-size:23px;opacity:.92}}
.cta{{margin-top:auto;opacity:0;text-align:center}} .cta.show{{opacity:1}}
.cta .te{{font-weight:700;font-size:36px;line-height:1.5}}
.cta .en{{font-size:24px;opacity:.95}}
.contact{{margin-top:18px;background:#fff;color:{navy};border-radius:24px;padding:20px 28px;text-align:center}}
.contact .n{{font-weight:700;font-size:32px}}
.contact .d{{font-size:26px;margin-top:2px;font-weight:600}}
</style></head><body>
<img class="logo" id="logo" src="data:image/png;base64,{_b64(LOGO_PNG)}">
<div class="title"><div class="who">👥 <span class="te">చాలామంది నన్ను అడిగే ప్రశ్న</span></div>
 <div class="bub q"><div class="te">{c['title_te']}</div><div class="en">{c['title_en']}</div></div></div>
<div class="answer {sh(stage >= 1)}"><div class="who"><span class="te">నా సమాధానం</span> 🧑‍⚕️</div>
 <div class="bub a"><div class="te">{c['answer_te']}</div><div class="en">{c['answer_en']}</div></div></div>
<div class="hero show">{''.join(pic(e, 190 if j == len(c.get('icons', [])) // 2 else 150) for j, e in enumerate(c.get('icons', [])[:3]))}</div>
<div class="tips">{tips}</div>
<div class="cta {sh(stage >= n + 2)}"><div class="te">{c['cta_te']}</div><div class="en">{dm}{c['cta_en']}</div>
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
  for (const el of document.querySelectorAll('.logo,.title,.answer,.bub,.tip,.cta,.contact,.te,.en,.tag,.sub,.handle,.follow')) {
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
    page.set_content(outro_html(c, w, h) if kind == "outro" else
                     convo_html(c, w, h, stage) if (kind == "short" and "answer_te" in c) else html(c, w, h, stage, kind))
    page.evaluate("async () => { await Promise.all([...document.fonts].map(f => f.load())); await document.fonts.ready; }")
    page.wait_for_timeout(300)
    page.screenshot(path=path, type="png")
    return page.evaluate(MEASURE_JS)


def build_voice(c, out, td):
    """Synthesize narration per stage (phrase by phrase). Returns list of (stage_wav, seconds) and phrase records."""
    import voice
    vdir = out / "voice"; vdir.mkdir(exist_ok=True)
    for old in vdir.glob("*"):
        old.unlink()
    stages, records = [], []
    for si, seg in enumerate(voice.script(c)):
        parts = []
        for pi, ph in enumerate(voice.phrases(seg)):
            wav = f"{td}/s{si}p{pi}.wav"
            dur = voice.synth(ph, wav)
            keep = vdir / f"s{si}p{pi}.m4a"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "aac", "-b:a", "64k", str(keep)], check=True)
            records.append({"stage": si, "phrase": ph, "file": f"voice/{keep.name}", "seconds": round(dur, 2)})
            parts.append((wav, 0.22 if ph.endswith((".", "!", "?")) else 0.10))
        # concat phrases with natural pauses
        lst = f"{td}/s{si}.txt"; args = ["ffmpeg", "-y", "-loglevel", "error"]
        filt, k = [], 0
        for wav, gap in parts:
            args += ["-i", wav, "-f", "lavfi", "-t", str(gap), "-i", "anullsrc=r=22050:cl=mono"]
            filt.append(f"[{k}:a][{k+1}:a]"); k += 2
        out_wav = f"{td}/stage{si}.wav"
        args += ["-filter_complex", "".join(filt) + f"concat=n={k}:v=0:a=1[a]", "-map", "[a]", "-ar", "44100", out_wav]
        subprocess.run(args, check=True)
        secs = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out_wav],
                                    capture_output=True, text=True).stdout)
        stages.append((out_wav, secs))
    return stages, records


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
        import voice
        n_frames = len(voice.script(c)) - 1   # one frame per narration stage, plus the outro below
        for s_ in range(0, n_frames):
            f = f"{td}/f{s_}.png"
            m = shot(page, c, 1080, 1920, s_, "short", f)
            frames.append(f)
        qa["short"] = m
        qa["outro"] = shot(page, c, 1080, 1920, 0, "outro", f"{td}/outro.png")
        frames.append(f"{td}/outro.png")
        b.close()
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{td}/post.png", "-q:v", "2", str(out / "post.jpg")], check=True)

        # ---- voice-over: one narration block per stage (title, tips, CTA+contact, brand outro)
        stages, records = build_voice(c, out, td)
        assert len(stages) == len(frames), (len(stages), len(frames))
        LEAD, TAIL = 0.15, 0.25
        durs = [max(1.8, LEAD + secs + TAIL) for _, secs in stages]
        durs[-1] += 0.5
        total = sum(durs)
        starts = [sum(durs[:i]) for i in range(len(durs))]
        qa["voice"] = {"phrases": records, "stage_starts": starts, "stage_durations": durs}

        # voice track
        args = ["ffmpeg", "-y", "-loglevel", "error"]
        for wav, _ in stages:
            args += ["-i", wav]
        mix = []
        for i, st in enumerate(starts):
            ms = int((st + LEAD) * 1000)
            mix.append(f"[{i}:a]adelay={ms}|{ms},apad[d{i}]")
        args += ["-filter_complex", ";".join(mix) + ";" + "".join(f"[d{i}]" for i in range(len(stages))) +
                 f"amix=inputs={len(stages)}:normalize=0,atrim=0:{total:.2f},loudnorm=I=-16:TP=-2:LRA=9[v]",
                 "-map", "[v]", "-ac", "2", "-ar", "44100", f"{td}/voice.wav"]
        subprocess.run(args, check=True)
        # music (original tracks, rotated by date) under the voice
        import datetime
        tracks = sorted((HERE / "audio").glob("track*.m4a"))
        day = c.get("date") or out.name
        try:
            idx = datetime.date.fromisoformat(day).toordinal() % len(tracks)
        except ValueError:
            idx = 0
        music = tracks[idx]
        qa["music"] = music.name
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{td}/voice.wav", "-i", str(music), "-filter_complex",
                        f"[1:a]atrim=0:{total:.2f},volume={MUSIC_DB}dB,afade=t=out:st={total-2:.2f}:d=2[m];"
                        f"[0:a][m]amix=inputs=2:normalize=0,alimiter=limit=0.89[a]",
                        "-map", "[a]", "-ar", "44100", "-ac", "2", f"{td}/mix.wav"], check=True)

        args = ["ffmpeg", "-y", "-loglevel", "error"]
        for f, d in zip(frames, durs):
            args += ["-loop", "1", "-t", str(d + 0.5), "-i", f]
        args += ["-i", f"{td}/mix.wav"]
        chain, prev, off = [], "[0:v]", 0.0
        for i in range(1, len(frames)):
            off += durs[i - 1]
            chain.append(f"{prev}[{i}:v]xfade=transition=fade:duration=0.3:offset={off:.2f}[v{i}]")
            prev = f"[v{i}]"
        chain.append(f"{prev}format=yuv420p,fps=30[vout]")
        args += ["-filter_complex", ";".join(chain), "-map", "[vout]", "-map", f"{len(frames)}:a",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
                 "-t", f"{total:.2f}", "-movflags", "+faststart", str(out / "short.mp4")]
        subprocess.run(args, check=True)
    json.dump(qa, open(out / "qa.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("rendered", out)


if __name__ == "__main__":
    main()
