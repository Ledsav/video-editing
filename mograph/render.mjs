#!/usr/bin/env node
// Render an HTML motion graphic to video (ProRes 4444 with alpha) or to PNG stills.
//
//   node render.mjs --html page.html --out out.mov --width 1920 --height 1080 \
//        --fps 30 --duration 2.5 [--params '{"title":"Hi"}']
//   node render.mjs --html page.html --stills 0.2,0.8,1.5 --out /tmp/prefix ...
//
// Time is fully controlled: the page is advanced frame by frame through VM.__seek(t)
// (see lib/runtime.js), so output is deterministic and independent of machine speed.
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));

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
  console.error('usage: render.mjs --html file.html --out out.mov [--width --height --fps --duration --params JSON --stills t1,t2]');
  process.exit(2);
}
const width = parseInt(args.width || '1920', 10);
const height = parseInt(args.height || '1080', 10);
const fps = parseFloat(args.fps || '30');
const params = args.params ? JSON.parse(args.params) : {};
const htmlPath = path.resolve(args.html);
const html = fs.readFileSync(htmlPath, 'utf8');
const metaDur = /<meta\s+name="vedit:duration"\s+content="([\d.]+)"/.exec(html);
const duration = parseFloat(args.duration || (metaDur ? metaDur[1] : '2'));
const runtime = fs.readFileSync(path.join(here, 'lib', 'runtime.js'), 'utf8');

const launchOpts = { args: ['--allow-file-access-from-files', '--disable-web-security', '--font-render-hinting=none'] };
if (process.env.VEDIT_CHROMIUM) launchOpts.executablePath = process.env.VEDIT_CHROMIUM;
const browser = await chromium.launch(launchOpts);
const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
page.on('pageerror', (e) => console.error('[page error]', e.message));
page.on('console', (m) => { if (m.type() === 'error') console.error('[page console]', m.text()); });
await page.addInitScript({
  content: `window.__VEDIT_RENDERER__ = true; window.PARAMS = ${JSON.stringify(params)};
            window.VEDIT = ${JSON.stringify({ width, height, fps, duration })};\n${runtime}`,
});
await page.goto(pathToFileURL(htmlPath).href, { waitUntil: 'load' });
await page.evaluate(() => document.fonts.ready);
await page.evaluate(() => (window.VM_READY ? window.VM_READY : null));

const grab = async (t) => {
  await page.evaluate((tt) => window.VM.__seek(tt), t);
  return page.screenshot({ omitBackground: true, type: 'png' });
};

if (args.stills) {
  const times = String(args.stills).split(',').map(Number);
  const written = [];
  for (const t of times) {
    const file = `${args.out}_${t.toFixed(2)}.png`;
    fs.writeFileSync(file, await grab(t));
    written.push(file);
  }
  console.log(JSON.stringify(written));
} else {
  const frames = Math.max(1, Math.round(duration * fps));
  const ff = spawn('ffmpeg', [
    '-hide_banner', '-loglevel', 'error', '-y',
    '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'png', '-i', '-',
    '-frames:v', String(frames),
    '-c:v', 'prores_ks', '-profile:v', '4', '-pix_fmt', 'yuva444p10le', '-vendor', 'apl0',
    args.out,
  ], { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise((res, rej) => ff.on('close', (c) => (c === 0 ? res() : rej(new Error(`ffmpeg exited ${c}`)))));
  for (let i = 0; i < frames; i++) {
    const buf = await grab(i / fps);
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
  }
  ff.stdin.end();
  await done;
  console.log(JSON.stringify({ out: args.out, frames, fps, duration }));
}
await browser.close();
