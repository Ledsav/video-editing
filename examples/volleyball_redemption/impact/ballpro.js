// Real Mikasa V200W model (FBX + PBR textures in impact/ball_v200w/), normalised to radius 1 around the origin.
async function loadProBall(THREE, base = 'ball_v200w/') {
  const { FBXLoader } = await import(VEDIT.libs.three_addons + 'loaders/FBXLoader.js');
  const obj = new FBXLoader().parse(await readBinary(base + 'ball.fbx'), '');
  const tl = new THREE.TextureLoader();
  const tex = (f, srgb) => new Promise((res) => tl.load(base + f, (t) => { if (srgb) t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; res(t); }, undefined, () => res(null)));
  const set = async (p) => new THREE.MeshStandardMaterial({
    map: await tex(p + 'BaseColor.png', true), normalMap: await tex(p + 'Normal.png'), roughnessMap: await tex(p + 'Roughness.png'),
    roughness: 1, metalness: 0 });
  const main = await set('Material_'), valve = await set('Pimpa_Material_');
  obj.traverse((o) => { if (!o.isMesh) return;
    const pick = (m) => (/pimpa/i.test(m?.name || '') ? valve : main);
    o.material = Array.isArray(o.material) ? o.material.map(pick) : pick(o.material); o.castShadow = true; o.frustumCulled = false; });
  // centre and scale to unit radius
  const box = new THREE.Box3().setFromObject(obj), c = box.getCenter(new THREE.Vector3()), r = box.getSize(new THREE.Vector3()).x / 2;
  const pivot = new THREE.Group(); obj.position.sub(c); pivot.add(obj); pivot.userData.r = r; obj.parent.scale.setScalar(1 / r);
  const out = new THREE.Group(); out.add(pivot); return out;
}
