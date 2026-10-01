import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from affinepix import bmp, report

ROOT = os.path.join(os.path.dirname(__file__), os.pardir)
SAMPLES = os.path.join(ROOT, "samples")
ALL_NAMES = ["texture", "flat", "edge", "wide", "narrow", "big"]


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "affinepix", *args],
        cwd=ROOT, capture_output=True, text=True)


def expected_lines(name):
    path = os.path.join(SAMPLES, "expected", name + ".txt")
    with open(path, encoding="utf-8") as f:
        return [line for line in f.read().splitlines()
                if line.strip() and not line.startswith("#")]


class RunCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out_root = tempfile.mkdtemp(prefix="affinepix_test_")
        cls.addClassCleanup(shutil.rmtree, cls.out_root, True)
        cls.reports = {}
        for name in ALL_NAMES:
            out_dir = os.path.join(cls.out_root, name)
            result = run_cli("run", "samples/ops/%s.txt" % name, "--out", out_dir)
            assert result.returncode == 0, (name, result.stderr)
            with open(os.path.join(out_dir, "report.txt"), encoding="utf-8") as f:
                cls.reports[name] = f.read().splitlines()

    def out_dir(self, name):
        return os.path.join(self.out_root, name)

    def test_reports_match_expected_byte_for_byte(self):
        for name in ALL_NAMES:
            with self.subTest(name=name):
                self.assertEqual(self.reports[name], expected_lines(name))

    def test_output_bitmaps_recompute_to_same_checksums(self):
        for name in ALL_NAMES:
            for i, line in enumerate(self.reports[name], 1):
                with self.subTest(name=name, op=i):
                    fields = dict(tok.split("=", 1)
                                  for tok in line.split(" ")[1:])
                    path = os.path.join(
                        self.out_dir(name), "%s.%02d.bmp" % (name, i))
                    w, h, pixels = bmp.read_bmp(path)
                    sum_rgb, sha = report.checksums(pixels)
                    self.assertEqual(w, int(fields["w"]))
                    self.assertEqual(h, int(fields["h"]))
                    self.assertEqual(w * h, int(fields["pixels"]))
                    self.assertEqual(sum_rgb, int(fields["sum_rgb"]))
                    self.assertEqual(sha, fields["sha256"])

    def test_texture_nearest_differs_from_bilinear(self):
        # 同几何(30°)的最近邻与双线性校验值必须不同。
        line1, line2 = self.reports["texture"][0], self.reports["texture"][1]
        self.assertNotEqual(line1.split("sha256=")[1],
                            line2.split("sha256=")[1])

    def test_narrow_flip_same_sum_different_sha(self):
        # 第 1、2 条:精确复制与精确翻转。
        line1, line2 = self.reports["narrow"][0], self.reports["narrow"][1]
        self.assertEqual(line1.split("sum_rgb=")[1].split(" ")[0],
                         line2.split("sum_rgb=")[1].split(" ")[0])
        self.assertNotEqual(line1.split("sha256=")[1],
                            line2.split("sha256=")[1])

    def test_flat_op4_is_exact_flip(self):
        # flat 第 4 条 180°:输出是原图的精确翻转。
        w, h, src = bmp.read_bmp(os.path.join(SAMPLES, "images", "flat.bmp"))
        out_path = os.path.join(self.out_dir("flat"), "flat.04.bmp")
        ow, oh, out = bmp.read_bmp(out_path)
        self.assertEqual((ow, oh), (w, h))
        flipped = bytearray(len(src))
        row = w * 3
        for y in range(h):
            line = src[y * row:(y + 1) * row]
            rev = bytearray(row)
            for x in range(w):
                rev[(w - 1 - x) * 3:(w - x) * 3] = line[x * 3:(x + 1) * 3]
            flipped[(h - 1 - y) * row:(h - y) * row] = rev
        self.assertEqual(out, bytes(flipped))

    def test_flat_rotated_corners_pure_black(self):
        # flat 第 1 条 45°:四角必须是纯黑。
        path = os.path.join(self.out_dir("flat"), "flat.01.bmp")
        w, h, pixels = bmp.read_bmp(path)
        for x in (0, w - 1):
            for y in (0, h - 1):
                i = (y * w + x) * 3
                self.assertEqual(pixels[i:i + 3], b"\x00\x00\x00",
                                 "corner (%d, %d)" % (x, y))

    def test_run_twice_byte_identical(self):
        for name in ("texture", "big"):
            with self.subTest(name=name):
                first = {}
                for fn in sorted(os.listdir(self.out_dir(name))):
                    with open(os.path.join(self.out_dir(name), fn), "rb") as f:
                        first[fn] = hashlib.sha256(f.read()).hexdigest()
                out2 = os.path.join(self.out_root, name + "_again")
                result = run_cli("run", "samples/ops/%s.txt" % name,
                                 "--out", out2)
                self.assertEqual(result.returncode, 0, result.stderr)
                for fn, sha in first.items():
                    with open(os.path.join(out2, fn), "rb") as f:
                        self.assertEqual(
                            hashlib.sha256(f.read()).hexdigest(), sha, fn)


class ExitCodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="affinepix_exit_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_missing_ops_is_1(self):
        result = run_cli("run", "samples/ops/nope.txt",
                         "--out", self.tmp)
        self.assertEqual(result.returncode, 1)

    def test_missing_image_is_1(self):
        ops_path = os.path.join(self.tmp, "bad.txt")
        with open(ops_path, "w", encoding="utf-8") as f:
            f.write("image=samples/images/nope.bmp\n"
                    "angle=0 size=- sample=nearest\n")
        result = run_cli("run", ops_path, "--out", self.tmp)
        self.assertEqual(result.returncode, 1)

    def test_invalid_ops_is_1_and_writes_nothing(self):
        ops_path = os.path.join(self.tmp, "bad.txt")
        with open(ops_path, "w", encoding="utf-8") as f:
            f.write("image=samples/images/texture.bmp\n"
                    "angle=0 size=- sample=cubic\n")
        out_dir = os.path.join(self.tmp, "out")
        result = run_cli("run", ops_path, "--out", out_dir)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(os.path.exists(out_dir))

    def test_unwritable_dir_is_1(self):
        blocker = os.path.join(self.tmp, "blocker")
        with open(blocker, "w") as f:
            f.write("x")
        result = run_cli("run", "samples/ops/texture.txt",
                         "--out", os.path.join(blocker, "sub"))
        self.assertEqual(result.returncode, 1)

    def test_usage_error_is_2(self):
        self.assertEqual(run_cli().returncode, 2)
        self.assertEqual(run_cli("run").returncode, 2)
        self.assertEqual(run_cli("run", "samples/ops/texture.txt").returncode, 2)
        self.assertEqual(run_cli("bogus").returncode, 2)

    def test_page_missing_results_is_1(self):
        result = run_cli("page", "samples/ops/texture.txt",
                         "--dir", self.tmp,
                         "--html", os.path.join(self.tmp, "p.html"))
        self.assertEqual(result.returncode, 1)


class PageCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="affinepix_page_")
        cls.addClassCleanup(shutil.rmtree, cls.tmp, True)
        cls.pages = {}
        for name in ("texture", "edge"):
            out_dir = os.path.join(cls.tmp, name)
            result = run_cli("run", "samples/ops/%s.txt" % name,
                             "--out", out_dir)
            assert result.returncode == 0, result.stderr
            html_path = os.path.join(cls.tmp, name + ".html")
            result = run_cli("page", "samples/ops/%s.txt" % name,
                             "--dir", out_dir, "--html", html_path)
            assert result.returncode == 0, result.stderr
            with open(html_path, encoding="utf-8") as f:
                cls.pages[name] = f.read()

    def test_page_has_four_required_parts(self):
        for name, page in self.pages.items():
            with self.subTest(name=name):
                # 并排两块画布(原图 + 结果)。
                self.assertIn('id="src1"', page)
                self.assertIn('id="dst1"', page)
                # 尺寸与采样方式标注。
                self.assertIn("sample=nearest", page)
                self.assertIn("px", page)
                # 像素放大视图。
                self.assertIn('id="zoom1"', page)
                self.assertIn("像素放大", page)
                # 数值与 report.txt 同源。
                self.assertIn("sum_rgb=", page)
                self.assertIn("sha256=", page)

    def test_page_dimensions_match_report(self):
        for name in ("texture", "edge"):
            with self.subTest(name=name):
                page = self.pages[name]
                report_path = os.path.join(self.tmp, name, "report.txt")
                with open(report_path, encoding="utf-8") as f:
                    lines = f.read().splitlines()
                for i, line in enumerate(lines, 1):
                    fields = dict(tok.split("=", 1)
                                  for tok in line.split(" ")[1:])
                    dims = "%s×%s" % (fields["w"], fields["h"])
                    self.assertIn(dims, page)
                    self.assertIn(fields["sha256"], page)
                    self.assertIn("sum_rgb=%s" % fields["sum_rgb"], page)

    def test_page_self_contained_and_deterministic(self):
        for name in ("texture", "edge"):
            with self.subTest(name=name):
                page = self.pages[name]
                self.assertNotIn("http://", page)
                self.assertNotIn("https://", page)
                self.assertNotIn(ROOT, page)
                self.assertNotIn(self.tmp, page)
                self.assertIn("data:image/bmp;base64,", page)
                # 再生成一次,逐字节相同。
                html2 = os.path.join(self.tmp, name + "_again.html")
                result = run_cli("page", "samples/ops/%s.txt" % name,
                                 "--dir", os.path.join(self.tmp, name),
                                 "--html", html2)
                self.assertEqual(result.returncode, 0, result.stderr)
                with open(html2, encoding="utf-8") as f:
                    self.assertEqual(f.read(), page)


if __name__ == "__main__":
    unittest.main()
