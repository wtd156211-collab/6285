import struct
import unittest

from affinepix.bmp import BmpError, Image, encode_bmp, read_bmp


def make_image(width, height):
    rgb = bytes((x * 7 + y * 13 + c * 41) % 256
                for y in range(height) for x in range(width) for c in range(3))
    return Image(width, height, rgb)


class RoundTripTest(unittest.TestCase):
    def test_roundtrip_preserves_pixels(self):
        for width, height in [(1, 1), (5, 160), (3, 2), (16, 9)]:
            image = make_image(width, height)
            decoded = read_bmp(encode_bmp(image))
            self.assertEqual(decoded.width, width)
            self.assertEqual(decoded.height, height)
            self.assertEqual(decoded.rgb, image.rgb)

    def test_stride_padding(self):
        image = make_image(5, 3)
        data = encode_bmp(image)
        self.assertEqual(len(data), 54 + 16 * 3)
        self.assertEqual(struct.unpack_from("<I", data, 10)[0], 54)
        self.assertEqual(struct.unpack_from("<I", data, 34)[0], 16 * 3)
        self.assertEqual(struct.unpack_from("<I", data, 2)[0], len(data))


class InvalidHeaderTest(unittest.TestCase):
    def corrupt(self, offset, fmt, value):
        data = bytearray(self.valid)
        struct.pack_into(fmt, data, offset, value)
        return bytes(data)

    @classmethod
    def setUpClass(cls):
        cls.valid = encode_bmp(make_image(4, 4))

    def test_bad_magic(self):
        with self.assertRaises(BmpError):
            read_bmp(b"ZZ" + self.valid[2:])

    def test_truncated(self):
        with self.assertRaises(BmpError):
            read_bmp(self.valid[:20])
        with self.assertRaises(BmpError):
            read_bmp(self.valid[:-1])

    def test_header_size(self):
        with self.assertRaises(BmpError):
            read_bmp(self.corrupt(14, "<I", 108))

    def test_bit_count(self):
        with self.assertRaises(BmpError):
            read_bmp(self.corrupt(28, "<H", 32))

    def test_compression(self):
        with self.assertRaises(BmpError):
            read_bmp(self.corrupt(30, "<I", 1))

    def test_non_positive_dimensions(self):
        for offset in (18, 22):
            with self.assertRaises(BmpError):
                read_bmp(self.corrupt(offset, "<i", 0))
            with self.assertRaises(BmpError):
                read_bmp(self.corrupt(offset, "<i", -3))


if __name__ == "__main__":
    unittest.main()
