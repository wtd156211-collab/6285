"""24 位未压缩 BMP(BITMAPINFOHEADER / BI_RGB)读写。

内部统一使用规范序像素:自上而下、行优先、每像素 R,G,B 三字节,无行填充。
只处理 README 第二节规定的格式,其余一律抛 BmpError。
"""

import struct

FILE_HEADER = struct.Struct("<2sIHHI")
INFO_HEADER = struct.Struct("<IiiHHIIiiII")
FILE_HEADER_SIZE = 14
INFO_HEADER_SIZE = 40
PIXEL_OFFSET = 54
BYTES_PER_PIXEL = 3


class BmpError(ValueError):
    """位图缺失或不合法。"""


def _stride(width):
    return ((width * BYTES_PER_PIXEL + 3) // 4) * 4


def read_bmp(path):
    """读位图,返回 (width, height, pixels);pixels 是规范序 RGB bytes。"""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as exc:
        raise BmpError("无法读取位图: %s (%s)" % (path, exc))

    if len(data) < FILE_HEADER_SIZE + INFO_HEADER_SIZE:
        raise BmpError("位图过短,缺少完整文件头: %s" % path)
    if data[0:2] != b"BM":
        raise BmpError("不是 BMP 文件(缺 BM 标记): %s" % path)

    _sig, _file_size, _r1, _r2, off_bits = FILE_HEADER.unpack_from(data, 0)
    (header_size, width, height, planes, bit_count, compression,
     _size_image, _x_ppm, _y_ppm, _clr_used, _clr_important) = (
        INFO_HEADER.unpack_from(data, FILE_HEADER_SIZE))

    if header_size != INFO_HEADER_SIZE:
        raise BmpError("只支持 biSize=40 的 BITMAPINFOHEADER: %s" % path)
    if width <= 0 or height <= 0:
        raise BmpError("位图宽高必须为正(不支持自上而下位图): %s" % path)
    if planes != 1:
        raise BmpError("位图 biPlanes 必须为 1: %s" % path)
    if bit_count != 24:
        raise BmpError("只支持 24 位位图: %s" % path)
    if compression != 0:
        raise BmpError("只支持 BI_RGB 未压缩位图: %s" % path)
    if off_bits < PIXEL_OFFSET:
        raise BmpError("bfOffBits 非法: %s" % path)

    stride = _stride(width)
    if len(data) < off_bits + stride * height:
        raise BmpError("像素数据不完整: %s" % path)

    row_bytes = width * BYTES_PER_PIXEL
    pixels = bytearray(width * height * BYTES_PER_PIXEL)
    for y in range(height):
        src_y = off_bits + (height - 1 - y) * stride
        row = data[src_y:src_y + row_bytes]
        dst_y = y * row_bytes
        pixels[dst_y:dst_y + row_bytes:3] = row[2::3]
        pixels[dst_y + 1:dst_y + row_bytes:3] = row[1::3]
        pixels[dst_y + 2:dst_y + row_bytes:3] = row[0::3]
    return width, height, bytes(pixels)


def encode_bmp(width, height, pixels):
    """把规范序 RGB 像素编码为 24 位 BMP 字节串。"""
    if len(pixels) != width * height * BYTES_PER_PIXEL:
        raise BmpError("像素长度与宽高不符")
    stride = _stride(width)
    pad = stride - width * BYTES_PER_PIXEL
    size_image = stride * height
    file_size = PIXEL_OFFSET + size_image
    header = FILE_HEADER.pack(b"BM", file_size, 0, 0, PIXEL_OFFSET)
    header += INFO_HEADER.pack(
        INFO_HEADER_SIZE, width, height, 1, 24, 0, size_image, 0, 0, 0, 0)

    row_bytes = width * BYTES_PER_PIXEL
    pad_bytes = b"\x00" * pad
    out = bytearray(header)
    for y in range(height - 1, -1, -1):
        row_start = y * row_bytes
        rgb = pixels[row_start:row_start + row_bytes]
        line = bytearray(stride)
        line[0:row_bytes:3] = rgb[2::3]
        line[1:row_bytes:3] = rgb[1::3]
        line[2:row_bytes:3] = rgb[0::3]
        if pad:
            line[row_bytes:] = pad_bytes
        out += line
    return bytes(out)


def write_bmp(path, width, height, pixels):
    """把规范序 RGB 像素写成 24 位 BMP 文件。"""
    with open(path, "wb") as f:
        f.write(encode_bmp(width, height, pixels))
