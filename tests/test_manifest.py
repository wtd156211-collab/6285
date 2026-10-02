import unittest

from affinepix.manifest import ParseError, parse_manifest

HEADER = "image=samples/images/flat.bmp\n"
OP = "angle=30 size=- sample=nearest\n"


class ParseTest(unittest.TestCase):
    def test_basic_parse(self):
        path, ops = parse_manifest(HEADER + "\n# comment\n" + OP)
        self.assertEqual(path, "samples/images/flat.bmp")
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0].angle, 30)
        self.assertIsNone(ops[0].tw)
        self.assertEqual(ops[0].sample, "nearest")

    def test_explicit_size(self):
        _, ops = parse_manifest(HEADER + "angle=0 size=64x48 sample=bilinear\n")
        self.assertEqual((ops[0].tw, ops[0].th), (64, 48))
        self.assertEqual(ops[0].size_token, "64x48")

    def test_negative_angle(self):
        _, ops = parse_manifest(HEADER + "angle=-38 size=100x75 sample=bilinear\n")
        self.assertEqual(ops[0].angle, -38)

    def test_missing_image_line(self):
        with self.assertRaises(ParseError):
            parse_manifest("# only a comment\n")

    def test_bad_angle(self):
        with self.assertRaises(ParseError):
            parse_manifest(HEADER + "angle=12.5 size=- sample=nearest\n")
        with self.assertRaises(ParseError):
            parse_manifest(HEADER + "angle=181 size=- sample=nearest\n")

    def test_bad_size(self):
        with self.assertRaises(ParseError):
            parse_manifest(HEADER + "angle=0 size=64*48 sample=nearest\n")
        with self.assertRaises(ParseError):
            parse_manifest(HEADER + "angle=0 size=0x48 sample=nearest\n")

    def test_bad_sample(self):
        with self.assertRaises(ParseError):
            parse_manifest(HEADER + "angle=0 size=- sample=bicubic\n")

    def test_bad_field_order_and_count(self):
        with self.assertRaises(ParseError):
            parse_manifest(HEADER + "angle=0 size=- extra sample=nearest\n")
        with self.assertRaises(ParseError):
            parse_manifest(HEADER + "sample=nearest angle=0 size=-\n")
        with self.assertRaises(ParseError):
            parse_manifest("angle=0 size=- sample=nearest\n")


if __name__ == "__main__":
    unittest.main()
