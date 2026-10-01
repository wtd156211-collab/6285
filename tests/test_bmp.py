import os
import tempfile
import unittest

from affinepix import bmp

SAMPLES = os.path.join(os.path.dirname(__file__), os.pardir, "samples")
IMAGES = os.path.join(SAMPLES, "images")


class ReadBmpTests(unittest.TestCase):
    def test_reads_all_samples(self):
        expected = {
            "texture.bmp": (256, 192), "flat.bmp": (320, 240),
            "edge.bmp": (200, 150), "wide.bmp": (480, 3),
            "narrow.bmp": (5, 160), "big.bmp": (1920, 1080),
        }
        for name, dims in expected.items():
            with self.subTest(name=name):
                w, h, pixels = bmp.read_bmp(os.path.join(IMAGES, name))
                self.assertEqual((w, h), dims)
                self.assertEqual(len(pixels), w * h * 3)

    def test_narrow_has_padding_byte(self):
        # 5 像素宽 -> 行 15 字节,stride 16,带 1 字节填充。
        path = os.path.join(IMAGES, "narrow.bmp")
        data = open(path, "rb").read()
        self.assertEqual(len(data), 54 + 16 * 160)
        w, h, pixels = bmp.read_bmp(path)
        self.assertEqual((w, h), (5, 160))

    def test_missing_file(self):
        with self.assertRaises(bmp.BmpError):
            bmp.read_bmp(os.path.join(IMAGES, "nope.bmp"))

    def test_rejects_bad_headers(self):
        good = open(os.path.join(IMAGES, "wide.bmp"), "rb").read()

        def mutated(offset, data_bytes):
            buf = bytearray(good)
            buf[offset:offset + len(data_bytes)] = data_bytes
            return bytes(buf)

        cases = {
            "no_bm": mutated(0, b"ZZ"),
            "bisize": mutated(14, (41).to_bytes(4, "little")),
            "bitcount": mutated(28, (8).to_bytes(2, "little")),
            "compression": mutated(30, (1).to_bytes(4, "little")),
            "width": mutated(18, (0).to_bytes(4, "little", signed=True)),
            "height": mutated(22, (-3).to_bytes(4, "little", signed=True)),
            "planes": mutated(26, (2).to_bytes(2, "little")),
            "truncated": good[:100],
        }
        for name, blob in cases.items():
            with self.subTest(name=name):
                with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as f:
                    f.write(blob)
                    tmp = f.name
                try:
                    with self.assertRaises(bmp.BmpError):
                        bmp.read_bmp(tmp)
                finally:
                    os.unlink(tmp)


class RoundTripTests(unittest.TestCase):
    def test_roundtrip_all_samples(self):
        for name in sorted(os.listdir(IMAGES)):
            with self.subTest(name=name):
                path = os.path.join(IMAGES, name)
                w, h, pixels = bmp.read_bmp(path)
                encoded = bmp.encode_bmp(w, h, pixels)
                with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as f:
                    f.write(encoded)
                    tmp = f.name
                try:
                    w2, h2, pixels2 = bmp.read_bmp(tmp)
                finally:
                    os.unlink(tmp)
                self.assertEqual((w, h), (w2, h2))
                self.assertEqual(pixels, pixels2)

    def test_header_fields(self):
        w, h, pixels = bmp.read_bmp(os.path.join(IMAGES, "narrow.bmp"))
        encoded = bmp.encode_bmp(w, h, pixels)
        self.assertEqual(encoded[0:2], b"BM")
        self.assertEqual(int.from_bytes(encoded[10:14], "little"), 54)
        self.assertEqual(int.from_bytes(encoded[14:18], "little"), 40)
        self.assertEqual(int.from_bytes(encoded[34:38], "little"), 16 * 160)
        self.assertEqual(len(encoded), 54 + 16 * 160)


if __name__ == "__main__":
    unittest.main()
