# Unit checks of images.py (the TGA the engine's loader accepts, palette modes, sizes).
# Run: .venv-tools/bin/python mireina/tools/test-images.py
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import images  # noqa: E402
from PIL import Image  # noqa: E402


def header(path):
    with open(path, "rb") as f:
        return struct.unpack("<BBBHHBHHHHBB", f.read(18))


class ImagesTest(unittest.TestCase):
    def test_free_mode_writes_the_loader_format(self):
        rgb = Image.effect_noise((640, 480), 80).convert("RGB")
        with tempfile.TemporaryDirectory() as d:
            out = images.to_tga(rgb, "dinoscene", Path(d) / "dinoscene.tga")
            idlen, cmaptype, imgtype, cmapstart, cmaplen, cmapbits, x, y, w, h, bpp, desc = header(out)
            self.assertEqual((idlen, cmaptype, imgtype), (0, 1, 1))
            self.assertEqual((cmapstart, cmapbits, bpp), (0, 24, 8))
            self.assertLessEqual(cmaplen, 256)
            self.assertEqual((w, h), (640, 480))
            back = Image.open(out)
            self.assertEqual(back.mode, "P")
            self.assertEqual(back.size, (640, 480))
            self.assertLessEqual(len(set(back.get_flattened_data())), 256)
            self.assertEqual(images.check_tga(out)["size"], (640, 480))

    def test_keep_mode_uses_the_original_palette(self):
        rgb = Image.new("RGB", (640, 480), (200, 30, 60))
        with tempfile.TemporaryDirectory() as d:
            out = images.to_tga(rgb, "bonus", Path(d) / "bonus.tga")
            back = Image.open(out)
            orig = images.palette_of("bonus")
            self.assertEqual(back.getpalette()[: 256 * 3], orig.getpalette()[: 256 * 3], "the original palette is kept verbatim")

    def test_sizes_are_enforced(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                images.to_tga(Image.new("RGB", (640, 480)), "legal", Path(d) / "legal.tga")
            images.to_tga(Image.new("RGB", (420, 251)), "legal", Path(d) / "legal.tga")
            with self.assertRaises(ValueError):
                images.to_tga(Image.new("RGB", (640, 480)), "nope", Path(d) / "nope.tga")

    def test_check_tga_refuses_a_truecolor_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "rgb.tga"
            Image.new("RGB", (8, 8)).save(p, format="TGA")
            with self.assertRaises(AssertionError):
                images.check_tga(p)

    def test_every_committed_original_passes_the_check(self):
        for name in sorted(images.SIZES):
            with self.subTest(name=name):
                info = images.check_tga(images.DATA_IMAGES / f"{name}.tga")
                self.assertEqual(info["size"], images.SIZES[name])

    def test_export_writes_the_gemini_targets(self):
        with tempfile.TemporaryDirectory() as d:
            paths = images.export_originals(Path(d))
            self.assertEqual(sorted(p.stem for p in paths), sorted(images.GEMINI))
            self.assertEqual(Image.open(paths[0]).size, (640, 480))


if __name__ == "__main__":
    unittest.main(verbosity=1)
