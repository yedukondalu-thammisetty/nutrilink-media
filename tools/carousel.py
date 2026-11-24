"""Picture-rich, conversation-style Instagram carousel for NutriLink By NutriiGlow (1080x1350 slides).

Usage: python3 tools/carousel.py posts/<date>/content.json posts/<date>
Writes carousel_1.jpg ... carousel_N.jpg (N = 7 or 8) and carousel_qa.json, and exits non-zero if any
check fails (fonts, overflow, logo, contact card, missing 3D pictures). Uses the locked logo, fonts and
contact constants from render.py and the 3D Fluent emoji pictures in tools/icons/fluent3d.

Look (modelled on popular Telugu wellness-coach carousels): warm cream background, dark-brown and
green Telugu headings, ornament dividers, and on every slide 3D pictures that SHOW what the words say
(a dal post shows dal, onion, tomato, chilli; a sleep post shows a bed and a sleeping face).

content.json "carousel" block:
  question_te      the question people ask (cover)                 e.g. "రోజూ ఎంత సేపు [[Walking]] చేయాలి?"
  cover_icons      3-5 emoji pictured on the cover                  e.g. ["🚶‍♀️", "👟", "⏱️", "🌳"]
  answer_te        the coach's short answer                         e.g. "రోజూ {{30 నిమిషాలు}} చాలు!"
  why_te           one-line reason
  why_detail_te    1-2 short sentences
  answer_icons     2-4 emoji pictured on the answer slide
  steps            3-4 items, ONE SLIDE EACH:
                     {"icon": "<emoji>", "title": "<1-3 words, Tenglish ok, e.g. Protein / నిద్ర>",
                      "subtitle_te": "<one line, e.g. తగినంత Protein…>",
                      "points": ["<2-3 short benefit/how-to lines>"],
                      "icons": ["<3-5 emoji pictured at the bottom>"]}
  remember_te      key takeaway
  remember_icons   2-3 emoji
  cta_question_te  question on the last slide
  dm_keyword       one English word in capitals                     e.g. "WALK"
Every emoji must be something you can SEE that matches the words (food, people doing the action,
objects). Wrap words in [[ ]] for a green highlight and {{ }} for a brown-red word with a yellow
brush underline. "\n" is a line break.
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
from icons import icon_uri  # noqa: E402
from render import (BRAND_COLORS, CONTACT_EMAIL, CONTACT_NAME, CONTACT_PHONE, IG_HANDLE, LOGO_PNG,  # noqa: E402
                    _b64, font_css)

YT_HANDLE = "@NutriLinkWellnessPlatform"
TEAL, BLUE = BRAND_COLORS["teal"], BRAND_COLORS["blue"]
BROWN, GREEN, RED, CREAM = "#3B2314", "#2F6B1F", "#A3361A", "#F4EEE4"
missing_icons = []


def fmt(s):
    s = H.escape(s)
    s = re.sub(r"\[\[(.+?)\]\]", r'<span class="g">\1</span>', s)
    s = re.sub(r"\{\{(.+?)\}\}", r'<span class="r">\1</span>', s)
    return s.replace("\n", "<br>")


def img(emoji, size, cls=""):
    uri, ok = icon_uri(emoji)
    if not ok:
        missing_icons.append(emoji)
    return f'<img class="ic {cls}" src="{uri}" style="width:{size}px;height:{size}px">'


def cluster(emojis, big, small):
    n = len(emojis)
    mid = n // 2
    total = big + small * (n - 1) + 6 * (n - 1)
    f = min(1.0, 900 / total)          # always fit inside the slide width
    big, small = int(big * f), int(small * f)
    imgs = "".join(img(e, big if (i == mid or n <= 2) else small) for i, e in enumerate(emojis))
    return f'<div class="cluster">{imgs}</div>'


ORN = f'''<div class="orn"><span></span><svg width="54" height="18" viewBox="0 0 54 18"><path d="M27 1 L33 9 L27 17 L21 9 Z" fill="none" stroke="{BROWN}" stroke-width="1.6"/><circle cx="12" cy="9" r="2.2" fill="{BROWN}"/><circle cx="42" cy="9" r="2.2" fill="{BROWN}"/></svg><span></span></div>'''

CSS = f"""
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:1080px;height:1350px;overflow:hidden;color:{BROWN};font-family:Pop,Tel,"Noto Color Emoji",sans-serif;position:relative;
 background:radial-gradient(ellipse at 50% 40%,#FBF8F2 0%,{CREAM} 60%,#EADFCD 100%)}}
.te{{font-family:Pop,Tel,"Noto Color Emoji";font-weight:700}}
.g{{color:{GREEN}}}
.r{{color:{RED};background:linear-gradient(transparent 78%,rgba(245,196,66,.75) 78%,rgba(245,196,66,.75) 92%,transparent 92%)}}
.head{{position:absolute;left:56px;right:56px;top:44px;display:flex;justify-content:space-between;align-items:center}}
.badge{{background:linear-gradient(150deg,{TEAL} 0%,#1690C4 55%,{BLUE} 100%);border-radius:22px;padding:10px 20px;display:flex;align-items:center;box-shadow:0 8px 22px rgba(31,114,224,.22)}}
.logo{{height:84px;width:auto;display:block}}
.pg{{background:rgba(59,35,20,.82);color:#fff;border-radius:30px;padding:8px 22px;font-size:26px;font-weight:600}}
.main{{position:absolute;left:70px;right:70px;top:168px;bottom:120px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center}}
.orn{{display:flex;align-items:center;gap:14px;margin:22px auto;width:520px}}
.orn span{{flex:1;height:2px;background:linear-gradient(90deg,transparent,{BROWN},transparent);opacity:.6}}
.cluster{{display:flex;align-items:flex-end;justify-content:center;gap:6px;margin-top:40px;position:relative;padding-bottom:18px}}
.cluster:after{{content:"";position:absolute;left:8%;right:8%;bottom:0;height:34px;border-radius:50%;background:radial-gradient(ellipse,rgba(59,35,20,.22),transparent 70%)}}
.ic{{display:block;filter:drop-shadow(0 14px 18px rgba(59,35,20,.22));position:relative;z-index:1}}
.chip{{display:inline-block;background:#fff;border:2px solid #E4D7C3;border-radius:40px;padding:10px 28px;font-size:30px;color:{GREEN}}}
.q{{font-size:78px;line-height:1.45;margin-top:30px}}
.swipe{{margin-top:26px;font-size:54px;font-weight:700}}
.lbl{{font-size:36px;color:#7A5A44}}
.ans{{font-size:76px;line-height:1.45;color:{GREEN}}}
.why{{font-size:50px;line-height:1.5}}
.detail{{font-size:32px;line-height:1.6;font-weight:500;color:#5A4030;margin-top:14px;max-width:880px}}
.title{{display:flex;align-items:center;gap:22px;font-size:100px;font-weight:700;line-height:1.2}}
.sub{{font-size:58px;line-height:1.45;color:{GREEN}}}
.pts{{margin-top:22px;display:flex;flex-direction:column;gap:18px;align-items:flex-start;text-align:left;max-width:900px}}
.pt{{display:flex;gap:22px;align-items:flex-start;font-size:46px;line-height:1.45}}
.ck{{flex:none;width:58px;height:58px;border-radius:50%;background:{GREEN};display:flex;align-items:center;justify-content:center;margin-top:6px}}
.foot{{position:absolute;left:0;right:0;bottom:40px;text-align:center;font-size:28px;font-weight:600;color:#7A5A44}}
.foot .orn{{margin:6px auto 0;width:420px}}
.dm{{display:inline-block;background:linear-gradient(90deg,{TEAL},{BLUE});color:#fff;border-radius:60px;padding:24px 56px;font-size:48px;margin-top:34px;box-shadow:0 14px 30px rgba(31,114,224,.28)}}
.contact{{margin-top:36px;background:#fff;border:2px solid #E4D7C3;border-radius:28px;padding:26px 40px;box-shadow:0 10px 26px rgba(59,35,20,.10)}}
.contact .n{{font-size:36px;font-weight:700;color:{BROWN}}} .contact .d{{font-size:30px;font-weight:600;margin-top:6px;color:#5A4030}}
"""

CHECK = '<div class="ck"><svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></div>'
YT_ICON = '<svg width="34" height="24" viewBox="0 0 34 24" style="vertical-align:-4px"><rect width="34" height="24" rx="6" fill="#FF0033"/><path d="M13.5 6.5v11l9.5-5.5z" fill="#fff"/></svg>'


def page(n, total, body):
    foot = (f'{IG_HANDLE}{ORN}' if n < total else f'{IG_HANDLE} · {YT_ICON} {YT_HANDLE}{ORN}')
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{font_css()}{CSS}</style></head><body>
<div class="head"><div class="badge"><img class="logo" id="logo" src="data:image/png;base64,{_b64(LOGO_PNG)}"></div><div class="pg">{n}/{total}</div></div>
<div class="main" id="main">{body}</div><div class="foot">{foot}</div></body></html>"""


def slides(k):
    s = [f"""<div class="chip te">👥 చాలామంది నన్ను అడిగే Question…</div>
<div class="te q">{fmt(k['question_te'])}</div>
{cluster(k['cover_icons'], 330, 230)}
<div class="swipe">👇 Swipe →</div>""",
         f"""<div class="te lbl">నా సమాధానం</div>{ORN}
<div class="te ans">“{fmt(k['answer_te'])}”</div>{ORN}
<div class="te why">{fmt(k['why_te'])}</div>
<div class="te detail">{fmt(k['why_detail_te'])}</div>
{cluster(k['answer_icons'], 270, 210)}"""]
    for st in k["steps"]:
        pts = "".join(f'<div class="pt te">{CHECK}<div>{fmt(p)}</div></div>' for p in st["points"])
        s.append(f"""<div class="title te">{img(st['icon'], 120)}<div>{fmt(st['title'])}</div></div>{ORN}
<div class="te sub">{fmt(st['subtitle_te'])}</div>
<div class="pts">{pts}</div>
{cluster(st['icons'], 270, 200)}""")
    s.append(f"""<div class="chip te">💡 ఒక్క విషయం గుర్తుంచుకోండి</div>{ORN}
<div class="te q" style="font-size:72px">{fmt(k['remember_te'])}</div>
{cluster(k['remember_icons'], 300, 230)}""")
    s.append(f"""<div class="te q" style="font-size:68px;margin-top:0">{fmt(k['cta_question_te'])}</div>
<div class="dm te">💬 DM చేయండి “{H.escape(k['dm_keyword'])}”</div>
<div class="te detail" style="margin-top:20px">No Pressure. Just a Conversation. 🙏</div>
<div class="contact" id="contact"><div class="n">{CONTACT_NAME}</div>
<div class="d">Call / WhatsApp: {CONTACT_PHONE}</div><div class="d">{CONTACT_EMAIL}</div></div>""")
    return s


MEASURE = """() => {
  const r = {fontsTel: document.fonts.check('700 40px Tel', 'తెలుగు'), fontsPop: document.fonts.check('700 40px Pop', 'Nutri'), overflow: []};
  const W = 1080, H = 1350;
  for (const el of document.querySelectorAll('.te,.cluster,.contact,.chip,.dm,.foot,.head,.pts')) {
    const b = el.getBoundingClientRect();
    if (b.left < 0 || b.top < 0 || b.right > W + .5 || b.bottom > H + .5 || el.scrollWidth > el.clientWidth + 1)
      r.overflow.push({cls: el.className, text: (el.textContent||'').slice(0,40)});
  }
  const m = document.getElementById('main').getBoundingClientRect();
  const kids = [...document.getElementById('main').children].map(e => e.getBoundingClientRect());
  const top = Math.min(...kids.map(b => b.top)), bottom = Math.max(...kids.map(b => b.bottom));
  if (top < m.top - 1 || bottom > m.bottom + 1) r.overflow.push({cls: 'main', text: `content taller than slide area (${Math.round(bottom-top)}px > ${Math.round(m.height)}px)`});
  const L = document.getElementById('logo').getBoundingClientRect(); r.logo = {w: L.width, h: L.height};
  const imgs = [...document.querySelectorAll('img.ic')]; r.pictures = imgs.length;
  r.brokenPictures = imgs.filter(i => !i.complete || i.naturalWidth === 0).length;
  const c = document.getElementById('contact'); r.contact = c ? c.innerText : null;
  return r;
}"""


def check_content(k):
    errs = []
    need = ["question_te", "cover_icons", "answer_te", "why_te", "why_detail_te", "answer_icons", "steps",
            "remember_te", "remember_icons", "cta_question_te", "dm_keyword"]
    errs += [f"carousel.{x} missing" for x in need if x not in k]
    if errs:
        return errs
    if not (3 <= len(k["steps"]) <= 4):
        errs.append("steps must have 3-4 items")
    for i, st in enumerate(k["steps"]):
        for x in ("icon", "title", "subtitle_te", "points", "icons"):
            if x not in st:
                errs.append(f"steps[{i}].{x} missing")
        if not (2 <= len(st.get("points", [])) <= 3):
            errs.append(f"steps[{i}].points must have 2-3 lines")
        if not (3 <= len(st.get("icons", [])) <= 5):
            errs.append(f"steps[{i}].icons must have 3-5 emoji")
    if not (3 <= len(k["cover_icons"]) <= 5):
        errs.append("cover_icons must have 3-5 emoji")
    if not re.fullmatch(r"[A-Z]{3,12}", k["dm_keyword"]):
        errs.append("dm_keyword must be one capitalised English word")
    return errs


def main():
    c = json.load(open(sys.argv[1], encoding="utf-8"))
    k = c["carousel"]
    out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    errs = check_content(k)
    if errs:
        print("CAROUSEL: FAIL\n" + "\n".join(errs)); sys.exit(1)
    for old in out.glob("carousel_*.jpg"):
        old.unlink()
    pages = slides(k)
    if missing_icons:
        errs.append(f"no 3D picture for emoji {missing_icons} (use another emoji)")
    qa = {"slides": []}
    with tempfile.TemporaryDirectory() as td, sync_playwright() as p:
        exe = "/usr/bin/google-chrome" if os.path.exists("/usr/bin/google-chrome") else None
        b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1350})
        for i, body in enumerate(pages, 1):
            pg.set_content(page(i, len(pages), body))
            pg.evaluate("async () => { await Promise.all([...document.fonts].map(f => f.load())); await document.fonts.ready; }")
            pg.wait_for_timeout(400)
            png = f"{td}/s{i}.png"
            pg.screenshot(path=png, type="png")
            m = pg.evaluate(MEASURE)
            qa["slides"].append(m)
            if not (m["fontsTel"] and m["fontsPop"]):
                errs.append(f"slide {i}: fonts not loaded")
            if m["overflow"]:
                errs.append(f"slide {i}: overflow {m['overflow']}")
            if abs(m["logo"]["h"] - 84) > 1:
                errs.append(f"slide {i}: logo size {m['logo']}")
            if m["brokenPictures"]:
                errs.append(f"slide {i}: {m['brokenPictures']} pictures did not load")
            if i < len(pages) and m["pictures"] < 2:
                errs.append(f"slide {i}: needs pictures")
            if i == len(pages):
                want = f"{CONTACT_NAME}\nCall / WhatsApp: {CONTACT_PHONE}\n{CONTACT_EMAIL}"
                if (m["contact"] or "").strip() != want:
                    errs.append(f"contact mismatch: {m['contact']!r}")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", png, "-q:v", "2", str(out / f"carousel_{i}.jpg")], check=True)
        b.close()
    qa["slide_count"] = len(pages)
    qa["errors"] = errs
    json.dump(qa, open(out / "carousel_qa.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"slides: {len(pages)}")
    print("CAROUSEL: " + ("PASS" if not errs else "FAIL\n" + "\n".join(errs)))
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
