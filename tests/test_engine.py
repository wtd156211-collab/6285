import math
import unittest

from affinepix import engine

NEAREST = engine.NEAREST
BILINEAR = engine.BILINEAR


class CanvasTests(unittest.TestCase):
    def test_ceil9_removes_float_epsilon(self):
        self.assertEqual(engine.ceil9(3.0 - 1e-12), 3)
        self.assertEqual(engine.ceil9(3.0 + 1e-12), 3)
        self.assertEqual(engine.ceil9(3.0000000005), 4)

    def test_identity_canvas(self):
        cos_t, sin_t = 1.0, 0.0
        self.assertEqual(engine.canvas_size(200, 100, cos_t, sin_t), (200, 100))

    def test_90_rotation_swaps_dims(self):
        cos_t, sin_t = 0.0, 1.0
        self.assertEqual(engine.canvas_size(480, 3, cos_t, sin_t), (3, 480))
        self.assertEqual(engine.canvas_size(5, 160, cos_t, sin_t), (160, 5))

    def test_180_rotation_keeps_dims(self):
        cos_t, sin_t = -1.0, 0.0
        self.assertEqual(engine.canvas_size(256, 192, cos_t, sin_t), (256, 192))

    def test_45_square(self):
        c = abs(math.cos(math.pi / 4))
        self.assertEqual(engine.canvas_size(10, 10, c, c),
                         (math.ceil(round(20 * c, 9)), math.ceil(round(20 * c, 9))))


def _solid(width, height, rgb):
    return bytes(rgb * (width * height))


def _index_image(width, height):
    # 每个像素唯一且可由坐标推回:R=x 模 256,G=y 模 256,B=0。
    out = bytearray(width * height * 3)
    for y in range(height):
        for x in range(width):
            i = (y * width + x) * 3
            out[i] = x % 256
            out[i + 1] = y % 256
    return bytes(out)


class IdentityAndFlipTests(unittest.TestCase):
    def test_identity_nearest_is_exact_copy(self):
        w, h = 8, 6
        src = _index_image(w, h)
        out, wo, ho = engine.transform(src, w, h, 0, w, h, NEAREST)
        self.assertEqual((wo, ho), (w, h))
        self.assertEqual(out, src)

    def test_identity_bilinear_is_exact_copy(self):
        w, h = 8, 6
        src = _index_image(w, h)
        out, _, _ = engine.transform(src, w, h, 0, w, h, BILINEAR)
        self.assertEqual(out, src)

    def test_180_nearest_is_exact_flip(self):
        w, h = 8, 6
        src = _index_image(w, h)
        out, wo, ho = engine.transform(src, w, h, 180, w, h, NEAREST)
        self.assertEqual((wo, ho), (w, h))
        expected = bytearray(len(src))
        for y in range(h):
            for x in range(w):
                si = (y * w + x) * 3
                di = ((h - 1 - y) * w + (w - 1 - x)) * 3
                expected[di:di + 3] = src[si:si + 3]
        self.assertEqual(out, bytes(expected))
        self.assertEqual(sum(out), sum(src))

    def test_180_rotation_sign(self):
        # +180 与 -180 结果相同。
        w, h = 7, 5
        src = _index_image(w, h)
        a, _, _ = engine.transform(src, w, h, 180, w, h, NEAREST)
        b, _, _ = engine.transform(src, w, h, -180, w, h, NEAREST)
        self.assertEqual(a, b)


class OutOfBoundsTests(unittest.TestCase):
    def test_45_corners_are_pure_black(self):
        w, h = 12, 12
        src = _solid(w, h, (200, 100, 50))
        out, wo, ho = engine.transform(src, w, h, 45, w, h, BILINEAR)
        self.assertEqual((out[0:3]), b"\x00\x00\x00")
        for X in (0, wo - 1):
            for Y in (0, ho - 1):
                i = (Y * wo + X) * 3
                self.assertEqual(out[i:i + 3], b"\x00\x00\x00")

    def test_45_nearest_corners_black(self):
        w, h = 12, 12
        src = _solid(w, h, (200, 100, 50))
        out, wo, ho = engine.transform(src, w, h, 45, w, h, NEAREST)
        for X in (0, wo - 1):
            for Y in (0, ho - 1):
                i = (Y * wo + X) * 3
                self.assertEqual(out[i:i + 3], b"\x00\x00\x00")

    def test_edge_pixel_is_weighted_with_black(self):
        # 1x1 源图旋转 45 度:落在图内的像素必须由源像素与黑色按双线性
        # 权重混合(不是边缘复制也不是钳位),图外权重贡献为 0。
        w = h = 1
        src = bytes([100, 150, 200])
        out, wo, ho = engine.transform(src, w, h, 45, w, h, BILINEAR)
        mixed = 0
        for i in range(0, len(out), 3):
            r = out[i]
            if r:
                mixed += 1
                self.assertLess(r, 100)
                self.assertLessEqual(out[i + 1], 150)
                self.assertLessEqual(out[i + 2], 200)
        self.assertGreater(mixed, 0)

    def test_nearest_does_not_clamp_outside(self):
        # 最近邻落在图外必须是黑,而不是复制最边上的像素。
        w, h = 1, 1
        src = bytes([100, 100, 100])
        out, wo, ho = engine.transform(src, w, h, 45, w, h, NEAREST)
        self.assertEqual((wo, ho), (2, 2))
        self.assertEqual(out[0:3], b"\x00\x00\x00")


class ScalingTests(unittest.TestCase):
    def test_double_size_solid(self):
        # 纯色图放大:内部像素保持原色;边缘因图外取黑而变暗(不钳位)。
        w, h = 2, 2
        src = _solid(w, h, (10, 20, 30))
        out, wo, ho = engine.transform(src, w, h, 0, 4, 4, BILINEAR)
        self.assertEqual((wo, ho), (4, 4))
        center = (1 * wo + 1) * 3
        self.assertEqual(out[center:center + 3], bytes([10, 20, 30]))
        self.assertLess(out[0], 10)

    def test_scale_down_half(self):
        # 两个相同灰度像素压到一个输出像素,双线性结果不变。
        src = bytes([100, 100, 100] * 4)
        out, wo, ho = engine.transform(src, 2, 2, 0, 1, 1, BILINEAR)
        self.assertEqual(out, bytes([100, 100, 100]))

    def test_invalid_sample(self):
        with self.assertRaises(engine.EngineError):
            engine.transform(b"\x00" * 12, 2, 2, 0, 2, 2, "cubic")


if __name__ == "__main__":
    unittest.main()
