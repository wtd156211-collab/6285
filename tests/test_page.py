import os
import tempfile
import unittest

from affinepix.cli import main

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class PageTest(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp.cleanup()
        os.chdir(self._cwd)

    def build(self, name):
        out_dir = os.path.join(self.temp.name, name)
        html_path = os.path.join(self.temp.name, name + ".html")
        self.assertEqual(main(["run", "samples/ops/%s.txt" % name, "--out", out_dir]), 0)
        self.assertEqual(main(["page", "samples/ops/%s.txt" % name,
                               "--dir", out_dir, "--html", html_path]), 0)
        with open(html_path, encoding="utf-8") as handle:
            return html_path, handle.read()

    def test_page_contents(self):
        for name in ("texture", "edge"):
            _, html = self.build(name)
            with open("samples/ops/%s.txt" % name, encoding="utf-8") as handle:
                op_count = len([line for line in handle.read().split("\n")
                                if line and not line.startswith("#")]) - 1
            self.assertEqual(html.count("<section>"), op_count)
            for index in range(1, op_count + 1):
                self.assertIn('id="src-%d"' % index, html)
                self.assertIn('id="dst-%d"' % index, html)
                self.assertIn('id="zoom-%d"' % index, html)
                self.assertIn('id="srcdim-%d"' % index, html)
                self.assertIn('id="dstdim-%d"' % index, html)
            with open(os.path.join(self.temp.name, name, "report.txt"),
                      encoding="utf-8") as handle:
                for line in handle.read().split("\n"):
                    if not line:
                        continue
                    fields = dict(field.split("=", 1) for field in line.split(" ")[1:])
                    self.assertIn("w=%s h=%s" % (fields["w"], fields["h"]), html)
                    self.assertIn("pixels=%s" % fields["pixels"], html)
                    self.assertIn("sum_rgb=%s" % fields["sum_rgb"], html)
                    self.assertIn("sha256=%s" % fields["sha256"], html)
                    self.assertIn("sample=%s" % fields["sample"], html)
            self.assertNotIn(REPO_ROOT, html)
            self.assertNotIn("http://", html)
            self.assertNotIn("https://", html)

    def test_page_is_deterministic(self):
        first_path, first = self.build("texture")
        _, second = self.build("texture")
        self.assertEqual(first, second)

    def test_missing_result_bitmap_is_input_error(self):
        out_dir = os.path.join(self.temp.name, "flat")
        self.assertEqual(main(["run", "samples/ops/flat.txt", "--out", out_dir]), 0)
        os.unlink(os.path.join(out_dir, "flat.02.bmp"))
        code = main(["page", "samples/ops/flat.txt", "--dir", out_dir,
                     "--html", os.path.join(self.temp.name, "flat.html")])
        self.assertEqual(code, 1)


class CliErrorTest(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp.cleanup()
        os.chdir(self._cwd)

    def test_missing_manifest(self):
        code = main(["run", "samples/ops/nope.txt",
                     "--out", os.path.join(self.temp.name, "x")])
        self.assertEqual(code, 1)
        self.assertFalse(os.path.exists(os.path.join(self.temp.name, "x")))

    def test_usage_error(self):
        with self.assertRaises(SystemExit) as ctx:
            main(["run"])
        self.assertEqual(ctx.exception.code, 2)

    def test_invalid_manifest(self):
        bad = os.path.join(self.temp.name, "bad.txt")
        with open(bad, "w", encoding="utf-8") as handle:
            handle.write("image=samples/images/flat.bmp\nangle=0 size=- sample=cubic\n")
        code = main(["run", bad, "--out", os.path.join(self.temp.name, "y")])
        self.assertEqual(code, 1)
        self.assertFalse(os.path.exists(os.path.join(self.temp.name, "y")))


if __name__ == "__main__":
    unittest.main()
