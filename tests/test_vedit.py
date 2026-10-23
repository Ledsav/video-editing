"""End-to-end and unit tests. Run: python3 -m unittest discover -s tests -v"""
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vedit import grade as G  # noqa: E402
from vedit import hyperframes as HF  # noqa: E402
from vedit.render import render  # noqa: E402
from vedit.text import build_ass  # noqa: E402
from vedit.timeline import build_plan  # noqa: E402
from vedit.util import ffmpeg, probe  # noqa: E402


class GradeTests(unittest.TestCase):
    def test_neutral_is_identity(self):
        x = np.random.default_rng(0).random((500, 3))
        np.testing.assert_allclose(G.apply_grade(x, G.look()), x, atol=1e-6)

    def test_every_tone_is_monotonic_on_gray_ramp(self):
        ramp = np.repeat(np.linspace(0, 1, 64)[:, None], 3, axis=1)
        for tone in G.TONES:
            y = G.apply_grade(ramp, G.look(tone)) @ G.LUMA
            self.assertTrue(np.all(np.diff(y) >= -1e-3), tone)

    def test_intensity_interpolates(self):
        half = G.look("golden_hour", 0.5)
        full = G.look("golden_hour", 1.0)
        self.assertAlmostEqual(half["temperature"], full["temperature"] / 2)

    def test_cube_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = G.write_cube(G.look("noir"), Path(d) / "x.cube", size=9)
            lines = p.read_text().splitlines()
            self.assertIn("LUT_3D_SIZE 9", lines)
            self.assertEqual(len(lines), 4 + 9 ** 3)


class Media:
    """Small synthetic sources shared by the timeline and render tests."""
    dir: Path

    @classmethod
    def make(cls):
        cls.dir = Path(tempfile.mkdtemp(prefix="vedit_test_"))
        (cls.dir / "media").mkdir()
        for name, src, f in (("a", "testsrc2", 440), ("b", "mandelbrot", 660)):
            ffmpeg(["-f", "lavfi", "-i", f"{src}=s=320x180:r=30", "-f", "lavfi", "-i", f"sine=f={f}",
                    "-t", "4", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", cls.dir / "media" / f"{name}.mp4"])
        ffmpeg(["-f", "lavfi", "-i", "sine=f=110:d=12", "-ac", "2", cls.dir / "music.wav"])
        return cls.dir


def base_spec(**extra):
    spec = {
        "output": {"path": "out/test.mp4", "width": 320, "height": 180, "fps": 30, "preset": "ultrafast"},
        "sources": {"a": "media/a.mp4", "b": "media/b.mp4"},
        "story": {"arc": [{"at": "0%", "tone": "cold_thriller"}, {"at": "100%", "tone": "golden_hour"}]},
        "timeline": [
            {"id": "c1", "source": "a", "in": 0, "out": 2, "motion": "push_in"},
            {"id": "c2", "source": "b", "in": 0.5, "out": 3, "transition": {"type": "crossfade", "duration": 0.5}},
            {"id": "c3", "source": "a", "in": 1, "out": 3, "transition": "glitch", "speed": 1.25},
            {"id": "c4", "color": "#202020", "duration": 1, "transition": "zoom_punch"},
        ],
    }
    spec.update(extra)
    return spec


class TimelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Media.make()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def plan(self, **extra):
        return build_plan(base_spec(**extra), self.dir)

    def test_layout_and_overlap(self):
        p = self.plan()
        c1, c2, c3, c4 = p.clips
        self.assertEqual(c1.frames, 60)
        self.assertEqual(c2.start_frame, 60 - 15)          # 0.5 s crossfade overlap
        self.assertEqual(c3.start_frame, c2.start_frame + c2.frames)
        self.assertEqual(c3.frames, round(2 / 1.25 * 30))
        self.assertEqual(p.total_frames, c4.start_frame + c4.frames)

    def test_arc_grades_progress(self):
        p = self.plan()
        self.assertLess(p.clips[0].grade_start["temperature"], 0)   # cold at the start
        self.assertGreater(p.clips[-1].grade_end["temperature"], 0)  # warm at the end
        self.assertNotEqual(p.clips[1].grade_start, p.clips[1].grade_end)

    def test_beat_snapping(self):
        beats = [round(0.5 * k, 3) for k in range(30)]
        p = self.plan(sync={"beats": beats, "max_shift": 0.3})
        for c in p.clips[1:]:
            b = c.transition.boundary
            self.assertLess(min(abs(b - x) for x in beats), 1 / 30 + 1e-6, c.id)

    def test_clip_anchored_text(self):
        p = self.plan(text=[{"text": "HI *THERE*", "style": "kinetic", "at_clip": "c2", "offset": 0.2}])
        out = self.dir / "t.ass"
        build_ass(p, out)
        ass = out.read_text()
        self.assertIn("Dialogue:", ass)
        self.assertIn("THERE", ass)

    def test_scene_clip(self):
        p = self.plan(timeline=[{"id": "s", "hyperframes": "scene-kinetic", "duration": 2.0},
                                {"id": "d", "hyperframes": "scene_stats"},     # old underscore names resolve
                                {"id": "c", "source": "a", "in": 0, "out": 1}])
        self.assertEqual(p.clips[0].kind, "scene")
        self.assertEqual(p.clips[0].frames, 60)
        self.assertEqual(p.clips[1].frames, 150)                       # its own data-duration (5 s)
        self.assertEqual(p.clips[0].grade_start["saturation"], 1.0)   # scenes keep their own colours

    def test_old_renderer_keys_still_work(self):
        p = self.plan(timeline=[{"id": "s", "scene": "scene_kinetic", "params": {"lines": ["A"]}},
                                {"id": "b", "source": "b", "in": 0, "out": 1,
                                 "transition": {"type": "mograph", "template": "shape_wipe", "params": {"colors": ["#fff"]}}}])
        self.assertEqual(p.clips[0].kind, "scene")
        self.assertEqual(p.clips[0].raw["variables"], {"lines": ["A"]})
        self.assertEqual(p.clips[1].transition.overlay, {"hyperframes": "shape_wipe", "variables": {"colors": ["#fff"]}})

    def test_bad_source_range(self):
        with self.assertRaises(Exception):
            build_plan(base_spec(timeline=[{"source": "a", "in": 10, "out": 12}]), self.dir)

    def test_page_deps_enter_the_cache_key(self):
        page = self.dir / "dep_page.html"
        page.write_text('<meta name="vedit:deps" content="lib.js, missing.js">')
        (self.dir / "lib.js").write_text("const A = 1;")
        before = HF.deps(page)
        (self.dir / "lib.js").write_text("const A = 2;")
        self.assertEqual(before, ["const A = 1;"])
        self.assertNotEqual(before, HF.deps(page))
        page.write_text("<p>no deps</p>")
        self.assertEqual(HF.deps(page), [])


class HyperFramesTests(unittest.TestCase):
    """The build step that turns a HyperFrames project into a render-ready copy (no browser needed)."""

    def test_builtins_are_complete(self):
        names = {b["name"] for b in HF.builtins()}
        self.assertTrue({"light-leak", "film-burn", "shape-wipe", "title-card", "scene-kinetic"} <= names)
        shim = (ROOT / "hf/lib/vm-shim.js").read_text()
        for b in HF.builtins():
            html = (b["path"] / "index.html").read_text()
            self.assertIn("window.__timelines[VM.id] = VM.start();", html, b["name"])
            self.assertEqual((b["path"] / "assets/vedit/vm-shim.js").read_text(), shim, b["name"])
            if b.get("kind") == "transition":
                self.assertIn("cover_at", b, b["name"])

    def test_build_declares_variables_size_and_duration(self):
        with tempfile.TemporaryDirectory() as d:
            b = HF.build(HF.resolve("title-card"), Path(d), {"title": "HELLO\nWORLD", "accent": "#ff0000"},
                         size=(1080, 1920), duration=2.5)
            html = (b / "index.html").read_text()
            decl = re.search(r"data-composition-variables='([^']*)'", html).group(1)
            self.assertEqual(json.loads(decl)[0]["default"], "HELLO\nWORLD")   # escapes survive
            m = HF.meta(b)
            self.assertEqual((m["width"], m["height"], m["duration"]), (1080, 1920, 2.5))
            self.assertNotIn("cdn.jsdelivr.net", html)               # libraries vendored for offline renders
            self.assertIn('src="./assets/vendor/gsap/', html)
            self.assertTrue((b / "assets/vendor/gsap/dist/gsap.min.js").exists())
            # the source project is untouched
            self.assertEqual(HF.meta(HF.resolve("title-card"))["width"], 1920)

    def test_beat_aware_scenes_are_detected(self):
        from vedit.render import BEATS_RE, _html_text
        self.assertTrue(BEATS_RE.search(_html_text(HF.resolve("scene-kinetic"))))
        self.assertFalse(BEATS_RE.search(_html_text(HF.resolve("scene-stats"))))

    def test_vendored_modules_bring_their_imports(self):
        with tempfile.TemporaryDirectory() as d:
            b = HF.build(HF.resolve("scene-3d-mountains"), Path(d))
            self.assertIn("import('./assets/vendor/three/build/three.module.js')", (b / "index.html").read_text())
            self.assertTrue((b / "assets/vendor/three/build/three.core.js").exists())

    def test_media_variables_are_localized(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            ffmpeg(["-f", "lavfi", "-i", "color=c=red:s=64x64", "-frames:v", "1", d / "pic.png"])
            b = HF.build(HF.resolve("scene-photo-stack"), d / "work", {"images": ["pic.png"]}, base=d)
            html = (b / "index.html").read_text()
            self.assertNotIn('"pic.png"', html)
            self.assertEqual(len(list((b / "assets/media").glob("*.png"))), 1)


class PageTests(unittest.TestCase):
    """Single vedit pages (the old renderer's contract) built to run inside HyperFrames."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="vedit_page_"))
        (self.dir / "lib").mkdir()
        (self.dir / "scenes").mkdir()
        (self.dir / "lib" / "shared.js").write_text("window.SHARED = 1;")
        (self.dir / "scenes" / "pic.png").write_bytes(b"png")
        self.page = self.dir / "scenes" / "a.html"
        self.page.write_text('<!doctype html><html><head><meta charset="utf-8">\n'
                             '<meta name="vedit:duration" content="2.5"><meta name="vedit:libs" content="gsap">\n'
                             '<script src="../lib/shared.js"></script></head>\n'
                             '<body><script>window.VM_READY = Promise.resolve(); VM.onFrame(() => {});</script></body></html>')

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_page_is_resolved_and_described(self):
        page = HF.resolve("scenes/a.html", self.dir)
        self.assertTrue(HF.is_page(page))
        self.assertEqual(HF.meta(page)["duration"], 2.5)

    def test_page_build(self):
        b = HF.build(self.page, self.dir / "work", {"img": "scenes/pic.png", "n": 3}, size=(640, 360), base=self.dir)
        html = (b / "index.html").read_text()
        # the tree its ../ references reach is mirrored, and the page addresses it from its own folder
        self.assertTrue((b / "lib" / "shared.js").exists())
        self.assertFalse((b / "work").exists())
        self.assertIn('<base href="scenes/">', html)
        self.assertIn('src="../_vedit/vendor/gsap/dist/gsap.min.js"', html)
        self.assertLess(html.index("_vedit/runtime.js"), html.index("../lib/shared.js"))
        self.assertRegex(html, r'<body data-composition-id="vedit-page" [^>]*data-duration="2.5000" '
                               r'data-width="640" data-height="360" data-no-timeline')
        self.assertIn('"img": "pic.png"', html)          # edit-relative asset, addressed from the page
        self.assertIn('"waitReady": true', html)
        self.assertGreater(html.index("window.VM.__register();"), html.index("window.VM_READY ="))   # after page scripts
        self.assertEqual(HF.meta(b)["duration"], 2.5)

    @unittest.skipUnless(HF.available()[0], "HyperFrames not installed")
    def test_page_console(self):
        self.page.write_text('<html><head><meta name="vedit:duration" content="2"></head><body><script>'
                             'VM.onFrame((t) => { if (t > 0) console.error("FRAME " + t.toFixed(1)); });'
                             'console.error("LOADED"); missing();</script></body></html>')
        lines = HF.page_console(self.page, self.dir / "work", times=[0.5])
        self.assertIn("[page console] LOADED", lines)
        self.assertIn("[page error] missing is not defined", lines)
        self.assertIn("[page console] FRAME 0.5", lines)

    def test_page_keys_cover_declared_deps(self):
        b1 = HF.build(self.page, self.dir / "work")
        self.page.write_text(self.page.read_text().replace('<meta name="vedit:libs"', '<meta name="vedit:deps" content="../lib/shared.js"><meta name="vedit:libs"'))
        b2 = HF.build(self.page, self.dir / "work")
        (self.dir / "lib" / "shared.js").write_text("window.SHARED = 2;")
        b3 = HF.build(self.page, self.dir / "work")
        self.assertEqual(len({b1, b2, b3}), 3)


class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Media.make()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def test_full_render(self):
        extra = {
            "text": [{"text": "TITLE", "style": "title", "at_clip": "c1", "offset": 0.2, "duration": 1.5}],
            "music": [{"path": "music.wav", "volume": 0.5, "duck": True}],
            "sfx": [{"name": "impact", "at_clip": "c4"}] if (ROOT / "assets/sfx/impact.wav").exists() else [],
            "effects": [{"type": "flash", "start": 1.0, "duration": 0.2}],
            "story": {"arc": [{"at": "0%", "tone": "noir"}, {"at": "100%", "tone": "vibrant_pop"}],
                      "look": {"letterbox": 2.39}},
        }
        if HF.available()[0]:
            extra["graphics"] = [{"hyperframes": "lower-third", "start": 0.5, "duration": 1.5,
                                  "variables": {"name": "Test", "role": "Role"}}]
            extra["timeline"] = base_spec()["timeline"] + [
                {"id": "c5", "source": "b", "in": 0, "out": 2,
                 "transition": {"type": "hyperframes", "project": "shape-wipe", "duration": 0.6}},
                {"id": "c6", "source": "a", "in": 0, "out": 1.5, "transition": "light_leak"},
                {"id": "s1", "hyperframes": "scene-stats", "duration": 1.5, "transition": "crossfade",
                 "variables": {"title": "TEST", "stats": [{"value": 42, "label": "answer"}]}}]
        spec_path = self.dir / "edit.json"
        spec_path.write_text(json.dumps(base_spec(**extra)))
        plan = build_plan(spec_path)
        out = render(spec_path, preview=False, jobs=2)
        info = probe(out)
        self.assertTrue(info["has_audio"])
        self.assertEqual((info["width"], info["height"]), (320, 180))
        self.assertAlmostEqual(info["duration"], plan.duration, delta=0.1)
        # second render is served from the segment cache
        out2 = render(spec_path, preview=False, jobs=2)
        self.assertEqual(out, out2)


if __name__ == "__main__":
    unittest.main()
