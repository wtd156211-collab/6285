import unittest

from affinepix.bmp import Image
from affinepix.engine import apply, output_size


def gradient(width, height):
    rgb = bytes((x * 3 + y * 5 + c * 11) % 256
                for y in range(height) for x in range(width) for c in range(3))
    return Image(width, height, rgb)


def pixel(image, x, y):
    pos = (y * image.width + x) * 3
    return tuple(image.rgb[pos:pos + 3])


class OutputSizeTest(unittest.TestCase):
    def test_axis_aligned_angles_are_exact(self):
        self.assertEqual(output_size(256, 192, 90), (192, 256))
        self.assertEqual(output_size(256, 192, 180), (256, 192))
        self.assertEqual(output_size(5, 160, -90), (160, 5))
        self.assertEqual(output_size(320, 240, 0), (320, 240))

    def test_rotation_grows_canvas(self):
        self.assertEqual(output_size(256, 192, 30), (318, 295))
        self.assertEqual(output_size(320, 240, 45), (396, 396))


class NearestTest(unittest.TestCase):
    def test_identity_is_exact_copy(self):
        image = gradient(5, 160)
        out = apply(image, 0, 5, 160, "nearest")
        self.assertEqual(out.rgb, image.rgb)

    def test_180_is_exact_flip(self):
        image = gradient(5, 160)
        out = apply(image, 180, 5, 160, "nearest")
        self.assertEqual((out.width, out.height), (5, 160))
        for y in range(160):
            for x in range(5):
                self.assertEqual(pixel(out, x, y), pixel(image, 4 - x, 159 - y))

    def test_90_rotates_counterclockwise(self):
        image = gradient(4, 2)
        out = apply(image, 90, 4, 2, "nearest")
        self.assertEqual((out.width, out.height), (2, 4))
        for y in range(4):
            for x in range(2):
                self.assertEqual(pixel(out, x, y), pixel(image, 3 - y, x))

    def test_out_of_bounds_is_black(self):
        image = Image(2, 2, bytes([255] * 12))
        out = apply(image, 45, 2, 2, "nearest")
        self.assertEqual(pixel(out, 0, 0), (0, 0, 0))
        self.assertEqual(pixel(out, out.width - 1, out.height - 1), (0, 0, 0))


class BilinearTest(unittest.TestCase):
    def test_out_of_bounds_weighs_black(self):
        image = Image(2, 2, bytes([100, 100, 100] * 4))
        out = apply(image, 45, 2, 2, "bilinear")
        corner = pixel(out, 0, 0)
        self.assertTrue(all(0 < channel < 100 for channel in corner))

    def test_weights_match_spec(self):
        # 2x2 source, downscale 1x1: fx = fy = 1.0 -> x0 = y0 = 0, ax = ay = 0.5
        rgb = bytes([0, 0, 0, 40, 0, 0, 0, 0, 80, 0, 0, 0])
        image = Image(2, 2, rgb)
        out = apply(image, 0, 1, 1, "bilinear")
        self.assertEqual((out.width, out.height), (1, 1))
        # 0.25*0 + 0.25*40 + 0.25*0 + 0.25*0 = 10 on R; 0.25*80 = 20 on B
        self.assertEqual(pixel(out, 0, 0), (10, 0, 20))

    def test_pure_color_stays_pure_inside(self):
        image = Image(8, 8, bytes([10, 200, 30] * 64))
        out = apply(image, 0, 4, 4, "bilinear")
        self.assertEqual(out.rgb, bytes([10, 200, 30] * 16))


if __name__ == "__main__":
    unittest.main()
