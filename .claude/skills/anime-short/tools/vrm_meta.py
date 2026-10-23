"""A VRM's own licence terms (who may use it, violence, commercial use, licence) and, with --materials, its material and
expression names (for anime_shot.html's `materials` and `face` params).

  python3 vrm_meta.py [--materials] file.vrm [...]
"""
import json
import struct
import sys


def read(path):
    with open(path, 'rb') as fh:
        fh.read(12)
        n, _ = struct.unpack('<I4s', fh.read(8))
        return json.loads(fh.read(n))


def main(argv):
    mats = '--materials' in argv
    files = [a for a in argv if a != '--materials']
    if not files:
        print(__doc__)
        return 2
    for f in files:
        j = read(f)
        ext = j.get('extensions', {})
        name = f.split('/')[-1]
        if 'VRM' in ext:
            m = ext['VRM']['meta']
            keys = ['title', 'author', 'allowedUserName', 'violentUssageName', 'sexualUssageName', 'commercialUssageName', 'licenseName', 'otherLicenseUrl']
            print(name, 'VRM 0.x', {k: m.get(k) for k in keys})
            groups = [g.get('presetName') if g.get('presetName') not in (None, 'unknown') else g.get('name') for g in ext['VRM']['blendShapeMaster']['blendShapeGroups']]
        elif 'VRMC_vrm' in ext:
            m = ext['VRMC_vrm']['meta']
            keys = ['name', 'authors', 'licenseUrl', 'avatarPermission', 'allowExcessivelyViolentUsage', 'commercialUsage', 'creditNotation', 'allowRedistribution', 'modification']
            print(name, 'VRM 1.0', {k: m.get(k) for k in keys})
            ex = ext['VRMC_vrm'].get('expressions', {})
            groups = list(ex.get('preset', {})) + list(ex.get('custom', {}))
        else:
            print(name, 'not a VRM (no licence metadata): check its source page')
            groups = []
        if mats:
            print('  materials:', [m.get('name') for m in j.get('materials', [])])
            print('  expressions:', groups)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
