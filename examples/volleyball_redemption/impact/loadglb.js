// file:// pages can't fetch(); read the GLB with XHR and hand the bytes to GLTFLoader.parse
function readBinary(url) {
  return new Promise((res, rej) => { const x = new XMLHttpRequest(); x.open('GET', url); x.responseType = 'arraybuffer';
    x.onload = () => res(x.response); x.onerror = () => rej(new Error('xhr ' + url)); x.send(); });
}
async function loadGLB(GLTFLoader, url) {
  const buf = await readBinary(url);
  return new Promise((res, rej) => new GLTFLoader().parse(buf, '', res, rej));
}
