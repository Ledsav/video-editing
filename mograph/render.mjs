#!/usr/bin/env node
// Render an HTML motion graphic or motion-design scene to video, or to PNG stills.
//
//   node render.mjs --html page.html --out out.mov --width 1920 --height 1080 \
//        --fps 30 --duration 2.5 [--params '{"title":"Hi"}'] [--beats beats.json]
//        [--opaque] [--from-frame N --to-frame M]
//   node render.mjs --html page.html --stills 0.2,0.8,1.5 --out /tmp/prefix ...
//
// Time is fully controlled: the page is advanced frame by frame through VM.__seek(t)
// (see lib/runtime.js), so output is deterministic and independent of machine speed.
//   default   ProRes 4444 with alpha (.mov), PNG frames      -> overlays, titles, transitions
//   --opaque  H.264 (.mp4), JPEG frames, ~3x faster          -> full-screen scenes
// Libraries a page asks for with <meta name="vedit:libs" content="gsap,lottie,three"> are
// provided offline: gsap and lottie as globals, three via `await import(VEDIT.libs.three)`.
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const nm = path.join(here, 'node_modules');
const LIBS = {
  gsap: [path.join(nm, 'gsap/dist/gsap.min.js')],
  lottie: [path.join(nm, 'lottie-web/build/player/lottie.min.js')],
};
const MODULES = {
  three: path.join(nm, 'three/build/three.module.js'),
  three_addons: path.join(nm, 'three/examples/jsm/'),
};

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.startsWith('--')) out[key] = true;
      else { out[key] = next; i++; }
    }
  }
  return out;
}

const args = parseArgs(process.argv.slice(2));
if (!args.html || !args.out) {
  console.error('usage: render.mjs --html file.html --out out.mov [--width --height --fps --duration --params JSON --beats file --opaque --from-frame --to-frame --stills t1,t2]');
  process.exit(2);
}
const width = parseInt(args.width || '1920', 10);
const height = parseInt(args.height || '1080', 10);
const fps = parseFloat(args.fps || '30');
const params = args.params ? JSON.parse(args.params) : {};
const beats = args.beats ? JSON.parse(fs.readFileSync(args.beats, 'utf8')) : [];
const opaque = !!args.opaque;
const htmlPath = path.resolve(args.html);
const html = fs.readFileSync(htmlPath, 'utf8');
const metaDur = /<meta\s+name="vedit:duration"\s+content="([\d.]+)"/.exec(html);
const duration = parseFloat(args.duration || (metaDur ? metaDur[1] : '2'));
const metaLibs = /<meta\s+name="vedit:libs"\s+content="([^"]*)"/.exec(html);
const wanted = (metaLibs ? metaLibs[1] : '').split(',').map((s) => s.trim()).filter(Boolean);
const runtime = fs.readFileSync(path.join(here, 'lib', 'runtime.js'), 'utf8');

const launchOpts = { args: ['--allow-file-access-from-files', '--disable-web-security', '--font-render-hinting=none',
                            '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] };
if (process.env.VEDIT_CHROMIUM) launchOpts.executablePath = process.env.VEDIT_CHROMIUM;
const browser = await chromium.launch(launchOpts);
const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
page.on('pageerror', (e) => console.error('[page error]', e.message));
page.on('console', (m) => { if (m.type() === 'error') console.error('[page console]', m.text()); });

const libUrls = Object.fromEntries(Object.entries(MODULES).map(([k, p]) => [k, pathToFileURL(p).href]));
for (const lib of wanted) {
  for (const file of LIBS[lib] || []) await page.addInitScript({ path: file });
  if (!LIBS[lib] && !MODULES[lib]) console.error(`[render] unknown lib '${lib}' (available: ${[...Object.keys(LIBS), ...Object.keys(MODULES)].join(', ')})`);
}
await page.addInitScript({
  content: `window.__VEDIT_RENDERER__ = true; window.PARAMS = ${JSON.stringify(params)};
            window.VEDIT = ${JSON.stringify({ width, height, fps, duration, beats, libs: libUrls })};\n${runtime}`,
});
await page.goto(pathToFileURL(htmlPath).href, { waitUntil: 'load' });
await page.evaluate(() => document.fonts.ready);
// Pages that load assets or modules asynchronously set window.VM_READY to a promise.
await page.waitForFunction(() => window.VM_READY === undefined || window.VM_READY !== null, null, { timeout: 30000 }).catch(() => {});
await page.evaluate(() => (window.VM_READY ? window.VM_READY : null));
await page.evaluate(() => window.VM.__start && window.VM.__start());

// GSAP can skip tweens when its playhead jumps straight to a late time. Pre-roll its timeline
// through every skipped frame (cheap: no drawing, no screenshot) so parallel workers and stills
// match a sequential render exactly. Page code itself is a pure function of t by contract.
let playhead = 0;
const advance = async (t) => {
  await page.evaluate(({ from, to, step }) => {
    window.VM.__preroll(from, to, step);
    window.VM.__seek(to);
  }, { from: playhead, to: t, step: 1 / fps });
  playhead = t + 1 / fps;
};
const grab = async (t, type) => {
  if (t + 1e-6 < playhead - 1 / fps) {          // going backwards: restart from 0
    await page.reload({ waitUntil: 'load' });
    await page.evaluate(() => (window.VM_READY ? window.VM_READY : null));
    await page.evaluate(() => window.VM.__start && window.VM.__start());
    playhead = 0;
  }
  await advance(t);
  return type === 'jpeg'
    ? page.screenshot({ type: 'jpeg', quality: 94 })
    : page.screenshot({ omitBackground: true, type: 'png' });
};

if (args.stills) {
  const times = String(args.stills).split(',').map(Number);
  const written = [];
  for (const t of times) {
    const file = `${args.out}_${t.toFixed(2)}.png`;
    fs.writeFileSync(file, await grab(t, 'png'));
    written.push(file);
  }
  console.log(JSON.stringify(written));
} else {
  const total = Math.max(1, Math.round(duration * fps));
  const from = Math.max(0, parseInt(args['from-frame'] || '0', 10));
  const to = Math.min(total, parseInt(args['to-frame'] || String(total), 10));
  const enc = opaque
    ? ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '12', '-pix_fmt', 'yuv420p']
    : ['-c:v', 'prores_ks', '-profile:v', '4', '-pix_fmt', 'yuva444p10le', '-vendor', 'apl0'];
  const ff = spawn('ffmpeg', [
    '-hide_banner', '-loglevel', 'error', '-y',
    '-f', 'image2pipe', '-framerate', String(fps), '-c:v', opaque ? 'mjpeg' : 'png', '-i', '-',
    '-frames:v', String(to - from), ...enc, args.out,
  ], { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise((res, rej) => ff.on('close', (c) => (c === 0 ? res() : rej(new Error(`ffmpeg exited ${c}`)))));
  for (let i = from; i < to; i++) {
    const buf = await grab(i / fps, opaque ? 'jpeg' : 'png');
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
  }
  ff.stdin.end();
  await done;
  console.log(JSON.stringify({ out: args.out, frames: to - from, from, to, fps, duration }));
}
await browser.close();
