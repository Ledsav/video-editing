"""End-to-end and unit tests. Run: python3 -m unittest discover -s tests -v"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vedit import grade as G  # noqa: E402
from vedit import mograph  # noqa: E402
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
        p = self.plan(timeline=[{"id": "s", "scene": "scene_kinetic", "duration": 2.0},
                                {"id": "c", "source": "a", "in": 0, "out": 1}])
        self.assertEqual(p.clips[0].kind, "scene")
        self.assertEqual(p.clips[0].frames, 60)
        self.assertEqual(p.clips[0].grade_start["saturation"], 1.0)   # scenes keep their own colours

    def test_bad_source_range(self):
        with self.assertRaises(Exception):
            build_plan(base_spec(timeline=[{"source": "a", "in": 10, "out": 12}]), self.dir)


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
        if mograph.available()[0]:
            extra["graphics"] = [{"template": "lower_third", "start": 0.5, "duration": 1.5,
                                  "params": {"name": "Test", "role": "Role"}}]
            extra["timeline"] = base_spec()["timeline"] + [
                {"id": "c5", "source": "b", "in": 0, "out": 2,
                 "transition": {"type": "mograph", "template": "shape_wipe", "duration": 0.6}},
                {"id": "s1", "scene": "scene_stats", "duration": 1.5, "transition": "crossfade",
                 "params": {"title": "TEST", "stats": [{"value": 42, "label": "answer"}]}}]
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
