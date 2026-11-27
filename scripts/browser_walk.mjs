#!/usr/bin/env node
// Walk the haunted sample in a real Chrome at 1280 px, from landing to verdict, and print what was seen at each step:
// the heading that has focus, how far the page is scrolled, and how many step rails say "current step".
// It drives Chrome over its DevTools protocol with Node's built-in WebSocket (Node 22 or later); no package is needed.
// It only talks to a Ghost server you started yourself (default http://127.0.0.1:8080) and to the Chrome it starts.
//
// Usage:  node scripts/browser_walk.mjs [base-url]        (GHOST_CHROME overrides the Chrome path)
// Start the server first:  .venv/bin/python -m uvicorn web.app:app --port 8080
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const BASE = (process.argv[2] || "http://127.0.0.1:8080").replace(/\/$/, "");
const CHROME = process.env.GHOST_CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const PORT = 9333;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const profile = mkdtempSync(join(tmpdir(), "ghost-walk-"));
const chrome = spawn(CHROME, [`--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, "--headless=new", "--disable-gpu",
  "--window-size=1280,900", "--no-first-run", "--no-default-browser-check", "about:blank"], { stdio: "ignore" });
const report = [];
const say = (step, obj) => { report.push({ step, ...obj }); console.log(JSON.stringify({ step, ...obj })); };

async function getTarget() {
  for (let i = 0; i < 60; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      const page = list.find((t) => t.type === "page");
      if (page) return page.webSocketDebuggerUrl;
    } catch { /* chrome is still starting */ }
    await sleep(250);
  }
  throw new Error("Chrome did not start");
}

const wsUrl = await getTarget();
const ws = new WebSocket(wsUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let nextId = 1;
const pending = new Map();
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); } };
const send = (method, params = {}) => new Promise((res) => { const id = nextId++; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const evaluate = async (expr) => {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails.exception?.description || r.result.exceptionDetails));
  return r.result.result.value;
};
const until = async (expr, what, ms = 240000) => {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { if (await evaluate(expr)) return Date.now() - t0; await sleep(300); }
  throw new Error("timed out waiting for " + what);
};
// what the viewer sees right now
const SNAP = `(() => {
  const a = document.activeElement;
  const rails = [...document.querySelectorAll('.stepper')];
  const cues = rails.map(r => r.querySelectorAll('.step-cue').length);
  const vp = innerHeight;
  const rect = (sel) => { const e = document.querySelector(sel); if (!e) return null; const b = e.getBoundingClientRect(); return { top: Math.round(b.top), inView: b.top >= 0 && b.bottom <= vp }; };
  return { viewport: innerWidth + 'x' + innerHeight, scrollY: Math.round(scrollY),
    focused: a ? (a.tagName.toLowerCase() + (a.id ? '#' + a.id : '') + ' "' + (a.textContent || '').trim().slice(0, 60) + '"') : null,
    rails: rails.length, railsSayingCurrentStep: cues.filter(n => n > 0).length, currentMarkers: cues.reduce((s, n) => s + n, 0),
    ariaCurrent: document.querySelectorAll('[aria-current="step"]').length,
    headings: { loaded: rect('#loaded-h'), autopsy: rect('#autopsy-h'), job: rect('#job .job h2'), verdict: rect('.vc-headline') } };
})()`;

try {
  await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
  await send("Page.navigate", { url: BASE + "/" });
  await until("document.readyState === 'complete' && !!document.querySelector('.samples button')", "the landing page");
  say("1 landing", await evaluate(SNAP));

  await evaluate("[...document.querySelectorAll('.samples button')].find(b => /haunted/i.test(b.closest('li').textContent)).click()");
  await until("!!document.querySelector('#autopsy-h')", "the autopsy");
  await sleep(500);
  say("2 sample loaded, autopsy shown", await evaluate(SNAP));

  await evaluate(`(() => {
    const radios = [...document.querySelectorAll('input[name=choice]')];
    const r = radios.find(x => /Change Calculator!B9 from '>' to '>='/.test(x.closest('label').textContent));
    if (!r) throw new Error("the option Change Calculator!B9 from '>' to '>=' is not there");
    r.checked = true;
    document.querySelector('input[name=author]').value = 'Demo';
    document.querySelector('input[name=reason]').value = 'Bulk means 50 or more';
    document.querySelector('form[hx-post="/decision"] button[type=submit]').click();
  })()`);
  await until("/D-001/.test(document.querySelector('#autopsy')?.textContent || '')", "decision D-001");
  await sleep(500);
  say("3 decision recorded (D-001)", await evaluate(SNAP));

  // scroll somewhere neutral, so that a jump is visible
  await evaluate("document.querySelector('form[hx-post=\"/verify\"]').scrollIntoView({block: 'center'})");
  await sleep(300);
  say("4 before Run verification (form centred)", await evaluate(SNAP));
  const runStart = Date.now();
  await evaluate("document.querySelector('form[hx-post=\"/verify\"] button[type=submit]').click()");
  await until("!!document.querySelector('#job .job h2')", "the job panel");
  await sleep(700);
  say("5 right after Run verification", await evaluate(SNAP));
  const mid = [];
  for (let i = 0; i < 6; i++) { await sleep(1000); mid.push(await evaluate("({y: Math.round(scrollY), focused: document.activeElement.id || document.activeElement.tagName})")); }
  say("6 while polling (6 samples, one per second)", { samples: mid, scrollMoved: new Set(mid.map((m) => m.y)).size > 1, focusMoved: new Set(mid.map((m) => m.focused)).size > 1 });

  const waited = await until("!document.querySelector('.job[hx-get]') && !!document.querySelector('.vc-headline')", "the verdict");
  await sleep(700);
  say("7 run finished", { ...(await evaluate(SNAP)), waitedMs: waited,
    verdictText: await evaluate("document.querySelector('.vc-headline').textContent.trim()"),
    mutation: await evaluate("(document.querySelector('.mutation-summary') || {textContent: 'not shown'}).textContent.trim()"),
    secondsFromClickToVerdictSeen: Math.round((Date.now() - runStart) / 100) / 10 });
  say("8 end", { stepRailsAtEnd: await evaluate("[...document.querySelectorAll('.stepper')].map(r => [...r.querySelectorAll('li')].map(l => l.className.split(' ').filter(c => c !== 'step').join('')).join(','))") });
  writeFileSync(join(profile, "report.json"), JSON.stringify(report, null, 2));
} catch (e) {
  console.error("walk failed:", e.message);
  process.exitCode = 1;
} finally {
  try { ws.close(); } catch { /* closed */ }
  chrome.kill();
  await sleep(300);
  rmSync(profile, { recursive: true, force: true });
}
