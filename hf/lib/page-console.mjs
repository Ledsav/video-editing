#!/usr/bin/env node
// Print what a built vedit page logs while it gets ready (load errors, timing notes such as ANIME_TIMES):
// what the vedit renderer used to print while rendering. HyperFrames' snapshot does not relay the console,
// so vedit/hyperframes.py runs this next to it.
//
//   node page-console.mjs <build dir> <node_modules dir> <chrome executable> [timeout ms] [t1,t2,...]
//
// With times, the page is then seeked to each one (as HyperFrames does, through hf-seek), so what a page logs
// per frame is printed too.
//
// The build dir (from vedit/hyperframes.py) is served over HTTP, symlinks followed, in HyperFrames' Chrome.
// Lines: "[page console] <console.error text>" and "[page error] <uncaught exception>".
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const [root, nodeModules, chrome, timeoutArg, timesArg] = process.argv.slice(2);
const times = (timesArg || '').split(',').filter(Boolean).map(Number);
if (!root || !nodeModules || !chrome) {
  console.error('usage: page-console.mjs <build dir> <node_modules dir> <chrome executable> [timeout ms] [t1,t2,...]');
  process.exit(2);
}
const timeout = parseInt(timeoutArg || '120000', 10);
const puppeteer = createRequire(path.join(nodeModules, 'noop.js'))('puppeteer-core');
const TYPES = {
  '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.gif': 'image/gif', '.svg': 'image/svg+xml',
  '.wasm': 'application/wasm', '.ttf': 'font/ttf', '.otf': 'font/otf', '.woff': 'font/woff', '.woff2': 'font/woff2',
  '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.mp4': 'video/mp4', '.glb': 'model/gltf-binary', '.gltf': 'model/gltf+json',
};
const server = http.createServer((req, res) => {
  const rel = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  if (rel.split('/').includes('..')) { res.writeHead(403); res.end(); return; }
  const file = path.join(root, rel === '/' ? 'index.html' : rel);
  fs.stat(file, (err, st) => {
    if (err || !st.isFile()) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'content-type': TYPES[path.extname(file).toLowerCase()] || 'application/octet-stream' });
    fs.createReadStream(file).pipe(res);
  });
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const browser = await puppeteer.launch({ executablePath: chrome, headless: true,
  args: ['--no-sandbox', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--font-render-hinting=none'] });
let status = 0;
try {
  const page = await browser.newPage();
  const vp = JSON.parse(fs.readFileSync(path.join(root, 'index.html'), 'utf8').match(/window\.VEDIT = (\{.*?\});/)?.[1] || '{}');
  await page.setViewport({ width: vp.width || 1920, height: vp.height || 1080, deviceScaleFactor: 1 });
  page.on('console', (m) => { if (m.type() === 'error') console.log('[page console] ' + m.text()); });
  page.on('pageerror', (e) => console.log('[page error] ' + e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/index.html`, { waitUntil: 'load', timeout });
  await page.evaluate((ms) => Promise.race([
    (window.__hf && window.__hf.buildReady && window.__hf.buildReady['vedit-page']) || Promise.resolve(),
    new Promise((r) => setTimeout(r, ms)),
  ]), timeout);
  for (const t of times) {
    await page.evaluate((time) => new Promise((r) => {
      window.dispatchEvent(new CustomEvent('hf-seek', { detail: { time } }));
      requestAnimationFrame(() => r());
    }), t);
  }
} catch (e) {
  console.log('[page error] ' + e.message);
  status = 1;
} finally {
  await browser.close();
  server.close();
}
process.exit(status);
