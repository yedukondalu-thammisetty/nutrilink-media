"""Conversation-style Instagram carousel (5 slides, 1080x1350) for NutriLink By NutriiGlow.

Usage: python3 tools/carousel.py posts/<date>/content.json posts/<date>
Reads the "carousel" block of content.json, writes carousel_1.jpg ... carousel_5.jpg and
carousel_qa.json, and exits non-zero if any check fails (fonts, Telugu text overflow,
logo, contact details). Uses the locked logo, fonts and contact constants from render.py.

content.json "carousel" block:
  question_te      the question people ask (hook)            e.g. "Rice పూర్తిగా మానేస్తేనే బరువు తగ్గుతామా?"
  answer_te        the short answer                          e.g. "కాదు! అస్సలు అవసరం లేదు."
  why_te           one-line reason                            e.g. "Problem Rice కాదు… Quantity & Combination."
  why_detail_te    1-2 sentence explanation
  steps_title_te   heading for the how-to slide              e.g. "మీ Plate ఇలా ఉండేలా చూసుకోండి"
  steps            3-4 items {"icon": "<one emoji>", "te": "<text>"}
  remember_te      key takeaway (slide 4)
  cta_question_te  question on the last slide                e.g. "మీ Plate ఎలా ఉండాలో తెలుసుకోవాలా?"
  dm_keyword       one English word in capitals              e.g. "PLATE"
Wrap a word in [[ ]] to colour it teal and in {{ }} to underline it in green.
"""
import html as H
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from render import (BRAND_COLORS, CONTACT_EMAIL, CONTACT_NAME, CONTACT_PHONE, IG_HANDLE, LOGO_PNG,  # noqa: E402
                    _b64, font_css)

YT_HANDLE = "@NutriLinkWellnessPlatform"
TEAL, BLUE, GREEN, NAVY = (BRAND_COLORS[k] for k in ("teal", "blue", "green", "navy"))


def fmt(s):
    s = H.escape(s)
    s = re.sub(r"\[\[(.+?)\]\]", r'<span class="hl">\1</span>', s)
    s = re.sub(r"\{\{(.+?)\}\}", r'<span class="ul">\1</span>', s)
    return s.replace("\n", "<br>")


CSS = f"""
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:1080px;height:1350px;overflow:hidden;background:#FAFAF7;color:{NAVY};font-family:Pop,Tel,"Noto Color Emoji",sans-serif;position:relative}}
.te{{font-family:Pop,Tel,"Noto Color Emoji";font-weight:700}}
.hl{{color:{TEAL}}} .q{{color:{BLUE}}}
.ul{{background:linear-gradient(transparent 68%,rgba(139,213,78,.55) 68%)}}
.head{{position:absolute;left:64px;right:64px;top:48px;display:flex;justify-content:space-between;align-items:center}}
.badge{{background:linear-gradient(150deg,{TEAL} 0%,#1690C4 55%,{BLUE} 100%);border-radius:24px;padding:12px 24px;display:flex;align-items:center;box-shadow:0 8px 24px rgba(31,114,224,.25)}}
.logo{{height:96px;width:auto;display:block}}
.pg{{font-size:28px;font-weight:600;color:#6B7280}}
.main{{position:absolute;left:80px;right:80px;top:200px;bottom:150px;display:flex;flex-direction:column;justify-content:center}}
.chip{{align-self:flex-start;background:#E3F6F5;color:#0B7F7D;border-radius:40px;padding:12px 30px;font-size:32px}}
.big{{font-size:84px;line-height:1.5}}
.mid{{font-size:56px;line-height:1.55}}
.sm{{font-size:36px;line-height:1.65;font-weight:400;color:#374151}}
.ans{{background:#EEF9E6;border-left:12px solid {GREEN};border-radius:22px;padding:30px 40px}}
.card{{background:#fff;border:2px solid #E5E7EB;border-radius:28px;padding:16px 34px;box-shadow:0 10px 30px rgba(19,28,43,.06)}}
.step{{display:flex;gap:24px;align-items:flex-start;padding:20px 0;border-bottom:2px dashed #E5E7EB;font-size:40px;line-height:1.55}}
.step:last-child{{border-bottom:none}}
.step .ic{{flex:none;font-size:46px;width:60px;text-align:center}}
.foot{{position:absolute;left:64px;right:64px;bottom:52px;display:flex;justify-content:space-between;align-items:center;font-size:26px;font-weight:600;color:#4B5563}}
.swipe{{background:{NAVY};color:#fff;border-radius:40px;padding:12px 28px}}
.dm{{display:inline-block;background:linear-gradient(90deg,{TEAL},{BLUE});color:#fff;border-radius:60px;padding:24px 56px;font-size:48px}}
.contact{{margin-top:44px;background:{NAVY};color:#fff;border-radius:28px;padding:30px 36px;text-align:center}}
.contact .n{{font-size:36px;font-weight:700}} .contact .d{{font-size:30px;font-weight:600;margin-top:6px}}
"""

YT_ICON = '<svg width="34" height="24" viewBox="0 0 34 24" style="vertical-align:-4px"><rect width="34" height="24" rx="6" fill="#FF0033"/><path d="M13.5 6.5v11l9.5-5.5z" fill="#fff"/></svg>'


def slide(n, total, body):
    last = n == total
    foot = (f'<div>{IG_HANDLE}</div><div class="swipe">Swipe ➜</div>' if not last
            else f'<div>{IG_HANDLE}</div><div>{YT_ICON} {YT_HANDLE}</div>')
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{font_css()}{CSS}</style></head><body>
<div class="head"><div class="badge"><img class="logo" id="logo" src="data:image/png;base64,{_b64(LOGO_PNG)}"></div><div class="pg">{n}/{total}</div></div>
<div class="main" id="main">{body}</div><div class="foot">{foot}</div></body></html>"""


def slides(k):
    s = []
    s.append(f"""<div class="chip te">👥 చాలామంది నన్ను అడిగే Question…</div>
<div class="te big" style="margin-top:46px">“{fmt(k['question_te'])}”</div>
<div class="te sm" style="margin-top:46px">నా సమాధానం కోసం Swipe చేయండి 👉</div>""")
    s.append(f"""<div class="te" style="font-size:40px;color:#6B7280">నా సమాధానం:</div>
<div class="ans" style="margin-top:22px"><div class="te big" style="font-size:76px">“{fmt(k['answer_te'])}”</div></div>
<div class="te mid" style="margin-top:56px">{fmt(k['why_te'])}</div>
<div class="te sm" style="margin-top:26px">{fmt(k['why_detail_te'])}</div>""")
    steps = "".join(f'<div class="step te"><div class="ic">{H.escape(x["icon"])}</div><div>{fmt(x["te"])}</div></div>'
                    for x in k["steps"])
    s.append(f"""<div class="te" style="font-size:66px;line-height:1.5">{fmt(k['steps_title_te'])} 👇</div>
<div class="card" style="margin-top:40px">{steps}</div>""")
    s.append(f"""<div class="chip te" style="background:#EEF9E6;color:#3F7A12">💡 ఒక్క విషయం గుర్తుంచుకోండి</div>
<div class="te big" style="font-size:76px;margin-top:46px">{fmt(k['remember_te'])}</div>""")
    s.append(f"""<div class="te" style="font-size:68px;line-height:1.5;text-align:center">{fmt(k['cta_question_te'])}</div>
<div style="text-align:center;margin-top:44px"><span class="dm te">💬 DM చేయండి “{H.escape(k['dm_keyword'])}”</span></div>
<div class="te sm" style="text-align:center;margin-top:22px">No Pressure. Just a Conversation. 🙏</div>
<div class="contact" id="contact"><div class="n">{CONTACT_NAME}</div>
<div class="d">Call / WhatsApp: {CONTACT_PHONE}</div><div class="d">{CONTACT_EMAIL}</div></div>""")
    return s


MEASURE = """() => {
  const r = {fontsTel: document.fonts.check('700 40px Tel', 'తెలుగు'), fontsPop: document.fonts.check('700 40px Pop', 'Nutri'), overflow: []};
  const W = 1080, H = 1350;
  for (const el of document.querySelectorAll('.te,.card,.ans,.contact,.chip,.dm,.foot,.head')) {
    const b = el.getBoundingClientRect();
    if (b.left < 0 || b.top < 0 || b.right > W + .5 || b.bottom > H + .5 || el.scrollWidth > el.clientWidth + 1)
      r.overflow.push({cls: el.className, text: (el.textContent||'').slice(0,40)});
  }
  const m = document.getElementById('main').getBoundingClientRect();
  const kids = [...document.getElementById('main').children].map(e => e.getBoundingClientRect());
  r.contentTop = Math.min(...kids.map(b => b.top)); r.contentBottom = Math.max(...kids.map(b => b.bottom));
  if (r.contentTop < m.top - 1 || r.contentBottom > m.bottom + 1) r.overflow.push({cls: 'main', text: 'content taller than slide area'});
  const L = document.getElementById('logo').getBoundingClientRect(); r.logo = {w: L.width, h: L.height};
  const c = document.getElementById('contact'); r.contact = c ? c.innerText : null;
  return r;
}"""


def main():
    c = json.load(open(sys.argv[1], encoding="utf-8"))
    k = c["carousel"]
    out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    errs = []
    if not (3 <= len(k["steps"]) <= 4):
        errs.append("steps must have 3-4 items")
    if not re.fullmatch(r"[A-Z]{3,12}", k["dm_keyword"]):
        errs.append("dm_keyword must be one capitalised English word")
    pages = slides(k)
    qa = {"slides": []}
    with tempfile.TemporaryDirectory() as td, sync_playwright() as p:
        exe = "/usr/bin/google-chrome" if os.path.exists("/usr/bin/google-chrome") else None
        b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1350})
        for i, body in enumerate(pages, 1):
            pg.set_content(slide(i, len(pages), body))
            pg.evaluate("async () => { await Promise.all([...document.fonts].map(f => f.load())); await document.fonts.ready; }")
            pg.wait_for_timeout(300)
            png = f"{td}/s{i}.png"
            pg.screenshot(path=png, type="png")
            m = pg.evaluate(MEASURE)
            qa["slides"].append(m)
            if not (m["fontsTel"] and m["fontsPop"]):
                errs.append(f"slide {i}: fonts not loaded")
            if m["overflow"]:
                errs.append(f"slide {i}: overflow {m['overflow']}")
            if abs(m["logo"]["h"] - 96) > 1:
                errs.append(f"slide {i}: logo size {m['logo']}")
            if i == len(pages):
                want = f"{CONTACT_NAME}\nCall / WhatsApp: {CONTACT_PHONE}\n{CONTACT_EMAIL}"
                if (m["contact"] or "").strip() != want:
                    errs.append(f"contact mismatch: {m['contact']!r}")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", png, "-q:v", "2", str(out / f"carousel_{i}.jpg")], check=True)
        b.close()
    qa["errors"] = errs
    json.dump(qa, open(out / "carousel_qa.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("CAROUSEL: " + ("PASS" if not errs else "FAIL\n" + "\n".join(errs)))
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
