import hashlib
import os
import tempfile
import unittest

from affinepix.bmp import read_bmp
from affinepix.cli import main

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMES = ["texture", "flat", "edge", "wide", "narrow", "big"]


def run(name, out_dir):
    return main(["run", "samples/ops/%s.txt" % name, "--out", out_dir])


class AcceptanceTest(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp.cleanup()
        os.chdir(self._cwd)

    def report_path(self, name):
        return os.path.join(self.temp.name, name, "report.txt")

    def test_reports_match_expected_byte_for_byte(self):
        for name in NAMES:
            self.assertEqual(run(name, os.path.join(self.temp.name, name)), 0)
            with open(self.report_path(name), "rb") as handle:
                actual = handle.read()
            with open("samples/expected/%s.txt" % name, "rb") as handle:
                expected = handle.read()
            self.assertEqual(actual, expected, "report mismatch for %s" % name)

    def test_checksums_recomputed_from_output_bmps(self):
        for name in NAMES:
            run(name, os.path.join(self.temp.name, name))
            with open(self.report_path(name), encoding="utf-8") as handle:
                lines = [line for line in handle.read().split("\n") if line]
            for line in lines:
                fields = dict(field.split("=", 1) for field in line.split(" ")[1:])
                index = int(line.split(" ", 1)[0])
                path = os.path.join(self.temp.name, name, "%s.%02d.bmp" % (name, index))
                with open(path, "rb") as bmp_file:
                    image = read_bmp(bmp_file.read())
                self.assertEqual(str(image.width), fields["w"])
                self.assertEqual(str(image.height), fields["h"])
                self.assertEqual(str(image.width * image.height), fields["pixels"])
                self.assertEqual(str(sum(image.rgb)), fields["sum_rgb"])
                self.assertEqual(hashlib.sha256(image.rgb).hexdigest(), fields["sha256"])

    def test_texture_nearest_and_bilinear_differ(self):
        run("texture", os.path.join(self.temp.name, "texture"))
        with open(self.report_path("texture"), encoding="utf-8") as handle:
            lines = handle.read().split("\n")
        self.assertNotEqual(lines[0].split("sha256=")[1], lines[1].split("sha256=")[1])

    def test_narrow_copy_and_flip(self):
        run("narrow", os.path.join(self.temp.name, "narrow"))
        with open(self.report_path("narrow"), encoding="utf-8") as handle:
            lines = handle.read().split("\n")
        identity = lines[0].split("sha256=")[1]
        flipped = lines[1].split("sha256=")[1]
        self.assertNotEqual(identity, flipped)
        self.assertEqual(lines[0].split("sum_rgb=")[1].split(" ")[0],
                         lines[1].split("sum_rgb=")[1].split(" ")[0])

        with open("samples/images/narrow.bmp", "rb") as bmp_file:
            source = read_bmp(bmp_file.read())
        with open(os.path.join(self.temp.name, "narrow", "narrow.02.bmp"),
                  "rb") as bmp_file:
            result = read_bmp(bmp_file.read())
        for y in range(source.height):
            for x in range(source.width):
                spos = (y * source.width + x) * 3
                rpos = ((source.height - 1 - y) * source.width + source.width - 1 - x) * 3
                self.assertEqual(source.rgb[spos:spos + 3], result.rgb[rpos:rpos + 3])

    def test_flat_fourth_is_exact_flip(self):
        run("flat", os.path.join(self.temp.name, "flat"))
        with open("samples/images/flat.bmp", "rb") as bmp_file:
            source = read_bmp(bmp_file.read())
        with open(os.path.join(self.temp.name, "flat", "flat.04.bmp"),
                  "rb") as bmp_file:
            result = read_bmp(bmp_file.read())
        self.assertEqual(len(source.rgb), len(result.rgb))
        self.assertNotEqual(source.rgb, result.rgb)
        flipped = bytearray()
        for y in range(source.height - 1, -1, -1):
            row = source.rgb[y * source.width * 3:(y + 1) * source.width * 3]
            for x in range(source.width - 1, -1, -1):
                flipped += row[x * 3:x * 3 + 3]
        self.assertEqual(bytes(flipped), result.rgb)

    def test_reruns_are_byte_identical(self):
        first = os.path.join(self.temp.name, "a")
        second = os.path.join(self.temp.name, "b")
        run("wide", first)
        run("wide", second)
        for filename in sorted(os.listdir(first)):
            with open(os.path.join(first, filename), "rb") as fh1:
                with open(os.path.join(second, filename), "rb") as fh2:
                    self.assertEqual(fh1.read(), fh2.read())


if __name__ == "__main__":
    unittest.main()
