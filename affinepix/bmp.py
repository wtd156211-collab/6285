"""24-bit uncompressed BMP codec (BITMAPINFOHEADER, BI_RGB).

Images are held top-down as tightly packed RGB bytes, one byte per channel.
"""

import struct


class BmpError(ValueError):
    """Raised when a bitmap is missing or does not match the required format."""


class Image:
    __slots__ = ("width", "height", "rgb")

    def __init__(self, width, height, rgb):
        self.width = width
        self.height = height
        self.rgb = rgb


def read_bmp(data):
    if len(data) < 54 or data[0:2] != b"BM":
        raise BmpError("not a BMP file")
    (offset,) = struct.unpack_from("<I", data, 10)
    (header_size, width, height, planes, bit_count, compression) = struct.unpack_from(
        "<IiiHHI", data, 14
    )
    if header_size != 40:
        raise BmpError("unsupported info header size")
    if planes != 1:
        raise BmpError("unsupported plane count")
    if bit_count != 24:
        raise BmpError("only 24-bit BMP is supported")
    if compression != 0:
        raise BmpError("only BI_RGB BMP is supported")
    if width <= 0 or height <= 0:
        raise BmpError("non-positive dimensions")
    stride = (width * 3 + 3) // 4 * 4
    row_bytes = width * 3
    needed = offset + stride * height
    if offset < 54 or len(data) < needed:
        raise BmpError("truncated pixel data")

    rgb = bytearray(width * height * 3)
    dst = 0
    src_row = offset + stride * (height - 1)
    for _ in range(height):
        row = data[src_row:src_row + row_bytes]
        rgb[dst:dst + row_bytes] = row
        dst += row_bytes
        src_row -= stride
    rgb[0::3], rgb[2::3] = rgb[2::3], rgb[0::3]
    return Image(width, height, bytes(rgb))


def encode_bmp(image):
    width, height, rgb = image.width, image.height, image.rgb
    stride = (width * 3 + 3) // 4 * 4
    pad = stride - width * 3
    file_size = 54 + stride * height
    out = bytearray()
    out += b"BM"
    out += struct.pack("<IHHI", file_size, 0, 0, 54)
    out += struct.pack(
        "<IiiHHIIiiII",
        40,
        width,
        height,
        1,
        24,
        0,
        stride * height,
        0,
        0,
        0,
        0,
    )
    blank = b"\x00" * pad
    row_bytes = width * 3
    for src in range(len(rgb) - row_bytes, -1, -row_bytes):
        row = bytearray(rgb[src:src + row_bytes])
        row[0::3], row[2::3] = row[2::3], row[0::3]
        out += row
        if pad:
            out += blank
    return bytes(out)
