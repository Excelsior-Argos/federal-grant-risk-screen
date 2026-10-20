"""Record the demo video: the manual way first, then the same job in the live tool.

Run:  .venv\\Scripts\\python demo\\record_demo.py
Needs Playwright (pip install playwright, then: python -m playwright install chromium), numpy, scipy and
ffmpeg. Writes demo/demo.mp4. The browser is real and both sites are live, so nothing is staged.
While recording it logs each click, keystroke and slide to raw/events.json, and soundtrack.py builds
the music and sound effects to match.
"""
import json
import shutil
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

import soundtrack

SITE = "https://federal-grant-risk-screen-hufggeccbygdeedg.mexicocentral-01.azurewebsites.net"
REPO = "github.com/Excelsior-Argos/federal-grant-risk-screen"
EMPORIA = "546001262"
SUMMARY = "https://app.fac.gov/dissemination/summary/2024-06-GSAFAC-0000426782"
W, H = 1600, 900
HERE = Path(__file__).parent
RAW = HERE / "raw"

EVENTS, MARKS, CUTS = [], {}, []  # CUTS: (start, end) of page loads, cut out afterwards
T0 = [0.0]


def now():
    return time.monotonic() - T0[0]


def log(kind, at=None, **extra):
    EVENTS.append({"t": round(now() if at is None else at, 3), "kind": kind, **extra})


def cut_from(start):
    """Drop the stretch from start until now from the final video: a page loading is dead air."""
    CUTS.append((start, now()))


def on_final_timeline(t):
    return t - sum(min(end, t) - start for start, end in CUTS if t > start)


# A fake mouse pointer, a caption bar, a BEFORE/AFTER badge and a spotlight, drawn on top of every page.
OVERLAY = """
(() => {
  const css = `
    #demo-cur { position: fixed; z-index: 2147483647; width: 26px; height: 26px; margin: -13px 0 0 -13px;
      border-radius: 50%; background: rgba(31,78,121,.35); border: 3px solid #fff;
      box-shadow: 0 0 0 2px rgba(31,78,121,.9), 0 4px 12px rgba(0,0,0,.3); pointer-events: none;
      left: -100px; top: -100px; transition: transform .12s; }
    #demo-cur.down { transform: scale(.65); background: rgba(217,119,6,.65); }
    #demo-cap { position: fixed; z-index: 2147483646; left: 50%; bottom: 34px;
      transform: translate(-50%, 20px); opacity: 0; max-width: 1180px; background: rgba(15,23,42,.95);
      color: #fff; border-radius: 14px; padding: 15px 28px 17px; font: 500 26px/1.38 "Segoe UI", system-ui;
      text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,.35); pointer-events: none;
      transition: opacity .25s, transform .35s cubic-bezier(.2,.9,.3,1.2); }
    #demo-cap.on { opacity: 1; transform: translate(-50%, 0); }
    #demo-cap small { display: block; font-size: 15px; font-weight: 700; letter-spacing: .1em;
      text-transform: uppercase; color: #FBBF24; margin-bottom: 3px; }
    #demo-badge { position: fixed; z-index: 2147483646; top: 14px; left: 50%; transform: translateX(-50%);
      color: #fff; font: 700 15px/1 "Segoe UI", system-ui; letter-spacing: .08em; text-transform: uppercase;
      padding: 9px 16px; border-radius: 999px; pointer-events: none; box-shadow: 0 4px 14px rgba(0,0,0,.25); }
    .demo-ring { position: fixed; z-index: 2147483645; border: 4px solid #F59E0B; border-radius: 12px;
      box-shadow: 0 0 0 5000px rgba(15,23,42,.42), 0 0 24px 6px rgba(245,158,11,.55); pointer-events: none;
      animation: demo-ring-in .45s cubic-bezier(.2,.9,.3,1.3) both; }
    @keyframes demo-ring-in { from { opacity: 0; transform: scale(1.25); } to { opacity: 1; transform: none; } }
  `;
  function ensure() {
    if (!document.body || document.getElementById('demo-cur')) return;
    const s = document.createElement('style'); s.textContent = css; document.head.appendChild(s);
    for (const id of ['demo-cur', 'demo-cap', 'demo-badge']) {
      const d = document.createElement('div'); d.id = id; document.body.appendChild(d);
    }
    document.getElementById('demo-badge').style.display = 'none';
  }
  window.__demo = {
    ensure,
    caption(text, step) {
      ensure(); const c = document.getElementById('demo-cap');
      if (!text) { c.classList.remove('on'); return; }
      c.classList.remove('on'); void c.offsetWidth;
      c.innerHTML = (step ? `<small>${step}</small>` : '') + text; c.classList.add('on');
    },
    badge(text, color) {
      ensure(); const b = document.getElementById('demo-badge');
      b.textContent = text; b.style.background = color; b.style.display = 'block';
    },
    ring(x, y, w, h) {
      ensure(); this.unring(); const r = document.createElement('div'); r.className = 'demo-ring';
      Object.assign(r.style, {left: (x - 8) + 'px', top: (y - 8) + 'px', width: (w + 16) + 'px', height: (h + 16) + 'px'});
      document.body.appendChild(r);
    },
    unring() { document.querySelectorAll('.demo-ring').forEach(r => r.remove()); },
  };
  const move = e => { ensure(); const c = document.getElementById('demo-cur');
    if (c) { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; } };
  document.addEventListener('mousemove', move, true);
  document.addEventListener('mousedown', () => document.getElementById('demo-cur')?.classList.add('down'), true);
  document.addEventListener('mouseup', () => document.getElementById('demo-cur')?.classList.remove('down'), true);
  document.addEventListener('DOMContentLoaded', ensure);
})();
"""

CARD_CSS = """
* { box-sizing: border-box; }
body { margin: 0; width: 1600px; height: 900px; display: flex; align-items: center; justify-content: center;
  font-family: "Segoe UI", system-ui, sans-serif; color: #0F172A; overflow: hidden;
  background: radial-gradient(circle at 15% 20%, #E3ECF7 0, transparent 40%),
              radial-gradient(circle at 85% 80%, #EAF1E6 0, transparent 40%), #F6F8FB; }
body.dark { background: radial-gradient(circle at 30% 30%, #24476B 0, transparent 50%), #0F2236; color: #fff; }
.card { width: 1300px; position: relative; }
.kicker { font-size: 20px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: #1F4E79; }
h1 { font-size: 68px; margin: 10px 0 16px; line-height: 1.08; }
h2 { font-size: 44px; margin: 6px 0 26px; line-height: 1.15; }
p { font-size: 28px; line-height: 1.45; color: #334155; margin: 0 0 12px; }
.dark p { color: #CBD5E1; } .dark .kicker { color: #7DD3FC; }
.muted { color: #64748B; font-size: 20px; }
.center { text-align: center; }
.a { opacity: 0; animation: rise .6s cubic-bezier(.2,.8,.2,1) forwards; }
@keyframes rise { from { opacity: 0; transform: translateY(26px); } to { opacity: 1; transform: none; } }
.pop { opacity: 0; animation: popin .5s cubic-bezier(.2,.9,.3,1.4) forwards; }
@keyframes popin { from { opacity: 0; transform: scale(.6); } to { opacity: 1; transform: none; } }
.wipe { position: fixed; inset: 0; z-index: 10; animation: wipe .7s cubic-bezier(.7,0,.2,1) forwards; }
@keyframes wipe { from { transform: translateX(0); } to { transform: translateX(101%); } }
.letters span { display: inline-block; opacity: 0; animation: drop .55s cubic-bezier(.2,.9,.3,1.3) forwards; }
@keyframes drop { from { opacity: 0; transform: translateY(-40px) rotate(-6deg); } to { opacity: 1; transform: none; } }
table { width: 100%; border-collapse: collapse; font-size: 25px; background: #fff;
  box-shadow: 0 2px 14px rgba(15,23,42,.08); border-radius: 14px; overflow: hidden; }
td, th { padding: 15px 22px; border-bottom: 1px solid #E2E8F0; text-align: left; vertical-align: top; position: relative; }
th { background: #EEF2F7; font-size: 18px; text-transform: uppercase; letter-spacing: .05em; color: #475569; }
.stamp { position: absolute; right: 26px; top: 6px; opacity: 0; border: 5px solid #B42318; color: #B42318;
  font: 900 30px/1 "Segoe UI", system-ui; letter-spacing: .12em; padding: 8px 14px; border-radius: 8px;
  background: rgba(255,255,255,.85); animation: stamp .35s cubic-bezier(.3,1.6,.5,1) forwards; }
@keyframes stamp { from { opacity: 0; transform: scale(2.6) rotate(-16deg); }
  to { opacity: 1; transform: scale(1) rotate(-9deg); } }
.shake { animation: shake .35s linear; }
@keyframes shake { 20% { transform: translate(-6px, 3px); } 40% { transform: translate(5px, -3px); }
  60% { transform: translate(-3px, 2px); } 80% { transform: translate(2px, -1px); } }
.glow { animation: glow 1.2s ease-in-out infinite alternate; }
@keyframes glow { from { background: #fff; } to { background: #FEF3C7; } }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px 28px; }
.box { background: #fff; border-radius: 16px; padding: 22px 26px; box-shadow: 0 2px 14px rgba(15,23,42,.08);
  border-left: 6px solid #1F4E79; }
.box b { display: block; font-size: 26px; margin-bottom: 6px; color: #1F4E79; }
.box span { font-size: 21px; color: #334155; line-height: 1.45; }
.typed { min-height: 70px; } .typed::after { content: "|"; color: #1F4E79; animation: blink 1s steps(1) infinite; }
@keyframes blink { 50% { opacity: 0; } }
.big-num { font-size: 170px; font-weight: 800; color: #1F4E79; line-height: 1; font-variant-numeric: tabular-nums; }
.cups { font-size: 64px; min-height: 84px; letter-spacing: 4px; }
.cups span { display: inline-block; animation: popin .3s cubic-bezier(.2,.9,.3,1.4) both; }
.flow { display: flex; align-items: center; justify-content: center; gap: 0; margin: 10px 0 34px; }
.node { width: 190px; min-height: 118px; background: #fff; border-radius: 16px; padding: 16px 14px;
  box-shadow: 0 3px 16px rgba(15,23,42,.10); text-align: center; border-top: 6px solid #1F4E79; }
.node b { display: block; font-size: 22px; color: #0F172A; margin-bottom: 4px; }
.node span { font-size: 17px; color: #475569; line-height: 1.35; display: block; }
.node.ai { border-top-color: #D97706; } .node.human { border-top-color: #059669; }
.arrow { width: 46px; height: 4px; background: #94A3B8; position: relative; transform-origin: left;
  transform: scaleX(0); animation: draw .35s ease-out forwards; }
.arrow::after { content: ""; position: absolute; right: -2px; top: -6px; border: 8px solid transparent;
  border-left: 11px solid #94A3B8; border-right: 0; }
@keyframes draw { to { transform: scaleX(1); } }
.stats { display: flex; gap: 28px; justify-content: center; }
.stat { background: #fff; border-radius: 16px; padding: 18px 30px; box-shadow: 0 3px 16px rgba(15,23,42,.10);
  text-align: center; min-width: 360px; }
.stat b { font-size: 56px; color: #059669; font-variant-numeric: tabular-nums; }
.stat span { display: block; font-size: 20px; color: #475569; }
"""


def card(page, body, seconds, sfx=(), script="", dark=False, wipe="#1F4E79"):
    """Show one full-screen slide. sfx lists (delay, kind[, gain]) timed to the slide's own animations."""
    page.set_content(f"<html><head><style>{CARD_CSS}</style></head><body class='{'dark' if dark else ''}'>"
                     f"<div class='wipe' style='background:{wipe}'></div>{body}<script>{script}</script></body></html>")
    start = now()
    page.evaluate("window.__demo && window.__demo.ensure()")
    page.mouse.move(-50, -50)
    log("whoosh", start)
    for delay, kind, *gain in sfx:
        log(kind, start + delay, **({"gain": gain[0]} if gain else {}))
    time.sleep(seconds)


def caption(page, text, step=None, seconds=None):
    page.evaluate("([t, s]) => window.__demo.caption(t, s)", [text, step])
    time.sleep(seconds if seconds is not None else 1.4 + len(text.split()) / 3.3)


def badge(page, before):
    page.evaluate("window.__demo.ensure()")
    if before:
        page.evaluate("window.__demo.badge('Before · the manual way', '#B42318')")
    else:
        page.evaluate("window.__demo.badge('After · Federal Grant Risk Screen', '#1F4E79')")


def point(page, locator, steps=18):
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y, steps=steps)
    time.sleep(0.15)
    return x, y


def click(page, locator, pause=0.4):
    point(page, locator)
    log("click")
    page.mouse.down()
    time.sleep(0.06)
    page.mouse.up()
    time.sleep(pause)


def type_text(page, text, delay=0.06):
    for ch in text:
        page.keyboard.type(ch)
        log("key", pan=0.15)
        time.sleep(delay)


def ring(page, locator):
    box = locator.bounding_box()
    page.evaluate("b => window.__demo.ring(b.x, b.y, b.width, b.height)", box)
    log("swoosh")


def unring(page):
    page.evaluate("window.__demo.unring()")


def scroll(page, pixels, x=900, y=450):
    page.mouse.move(x, y, steps=6)
    step = 80 if pixels > 0 else -80
    for _ in range(abs(pixels) // 80):
        page.mouse.wheel(0, step)
        time.sleep(0.02)
    time.sleep(0.35)


def streamlit_ready(page, text, cut_start=None, timeout=90000):
    page.get_by_text(text).first.wait_for(timeout=timeout)
    page.wait_for_function("!document.querySelector('[data-testid=stStatusWidget]')", timeout=timeout)
    time.sleep(0.3)
    if cut_start is not None:
        cut_from(cut_start)


# ---------------------------------------------------------------------------------------------

def warm_up(browser):
    """Visit the live pages once without recording, so the site's caches are full."""
    page = browser.new_page(viewport={"width": W, "height": H})
    for url in [SITE + "/", f"{SITE}/?locality={EMPORIA}", SITE + "/?agency=Department+of+Social+Services"]:
        page.goto(url)
        page.get_by_text("Federal Grant Risk Screen").first.wait_for(timeout=120000)
        time.sleep(6)
    page.close()


def opening(page):
    title = "Federal Grant Risk Screen"
    letters = "".join(f'<span style="animation-delay:{0.3 + i * 0.035:.3f}s">{c if c != " " else "&nbsp;"}</span>'
                      for i, c in enumerate(title))
    card(page, f"""<div class="card center">
        <div class="kicker a" style="animation-delay:.15s">A portfolio demo</div>
        <h1 class="letters" style="font-size:84px">{letters}</h1>
        <p class="a" style="animation-delay:1.5s">188 audits. One grants monitor. Let's even the odds.</p></div>""",
         5.0, sfx=[(1.5, "pop", 0.6)])
    boxes = [("Evaluate each one's risk", "using its past audit results", "2 CFR 200.332"),
             ("Check its single audit", "on file, and filed within nine months", "2 CFR 200.512"),
             ("Follow up on findings", "that hit the agency's own grants", "2 CFR 200.332"),
             ("Issue a written decision", "on each one, within six months", "2 CFR 200.521")]
    grid = "".join(f'<div class="box pop" style="animation-delay:{0.6 + i * 0.45:.2f}s"><b>{t}</b>'
                   f'<span>{d} <span class="muted" style="font-size:17px">({c})</span></span></div>'
                   for i, (t, d, c) in enumerate(boxes))
    card(page, f"""<div class="card">
        <div class="kicker a" style="animation-delay:.2s">The rule</div>
        <h2 class="a" style="animation-delay:.3s">Pass federal grant money to a city or county, and you must:</h2>
        <div class="grid">{grid}</div>
        <p class="muted a" style="margin-top:24px;animation-delay:2.6s">Our example: a monitor at Virginia's Department
        of Criminal Justice Services (DCJS) checking the City of Emporia.</p></div>""",
         7.6, sfx=[(0.6 + i * 0.45, "pop") for i in range(4)])


def before(page):
    MARKS["before"] = now()
    card(page, """<div class="card center">
        <div class="kicker a" style="color:#B42318;animation-delay:.3s">Before</div>
        <h1 class="a" style="font-size:100px;animation-delay:.4s">The manual way</h1>
        <p class="a" style="animation-delay:1.0s">(you may want a coffee ☕)</p></div>""", 2.6, wipe="#B42318")

    start = now()
    page.goto("https://app.fac.gov/dissemination/search/", wait_until="networkidle")
    cut_from(start)
    badge(page, True)
    caption(page, "Search the Federal Audit Clearinghouse for the city.", "Step 1 · Find the audit", 0.3)
    click(page, page.get_by_role("button", name="Name (Entity, Auditee, or Auditor)"), 0.2)
    click(page, page.locator("#input_entity-name"), 0.1)
    type_text(page, "Emporia")
    click(page, page.locator("label[for=audit-year-2024]"), 0.1)
    click(page, page.get_by_role("button", name="State"), 0.2)
    point(page, page.locator("#auditee_state"))
    log("click")
    page.select_option("#auditee_state", "VA")
    time.sleep(0.3)
    scroll(page, -2000, 250, 450)
    with page.expect_navigation(wait_until="networkidle"):
        click(page, page.locator("input[type=submit][value=Search]").first, 0.1)
        start = now()
    cut_from(start)
    badge(page, True)
    caption(page, "Found it: Emporia's 2024 audit.", "Step 1 · Find the audit", 1.6)
    # The View link opens a new tab; show the click, then open the page in this tab so it stays on camera.
    point(page, page.locator(f"a[href='{SUMMARY.replace('https://app.fac.gov', '')}']").first)
    log("click")
    page.evaluate("document.getElementById('demo-cur').classList.add('down')")
    time.sleep(0.15)
    start = now()
    page.goto(SUMMARY, wait_until="networkidle")
    cut_from(start)
    badge(page, True)
    scroll(page, 1280)
    ring(page, page.locator("text=Findings:").first.locator("xpath=.."))
    caption(page, "The FAC says: 5 findings. Which ones? On whose grant? It won't say.", "Step 2 · Read the findings")
    unring(page)
    scroll(page, -1280)
    report = page.get_by_text("Single audit report").first
    ring(page, report)
    point(page, report)
    caption(page, "So you download the full audit report and go digging.", "Step 2 · Read the findings")
    unring(page)

    rows = [("Fiscal year ended", "June 30, 2024", ""),
            ("Audit due (nine months later)", "March 31, 2025", ""),
            ("Accepted by the FAC", "Sept. 8, 2026", "LATE"),
            ("Next audit, due March 31, 2026", "Not on file", "OVERDUE"),
            ("Your written decision is due", "March 8, 2027", "")]
    cells = ""
    for i, (label, value, stamp) in enumerate(rows):
        mark = f'<span class="stamp" style="animation-delay:{2.7 + (i - 2) * 0.8:.1f}s">{stamp}</span>' if stamp else ""
        glow = ' class="glow"' if i == 4 else ""
        cells += (f'<tr class="a" style="animation-delay:{0.4 + i * 0.35:.2f}s"><td{glow}>{label}</td>'
                  f'<td{glow}>{value}{mark}</td></tr>')
    card(page, f"""<div class="card" id="c">
        <div class="kicker a" style="animation-delay:.1s">Step 3 · Do the date math</div>
        <h2 class="a" style="animation-delay:.2s">City of Emporia, 2024 audit</h2>
        <table>{cells}</table></div>""", 6.8,
         sfx=[(0.4 + i * 0.35, "pop", 0.5) for i in range(5)] + [(2.75, "stamp"), (3.55, "stamp")],
         script="const c = document.getElementById('c');"
                "[2700, 3500].forEach(t => setTimeout(() => { c.classList.remove('shake'); void c.offsetWidth;"
                " c.classList.add('shake'); }, t + 60));")

    concerns = "5 findings on DCJS grants, all material weaknesses, 1 repeat. Filed late; next audit overdue."
    per_char, type_start = 0.032, 0.7
    card(page, f"""<div class="card">
        <div class="kicker a" style="animation-delay:.1s">Step 4 · Fill in the risk form</div>
        <h2 class="a" style="animation-delay:.2s">DCJS grant risk assessment: the audit rows</h2>
        <table class="a" style="animation-delay:.3s">
          <tr><th style="width:24%">Row</th><th>Answer</th><th style="width:11%">Points</th></tr>
          <tr><td>Single-Audit</td><td>Yes</td><td>0</td></tr>
          <tr><td>Audit Opinion</td><td>Audit performed on a DCJS program and Unmodified</td><td>0</td></tr>
          <tr><td>Concerns</td><td colspan="2"><div class="typed" id="t"></div></td></tr>
        </table>
        <p class="muted a" style="margin-top:16px;animation-delay:.4s">Simplified from DCJS's published risk
        assessment spreadsheet.</p></div>""", 5.8,
         sfx=[(type_start + i * per_char, "key", 0.8) for i in range(0, len(concerns), 2)],
         script=f"const s = {concerns!r}; let i = 0; setTimeout(function tick() {{"
                f" document.getElementById('t').textContent = s.slice(0, ++i);"
                f" if (i < s.length) setTimeout(tick, {per_char * 1000:.0f}); }}, {type_start * 1000:.0f});")

    # Count from 1 to 188, slowly then faster, with a coffee cup for every 20 done.
    values, delays, n, t = [], [], 1, 1.1
    while n < 188:
        n = min(188, n + max(1, (188 - n) // 9 if n > 20 else 2))
        t += 0.17 if n < 20 else 0.07
        values.append(n)
        delays.append(round(t, 3))
    card(page, f"""<div class="card center">
        <div class="kicker a" style="animation-delay:.1s">Step 5 · Repeat</div>
        <div class="big-num a" style="animation-delay:.2s"><span id="n">1</span>
          <span style="font-size:64px;color:#64748B">of 188</span></div>
        <div class="cups" id="cups"></div>
        <p class="a" style="animation-delay:.5s">Every DCJS subrecipient in the FAC. Then again next year.</p></div>""",
         6.0, sfx=[(d, "tick", 0.7) for d in delays] + [(delays[-1] + 0.05, "pop")],
         script=f"const v = {values}, d = {delays}; let cups = 0;"
                "v.forEach((n, i) => setTimeout(() => { document.getElementById('n').textContent = n;"
                " while (cups < Math.floor(n / 20)) { cups++; const s = document.createElement('span');"
                " s.textContent = '☕'; document.getElementById('cups').appendChild(s); } }, d[i] * 1000));")


def after(page):
    MARKS["after"] = now()
    card(page, """<div class="card center">
        <div class="kicker a" style="animation-delay:.3s">After</div>
        <h1 class="a" style="font-size:96px;animation-delay:.4s">Federal Grant Risk Screen</h1>
        <p class="a" style="animation-delay:.9s">Same job. All 188 at once. Coffee optional.</p></div>""",
         2.8, dark=True, wipe="#F59E0B")

    start = now()
    page.goto(SITE + "/")
    streamlit_ready(page, "Needs your attention", start)
    badge(page, False)
    log("chime")
    caption(page, "Pick your agency. Every subrecipient's audits are already checked.", "Live site")
    tile = page.locator(".kpi").nth(1)
    ring(page, tile)
    point(page, tile)
    caption(page, "7 of 188 have findings on DCJS's own grants. They go first.", "Live site")
    unring(page)
    late = page.get_by_text("Late or missing audits").first
    late.scroll_into_view_if_needed()
    log("swoosh", gain=0.6)
    time.sleep(0.4)
    ring(page, page.locator("[data-testid=stDataFrame]").first)
    caption(page, "No findings, but filed late or overdue? They get their own list.", "Live site")
    unring(page)
    scroll(page, -3000)
    emporia = page.locator("[data-testid=stHorizontalBlock]", has_text="CITY OF EMPORIA").first
    ring(page, emporia)
    caption(page, "Each card: risk rating, problem areas, decision due date.", "Live site", 2.6)
    unring(page)
    click(page, emporia.get_by_role("button", name="Open"), 0.15)
    streamlit_ready(page, "What to check next", now())
    badge(page, False)
    ring(page, page.locator(".quote").first)
    caption(page, "AI drafts the summary and quotes the auditor. Code checks every quote word for word.", "Summary")
    caption(page, "And a person approves it before it shows up here.", "Summary", 2.4)
    unring(page)

    click(page, page.get_by_role("tab", name="Audit checks"), 0.6)
    caption(page, "The date math from step 3, done by code.", "Audit checks", 2.6)
    scroll(page, 480)
    click(page, page.get_by_text("How this fills in the state risk forms"), 0.5)
    scroll(page, 400)
    caption(page, "Step 4's form rows, filled in for DCJS, VDEM and North Carolina. No AI.", "Audit checks")
    scroll(page, -2000)

    click(page, page.get_by_role("tab", name="Findings"), 0.5)
    click(page, page.get_by_text("What the auditor found").first, 0.4)
    caption(page, "Every finding: whose grant it hit, and the auditor's full text.", "Findings")
    scroll(page, -2000)

    click(page, page.get_by_role("button", name="Back to the DCJS worklist"), 0.15)
    streamlit_ready(page, "Needs your attention", now())
    badge(page, False)
    click(page, page.locator("[data-testid=stSidebar] [data-testid=stSelectbox]").first, 0.2)
    type_text(page, "Social", 0.07)
    log("click")
    page.keyboard.press("Enter")
    time.sleep(0.2)
    streamlit_ready(page, "Needs your attention", now())
    badge(page, False)
    log("chime", gain=0.7)
    caption(page, "Switch agency, and Social Services gets its own list and deadlines.", "Live site")


def closing(page):
    MARKS["end_card"] = now()
    nodes = [("FAC API", "6 tables of public audit data", ""), ("Postgres", "on Neon", ""),
             ("Claude", "drafts the risk summary", "ai"), ("Quote check", "code rejects any quote not in the audit", ""),
             ("Approval", "a person signs off (LangGraph)", "human"), ("Live page", "Streamlit on Azure", "")]
    flow = ""
    for i, (name, note, kind) in enumerate(nodes):
        if i:
            flow += f'<div class="arrow" style="animation-delay:{0.35 + i * 0.4:.2f}s"></div>'
        flow += (f'<div class="node pop {kind}" style="animation-delay:{0.2 + i * 0.4:.2f}s">'
                 f'<b>{name}</b><span>{note}</span></div>')
    card(page, f"""<div class="card">
        <div class="kicker a" style="animation-delay:.05s">Under the hood</div>
        <div class="flow">{flow}</div>
        <p class="center a" style="font-size:22px;animation-delay:2.6s">Plus an MCP server, so an AI assistant can look
        up the same findings. Deployed by GitHub Actions.</p>
        <div class="stats a" style="animation-delay:3.0s;margin-top:26px">
          <div class="stat"><b><span id="s1">0</span> / 30</b><span>AI ratings matched the hand rating</span></div>
          <div class="stat"><b><span id="s2">0</span> / 110</b><span>quotes found word for word</span></div>
        </div></div>""", 8.2,
         sfx=[(0.2 + i * 0.4, "pop", 0.6) for i in range(6)] + [(3.0, "sparkle")],
         script="function up(id, to, ms) { let n = 0; const step = Math.max(1, Math.round(to / 20));"
                " const t = setInterval(() => { n = Math.min(to, n + step); document.getElementById(id).textContent = n;"
                " if (n >= to) clearInterval(t); }, ms / 20); }"
                "setTimeout(() => { up('s1', 29, 900); up('s2', 110, 900); }, 3100);")
    MARKS["end"] = now()
    card(page, f"""<div class="card center">
        <h1 class="a" style="animation-delay:.2s">Federal Grant Risk Screen</h1>
        <p class="a" style="font-size:24px;animation-delay:.6s">Try it: {SITE.replace('https://', '')}</p>
        <p class="a" style="font-size:24px;animation-delay:.8s">Code: {REPO}</p>
        <p class="muted a" style="margin-top:30px;animation-delay:1.2s">A portfolio project, not affiliated with DCJS,
        VDSS or any Virginia agency. Data from the Federal Audit Clearinghouse.</p></div>""", 6.0)


def main():
    if RAW.exists():
        shutil.rmtree(RAW)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        warm_up(browser)
        context = browser.new_context(viewport={"width": W, "height": H}, record_video_dir=str(RAW),
                                      record_video_size={"width": W, "height": H},
                                      bypass_csp=True)  # fac.gov's security policy would block the captions
        context.add_init_script(OVERLAY)
        page = context.new_page()
        T0[0] = time.monotonic()
        page.set_default_timeout(60000)
        opening(page)
        before(page)
        after(page)
        closing(page)
        context.close()
        browser.close()

    video = next(RAW.glob("*.webm"))
    duration = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                     str(video)], capture_output=True, text=True, check=True).stdout)
    keep = [e for e in EVENTS if not any(a < e["t"] < b for a, b in CUTS)]
    final = {"duration": on_final_timeline(duration), "cuts": CUTS,
             "marks": {k: on_final_timeline(v) for k, v in MARKS.items()},
             "events": [{**e, "t": round(on_final_timeline(e["t"]), 3)} for e in keep]}
    (RAW / "events.json").write_text(json.dumps(final, indent=1))
    audio = soundtrack.build(RAW / "events.json", RAW / "soundtrack.wav")
    dropped = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in CUTS)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(audio),
                    "-vf", f"fps=25,select='not({dropped})',setpts=N/25/TB,scale=1920:1080:flags=lanczos",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-af", "loudnorm=I=-16:TP=-3:LRA=11,alimiter=limit=0.7:level=disabled", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart", str(HERE / "demo.mp4")], check=True)
    print(f"Wrote {HERE / 'demo.mp4'} ({final['duration']:.0f} s, {duration - final['duration']:.1f} s of loading cut)")


if __name__ == "__main__":
    main()
