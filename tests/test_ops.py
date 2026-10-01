import os
import tempfile
import unittest

from affinepix import ops as ops_mod

SAMPLES = os.path.join(os.path.dirname(__file__), os.pardir, "samples")
OPS = os.path.join(SAMPLES, "ops")


class ParseSampleTests(unittest.TestCase):
    def test_all_sample_ops_parse(self):
        counts = {"texture": 5, "flat": 4, "edge": 5,
                  "wide": 4, "narrow": 4, "big": 3}
        for name, count in counts.items():
            with self.subTest(name=name):
                image, ops = ops_mod.parse_ops(os.path.join(OPS, name + ".txt"))
                self.assertTrue(image.startswith("samples/images/"))
                self.assertEqual(len(ops), count)
                self.assertEqual([op.number for op in ops],
                                 list(range(1, count + 1)))

    def test_size_dash_means_no_scale(self):
        _, ops = ops_mod.parse_ops(os.path.join(OPS, "texture.txt"))
        self.assertEqual(ops[0].size_spec, "-")
        self.assertIsNone(ops[0].tw)
        self.assertIsNone(ops[0].th)

    def test_explicit_size(self):
        _, ops = ops_mod.parse_ops(os.path.join(OPS, "big.txt"))
        self.assertEqual((ops[0].tw, ops[0].th), (2048, 1152))
        self.assertEqual(ops[0].size_spec, "2048x1152")


class ParseErrorTests(unittest.TestCase):
    def _write(self, text):
        f = tempfile.NamedTemporaryFile(
            "w", suffix=".txt", delete=False, encoding="utf-8")
        f.write(text)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_missing_file(self):
        with self.assertRaises(ops_mod.OpsError):
            ops_mod.parse_ops("/nonexistent/ops.txt")

    def test_empty(self):
        with self.assertRaises(ops_mod.OpsError):
            ops_mod.parse_ops(self._write("# 只有注释\n\n"))

    def test_first_line_must_be_image(self):
        with self.assertRaises(ops_mod.OpsError):
            ops_mod.parse_ops(
                self._write("angle=0 size=- sample=nearest\n"))

    def test_no_ops(self):
        with self.assertRaises(ops_mod.OpsError):
            ops_mod.parse_ops(self._write("image=a.bmp\n"))

    def test_bad_angle(self):
        with self.assertRaises(ops_mod.OpsError):
            ops_mod.parse_ops(
                self._write("image=a.bmp\nangle=x size=- sample=nearest\n"))

    def test_bad_size(self):
        for size in ("10", "10x", "0x5", "-3x5", "axb"):
            with self.subTest(size=size):
                with self.assertRaises(ops_mod.OpsError):
                    ops_mod.parse_ops(self._write(
                        "image=a.bmp\nangle=0 size=%s sample=nearest\n" % size))

    def test_bad_sample(self):
        with self.assertRaises(ops_mod.OpsError):
            ops_mod.parse_ops(
                self._write("image=a.bmp\nangle=0 size=- sample=cubic\n"))

    def test_field_order_fixed(self):
        with self.assertRaises(ops_mod.OpsError):
            ops_mod.parse_ops(
                self._write("image=a.bmp\nsize=- angle=0 sample=nearest\n"))

    def test_comments_and_blanks_ignored(self):
        path = self._write(
            "# 头注释\n\nimage=a.bmp\n\n# 中间注释\n"
            "angle=0 size=- sample=nearest\nangle=90 size=4x5 sample=bilinear\n")
        image, ops = ops_mod.parse_ops(path)
        self.assertEqual(image, "a.bmp")
        self.assertEqual(len(ops), 2)
        self.assertEqual(ops[1].number, 2)


if __name__ == "__main__":
    unittest.main()
