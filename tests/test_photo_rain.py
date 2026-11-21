"""사진 배경 비멍: 칸 크기 · 넓은 칸 · 배경이 없거나 깨졌을 때 원래 비멍으로."""

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

import scenes


def _photo(path: Path) -> None:
    Image.new("RGB", (1200, 720), (150, 170, 180)).save(path)


class PhotoRainTest(unittest.TestCase):
    def test_tiles_are_full_resolution(self):
        p = Path(tempfile.mkdtemp()) / "bg.png"
        _photo(p)
        r = scenes.PhotoRain(str(p), seed=1)
        for _ in range(5):
            r.step(0.2)
        tiles, wide = r.tiles("hint")
        self.assertEqual(len(tiles), 13)
        self.assertEqual(Image.open(io.BytesIO(tiles[0])).size, (196, 196))  # 확대 없이 그대로
        self.assertEqual(Image.open(io.BytesIO(wide)).size, (392, 196))

    def test_feed_flashes_then_fades(self):
        p = Path(tempfile.mkdtemp()) / "bg.png"
        _photo(p)
        r = scenes.PhotoRain(str(p), seed=1)
        r.feed(0)
        self.assertEqual(r.flash, 1.0)
        for _ in range(10):
            r.step(0.2)
        self.assertEqual(r.flash, 0.0)

    def test_make_rain_falls_back_to_pixel_rain(self):
        missing = str(Path(tempfile.mkdtemp()) / "none.png")
        with mock.patch.object(scenes, "RAIN_PHOTO", missing):
            self.assertIsInstance(scenes.make_rain(1), scenes.Rain)
        broken = Path(tempfile.mkdtemp()) / "broken.png"
        broken.write_bytes(b"not an image")
        with mock.patch.object(scenes, "RAIN_PHOTO", str(broken)):
            self.assertIsInstance(scenes.make_rain(1), scenes.Rain)

    def test_make_rain_uses_photo_when_present(self):
        p = Path(tempfile.mkdtemp()) / "bg.png"
        _photo(p)
        with mock.patch.object(scenes, "RAIN_PHOTO", str(p)):
            self.assertIsInstance(scenes.make_rain(1), scenes.PhotoRain)


if __name__ == "__main__":
    unittest.main()
