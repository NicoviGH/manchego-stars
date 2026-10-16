#!/usr/bin/env node
// The built wiki as a phone shows it (#493): Chrome emulates a 390x844 phone (`mobile: true`
// honours the viewport meta, as a phone does), and for each page this screenshots the top, the
// first table wider than the column (scrolled to it), and a menu opened from the header.
// It also reports each page's layout width, and exits 1 if a page scrolls sideways or a phone
// does not lay it out at the phone's own width.
//
//   node tools/wiki/phone_shots.mjs <out-dir> [page-id ...]      (after python3 tools/gen_wiki.py)
//   W=1400 H=1000 node tools/wiki/phone_shots.mjs <out-dir> ...  (a desktop window instead)
//
// A page id is the wiki's hash (home, ch01, ch01/script, unit-braulo, roster, lord-select);
// `menu:#site-navigation` or `menu:#page-tools` opens that header menu on the page shown last.
// Needs Google Chrome and Node 22+ (its built-in WebSocket); no packages.
import { spawn } from 'node:child_process';
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const WIKI = resolve(dirname(fileURLToPath(import.meta.url)), '../../build/wiki/index.html');
const DEFAULT = ['home', 'ch01', 'ch01/script', 'ch05', 'unit-braulo', 'unit-izobai', 'roster',
                 'chapters', 'lord-select', 'menu:#site-navigation', 'menu:#page-tools'];
const [out, ...args] = process.argv.slice(2);
if (!out) { console.error('usage: phone_shots.mjs <out-dir> [page-id ...]'); process.exit(2); }
const ids = args.length ? args : DEFAULT;
mkdirSync(out, { recursive: true });

const port = 9333;
const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--hide-scrollbars',
  `--remote-debugging-port=${port}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), 'cdp'))}`,
  'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let target;
for (let i = 0; i < 50 && !target; i++) {
  try { target = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find(t => t.type === 'page'); }
  catch { await sleep(200); }
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise(r => { ws.onopen = r; });
let next = 0;
const pending = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const send = (method, params = {}) => new Promise(r => { const id = ++next; pending.set(id, r); ws.send(JSON.stringify({ id, method, params })); });
const run = async expression => (await send('Runtime.evaluate', { expression, returnByValue: true })).result.result.value;
const shoot = async name => {
  const s = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync(join(out, name.replace(/[^\w-]+/g, '_') + '.png'), Buffer.from(s.result.data, 'base64'));
};

const desktop = Boolean(process.env.W);
await send('Emulation.setDeviceMetricsOverride', { width: +(process.env.W || 390),
  height: +(process.env.H || 844), deviceScaleFactor: desktop ? 1 : 2, mobile: !desktop });
await send('Emulation.setTouchEmulationEnabled', { enabled: !desktop });
await send('Page.navigate', { url: 'file://' + WIKI + '#home' });
await sleep(6000);                          // a 10 MB page: its images decode before the router runs

let failed = 0;
for (const id of ids) {
  if (id.startsWith('menu:')) {
    await run(`window.scrollTo(0,0);document.querySelector('${id.slice(5)} h2').click()`);
    await sleep(400);
    await shoot(id);
    await run(`document.getElementById('menus-cover').click()`);
    continue;
  }
  await run(`location.hash='${id}'`);
  await sleep(800);
  await run('window.scrollTo(0,0)');
  await sleep(200);
  const r = await run(`(()=>{const d=document.documentElement;return {width:d.clientWidth,layout:d.scrollWidth}})()`);
  // A phone lays a page with no viewport meta out at 980px: the skin's phone rules never fire.
  const bad = r.layout > r.width ? '  SCROLLS SIDEWAYS' : !desktop && r.width !== 390 ? '  NOT AT PHONE WIDTH' : '';
  if (bad) failed++;
  console.log(`${id}: viewport ${r.width}px, page ${r.layout}px${bad}`);
  await shoot(id);
  const wide = await run(`(()=>{const t=[...document.querySelectorAll('section.page:not([hidden]) table')]
    .find(e=>e.getBoundingClientRect().right>innerWidth+1);if(!t)return null;t.scrollIntoView();
    const box=t.closest('.ms-scroll');return {table:t.className,width:Math.round(t.getBoundingClientRect().width),
    scrolls:box?getComputedStyle(box).overflowX:'no box'}})()`);
  if (wide) {
    console.log(`  widest table: .${wide.table.split(' ')[0]} ${wide.width}px, its box scrolls: ${wide.scrolls}`);
    await sleep(300);
    await shoot(id + '-wide');
  }
}
ws.close();
chrome.kill();
process.exit(failed ? 1 : 0);
