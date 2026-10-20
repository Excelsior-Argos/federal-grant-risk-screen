"""Record the demo video: the manual way first, then the same job in the live tool.

Run:  .venv\\Scripts\\python demo\\record_demo.py
Needs Playwright (pip install playwright, then: python -m playwright install chromium) and ffmpeg.
Writes demo/demo.mp4. The browser is real and the sites are live, so nothing is staged.
"""
import shutil
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

SITE = "https://federal-grant-risk-screen-hufggeccbygdeedg.mexicocentral-01.azurewebsites.net"
REPO = "github.com/Excelsior-Argos/federal-grant-risk-screen"
EMPORIA = "546001262"
W, H = 1600, 900
HERE = Path(__file__).parent
RAW = HERE / "raw"

# A fake mouse pointer, a caption bar and a BEFORE/AFTER badge, drawn on top of every page.
OVERLAY = """
(() => {
  const css = `
    #demo-cur { position: fixed; z-index: 2147483647; width: 26px; height: 26px; margin: -13px 0 0 -13px;
      border-radius: 50%; background: rgba(31,78,121,.35); border: 3px solid #fff;
      box-shadow: 0 0 0 2px rgba(31,78,121,.9), 0 4px 12px rgba(0,0,0,.3); pointer-events: none;
      left: -100px; top: -100px; transition: transform .12s; }
    #demo-cur.down { transform: scale(.7); background: rgba(217,119,6,.6); }
    #demo-cap { position: fixed; z-index: 2147483646; left: 50%; bottom: 34px; transform: translateX(-50%);
      max-width: 1180px; background: rgba(15,23,42,.94); color: #fff; border-radius: 14px;
      padding: 16px 28px 18px; font: 500 25px/1.4 "Segoe UI", system-ui, sans-serif; text-align: center;
      box-shadow: 0 10px 30px rgba(0,0,0,.35); pointer-events: none; transition: opacity .25s; }
    #demo-cap small { display: block; font-size: 16px; font-weight: 700; letter-spacing: .08em;
      text-transform: uppercase; color: #FBBF24; margin-bottom: 4px; }
    #demo-badge { position: fixed; z-index: 2147483646; top: 14px; left: 50%; transform: translateX(-50%);
      color: #fff; font: 700 15px/1 "Segoe UI", system-ui, sans-serif; letter-spacing: .08em;
      text-transform: uppercase; padding: 9px 16px; border-radius: 999px; pointer-events: none;
      box-shadow: 0 4px 14px rgba(0,0,0,.25); }
    .demo-ring { position: fixed; z-index: 2147483645; border: 4px solid #F59E0B; border-radius: 10px;
      box-shadow: 0 0 0 6px rgba(245,158,11,.25); pointer-events: none; transition: all .3s; }
  `;
  function ensure() {
    if (!document.body || document.getElementById('demo-cur')) return;
    const s = document.createElement('style'); s.textContent = css; document.head.appendChild(s);
    for (const id of ['demo-cur', 'demo-cap', 'demo-badge']) {
      const d = document.createElement('div'); d.id = id; document.body.appendChild(d);
    }
    document.getElementById('demo-cap').style.opacity = 0;
    document.getElementById('demo-badge').style.display = 'none';
  }
  window.__demo = {
    ensure,
    caption(text, step) {
      ensure(); const c = document.getElementById('demo-cap');
      if (!text) { c.style.opacity = 0; return; }
      c.innerHTML = (step ? `<small>${step}</small>` : '') + text; c.style.opacity = 1;
    },
    badge(text, color) {
      ensure(); const b = document.getElementById('demo-badge');
      if (!text) { b.style.display = 'none'; return; }
      b.textContent = text; b.style.background = color; b.style.display = 'block';
    },
    ring(x, y, w, h) {
      ensure(); const r = document.createElement('div'); r.className = 'demo-ring';
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
  font-family: "Segoe UI", system-ui, sans-serif; color: #0F172A; background: #F6F8FB; }
.card { width: 1280px; }
.kicker { font-size: 20px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: #1F4E79; }
h1 { font-size: 64px; margin: 10px 0 18px; line-height: 1.1; }
h2 { font-size: 44px; margin: 8px 0 26px; }
p { font-size: 28px; line-height: 1.5; color: #334155; margin: 0 0 14px; }
.muted { color: #64748B; font-size: 20px; }
table { width: 100%; border-collapse: collapse; font-size: 25px; background: #fff;
  box-shadow: 0 2px 10px rgba(15,23,42,.08); border-radius: 12px; overflow: hidden; }
td, th { padding: 16px 22px; border-bottom: 1px solid #E2E8F0; text-align: left; vertical-align: top; }
th { background: #EEF2F7; font-size: 19px; text-transform: uppercase; letter-spacing: .05em; color: #475569; }
tr.row { opacity: 0; transform: translateY(8px); transition: all .5s; }
tr.row.show { opacity: 1; transform: none; }
.bad { color: #B42318; font-weight: 700; }
.pill { display: inline-block; padding: 6px 14px; border-radius: 999px; font-weight: 700; font-size: 20px; }
.section { text-align: center; }
.section h1 { font-size: 92px; }
.big-num { font-size: 150px; font-weight: 800; color: #1F4E79; line-height: 1; font-variant-numeric: tabular-nums; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px 28px; }
.box { background: #fff; border-radius: 14px; padding: 20px 24px; box-shadow: 0 2px 10px rgba(15,23,42,.08); }
.box b { display: block; font-size: 24px; margin-bottom: 6px; color: #1F4E79; }
.box span { font-size: 21px; color: #334155; line-height: 1.45; }
.typed { min-height: 120px; color: #0F172A; }
.typed::after { content: "|"; color: #1F4E79; animation: blink 1s steps(1) infinite; }
@keyframes blink { 50% { opacity: 0; } }
"""


def card(page, body, seconds, script=""):
    page.set_content(f"<html><head><style>{CARD_CSS}</style></head><body>{body}"
                     f"<script>{script}</script></body></html>")
    page.evaluate("window.__demo && window.__demo.ensure()")
    page.mouse.move(-50, -50)
    time.sleep(seconds)


def caption(page, text, step=None, seconds=None):
    page.evaluate("([t, s]) => window.__demo.caption(t, s)", [text, step])
    if seconds is None:
        seconds = 1.8 + len(text.split()) / 3.2  # time to read it
    time.sleep(seconds)


def badge(page, before):
    if before:
        page.evaluate("window.__demo.badge('Before · the manual way', '#B42318')")
    else:
        page.evaluate("window.__demo.badge('After · Federal Grant Risk Screen', '#1F4E79')")


def point(page, locator, steps=28):
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y, steps=steps)
    time.sleep(0.25)
    return x, y


def click(page, locator, pause=0.6):
    x, y = point(page, locator)
    page.mouse.down()
    time.sleep(0.08)
    page.mouse.up()
    time.sleep(pause)


def ring(page, locator):
    box = locator.bounding_box()
    page.evaluate("b => window.__demo.ring(b.x, b.y, b.width, b.height)", box)


def unring(page):
    page.evaluate("window.__demo.unring()")


def scroll(page, pixels, x=900, y=450):
    page.mouse.move(x, y, steps=10)
    step = 40 if pixels > 0 else -40
    for _ in range(abs(pixels) // 40):
        page.mouse.wheel(0, step)
        time.sleep(0.025)
    time.sleep(0.5)


def streamlit_ready(page, text, timeout=90000):
    page.get_by_text(text).first.wait_for(timeout=timeout)
    page.wait_for_function("!document.querySelector('[data-testid=stStatusWidget]')", timeout=timeout)
    time.sleep(0.8)


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
    card(page, """<div class="card section">
        <div class="kicker">A portfolio demo</div>
        <h1>Federal Grant Risk Screen</h1>
        <p>How a Virginia state agency checks the federal audits of the local governments it funds:<br>
        the manual way, then with this tool.</p></div>""", 5)
    card(page, """<div class="card">
        <div class="kicker">The job</div>
        <h2>A state agency that passes federal grant money to a city or county must:</h2>
        <div class="grid">
          <div class="box"><b>Evaluate each one's risk</b><span>including the results of its past audits
            (2 CFR 200.332)</span></div>
          <div class="box"><b>Check its single audit</b><span>is on file and was filed on time, nine months after
            its year ends (2 CFR 200.512)</span></div>
          <div class="box"><b>Follow up on findings</b><span>that hit the agency's own grants, not other
            agencies' (2 CFR 200.332)</span></div>
          <div class="box"><b>Issue a written decision</b><span>on each of those findings within six months
            of the audit being filed (2 CFR 200.521)</span></div>
        </div>
        <p class="muted" style="margin-top:24px">Example: a grants monitor at Virginia's Department of Criminal
        Justice Services (DCJS) checking the City of Emporia.</p></div>""", 11)


def before(page):
    card(page, """<div class="card section"><div class="kicker" style="color:#B42318">Before</div>
        <h1>The manual way</h1><p>One subrecipient, start to finish.</p></div>""", 3.5)

    page.goto("https://app.fac.gov/dissemination/search/", wait_until="networkidle")
    badge(page, True)
    caption(page, "Search the Federal Audit Clearinghouse (FAC) for the subrecipient.", "Step 1 · Find the audit", 3.5)
    click(page, page.get_by_role("button", name="Name (Entity, Auditee, or Auditor)"))
    click(page, page.locator("#input_entity-name"), 0.2)
    page.locator("#input_entity-name").press_sequentially("Emporia", delay=110)
    time.sleep(0.4)
    click(page, page.locator("label[for=audit-year-2024]"), 0.3)
    state = page.get_by_role("button", name="State")
    click(page, state, 0.4)
    point(page, page.locator("#auditee_state"))
    page.select_option("#auditee_state", "VA")
    time.sleep(0.6)
    scroll(page, -2000, 250, 450)
    with page.expect_navigation(wait_until="networkidle"):
        click(page, page.locator("input[type=submit][value=Search]").first, 0.2)
    page.evaluate("window.__demo.ensure()")
    badge(page, True)
    caption(page, "One result: the City of Emporia's 2024 audit, accepted September 8, 2026.", "Step 1 · Find the audit")
    # The View link opens a new tab; show the click, then open the page in this tab so it stays on camera.
    point(page, page.locator("a[href='/dissemination/summary/2024-06-GSAFAC-0000426782']").first)
    page.evaluate("document.getElementById('demo-cur').classList.add('down')")
    time.sleep(0.2)
    page.goto("https://app.fac.gov/dissemination/summary/2024-06-GSAFAC-0000426782", wait_until="networkidle")
    page.evaluate("window.__demo.ensure()")
    badge(page, True)
    time.sleep(1)
    scroll(page, 1240)
    findings = page.locator("text=Findings:").first
    ring(page, findings.locator("xpath=.."))
    caption(page, "The FAC page only counts the findings. It does not say what they are, or whether they are on "
                  "DCJS's grants.", "Step 2 · Read the findings")
    unring(page)
    scroll(page, -1240)
    report = page.get_by_text("Single audit report").first
    ring(page, report)
    point(page, report)
    caption(page, "So the monitor downloads the full audit report and reads it: each finding, the federal program it "
                  "hit, and which agency passed that money down.", "Step 2 · Read the findings")
    unring(page)

    card(page, """<div class="card">
        <div class="kicker">Step 3 · Work out the deadlines by hand</div>
        <h2>City of Emporia, 2024 audit</h2>
        <table>
          <tr class="row"><td>Fiscal year ended</td><td>June 30, 2024</td></tr>
          <tr class="row"><td>Audit due (nine months later)</td><td>March 31, 2025</td></tr>
          <tr class="row"><td>Audit accepted by the FAC</td><td>Sept. 8, 2026: <span class="bad">filed late,
            27 months after year end</span></td></tr>
          <tr class="row"><td>Next audit (year ended June 30, 2025)</td><td>Due March 31, 2026:
            <span class="bad">not on file, overdue</span></td></tr>
          <tr class="row"><td>Written decision on each DCJS finding</td><td>Due March 8, 2027
            (six months after acceptance)</td></tr>
        </table></div>""", 12,
         "document.querySelectorAll('tr.row').forEach((r, i) => setTimeout(() => r.classList.add('show'), 600 + i * 1200))")

    concerns = ("Five findings on DCJS grants in the 2024 audit, all material weaknesses, one a repeat: procurement, "
                "allowed activities and costs, reporting. Audit filed late; next audit overdue.")
    card(page, f"""<div class="card">
        <div class="kicker">Step 4 · Fill in the agency's risk form</div>
        <h2>DCJS grant monitoring risk assessment: audit rows</h2>
        <table>
          <tr><th style="width:24%">Row</th><th>Answer</th><th style="width:12%">Points</th></tr>
          <tr><td>Single-Audit</td><td>Yes</td><td>0</td></tr>
          <tr><td>Audit Opinion</td><td>Audit performed on a DCJS program and Unmodified</td><td>0</td></tr>
          <tr><td>Documented concerns</td><td colspan="2"><div class="typed" id="t"></div></td></tr>
        </table>
        <p class="muted" style="margin-top:18px">Simplified from DCJS's published risk assessment spreadsheet.
        The concerns box is free text that can raise the risk level.</p></div>""", 13,
         f"const s = {concerns!r}; let i = 0; setTimeout(function tick() {{ "
         "document.getElementById('t').textContent = s.slice(0, ++i); if (i < s.length) setTimeout(tick, 38); }, 800);")

    card(page, """<div class="card section">
        <div class="kicker">Step 5 · Repeat</div>
        <div class="big-num"><span id="n">1</span> <span style="font-size:60px;color:#64748B">of 188</span></div>
        <p style="margin-top:22px">The FAC shows 188 Virginia local governments receiving DCJS money.<br>
        Each one needs steps 1 to 4, and DCJS policy repeats the assessment every year.</p></div>""", 7,
         "let n = 1; setTimeout(function up() { n = Math.min(188, n + Math.ceil((188 - n) / 14));"
         " document.getElementById('n').textContent = n; if (n < 188) setTimeout(up, 70); }, 1500);")


def after(page):
    card(page, """<div class="card section"><div class="kicker">After</div>
        <h1>Federal Grant Risk Screen</h1><p>The same job, for all 188 at once.</p></div>""", 3.5)

    page.goto(SITE + "/")
    streamlit_ready(page, "Needs your attention")
    badge(page, False)
    caption(page, "The monitor picks their agency. Every subrecipient's audits are already pulled from the FAC "
                  "and checked.", "Live site")
    tile = page.locator(".kpi").nth(1) if page.locator(".kpi").count() > 1 else page.get_by_text("have audit problems on your grants")
    ring(page, tile)
    point(page, tile)
    caption(page, "7 of the 188 have audit findings on DCJS's own grants. They come first.", "Live site")
    unring(page)

    emporia = page.locator("[data-testid=stHorizontalBlock]", has_text="CITY OF EMPORIA").first
    emporia.scroll_into_view_if_needed()
    time.sleep(0.5)
    ring(page, emporia)
    caption(page, "Each card shows the risk rating, the problem areas, and when the written decision is due.",
            "Live site")
    unring(page)
    click(page, emporia.get_by_role("button", name="Open"))
    streamlit_ready(page, "What to check next")
    page.evaluate("window.__demo.ensure()")
    badge(page, False)
    caption(page, "Steps 2 and 4: an AI drafts the risk summary. Each reason quotes the auditor's words.",
            "Summary")
    quote = page.locator(".quote").first
    ring(page, quote)
    caption(page, "Code checks every quote word for word against the audit, and a person approves the sheet "
                  "before it appears here.", "Summary")
    unring(page)
    scroll(page, 500)
    time.sleep(1.5)
    scroll(page, -2000)

    click(page, page.get_by_role("tab", name="Audit checks"), 1.0)
    caption(page, "Step 3, done by code: audit on file, filed late, next audit overdue, written decision due "
                  "March 8, 2027.", "Audit checks")
    scroll(page, 450)
    click(page, page.get_by_text("How this fills in the state risk forms"), 1.0)
    scroll(page, 400)
    caption(page, "Step 4's audit rows, filled in by code for the DCJS, VDEM and North Carolina forms. No AI here.",
            "Audit checks")
    scroll(page, -2000)

    click(page, page.get_by_role("tab", name="Findings"), 1.0)
    caption(page, "Every finding, marked when it is on DCJS's grants, with the program it hit.", "Findings")
    click(page, page.get_by_text("What the auditor found").first, 1.0)
    scroll(page, 350)
    caption(page, "The auditor's full text, with a link back to the audit on fac.gov.", "Findings")
    scroll(page, -2000)

    click(page, page.get_by_role("button", name="Back to the DCJS worklist"))
    streamlit_ready(page, "Needs your attention")
    page.evaluate("window.__demo.ensure()")
    badge(page, False)
    caption(page, "And it works for any Virginia agency.", "Live site", 2.0)
    select = page.locator("[data-testid=stSidebar] [data-testid=stSelectbox]").first
    click(page, select, 0.5)
    page.keyboard.type("Social", delay=90)
    time.sleep(0.5)
    page.keyboard.press("Enter")
    streamlit_ready(page, "Needs your attention")
    page.evaluate("window.__demo.ensure()")
    badge(page, False)
    caption(page, "Department of Social Services: its own 142 subrecipients, its own findings, its own deadlines.",
            "Live site")


def closing(page):
    card(page, """<div class="card">
        <div class="kicker">How it works</div>
        <h2>What runs behind the page</h2>
        <div class="grid">
          <div class="box"><b>Data</b><span>Six tables from the FAC's public API, loaded into Postgres (Neon):
            every Virginia local government audit.</span></div>
          <div class="box"><b>AI draft</b><span>Claude writes the risk summary. Code rejects any quote that is not
            word for word in the auditor's text.</span></div>
          <div class="box"><b>Human approval</b><span>A LangGraph workflow stops until a person approves, edits or
            rejects each draft.</span></div>
          <div class="box"><b>Rules by code</b><span>Deadlines and the audit rows of three real risk forms are
            worked out by code, with no AI.</span></div>
          <div class="box"><b>MCP server</b><span>Lets an AI assistant look up the same findings.</span></div>
          <div class="box"><b>Hosting</b><span>Streamlit on Azure App Service, deployed by GitHub Actions on every
            push.</span></div>
        </div>
        <p class="muted" style="margin-top:22px">Tested on 30 sampled localities: the AI's rating matched the hand
        rating on 29, and 110 of 110 quotes were found word for word.</p></div>""", 13)
    card(page, f"""<div class="card section">
        <h1>Federal Grant Risk Screen</h1>
        <p style="font-size:24px">Live: {SITE.replace('https://', '')}</p>
        <p style="font-size:24px">Code: {REPO}</p>
        <p class="muted" style="margin-top:30px">A portfolio project. Not affiliated with DCJS, VDEM or any Virginia
        agency. Data from the Federal Audit Clearinghouse.</p></div>""", 6)


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
        page.set_default_timeout(60000)
        try:
            opening(page)
            before(page)
            after(page)
            closing(page)
        finally:
            try:
                page.screenshot(path=str(HERE / "last_frame.png"))
            except Exception:
                pass
            context.close()
            browser.close()
    video = next(RAW.glob("*.webm"))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vf", "scale=1920:1080:flags=lanczos",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", str(HERE / "demo.mp4")], check=True)
    print("Wrote", HERE / "demo.mp4")


if __name__ == "__main__":
    main()
