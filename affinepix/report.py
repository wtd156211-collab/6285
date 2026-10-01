"""report.txt 行生成与像素校验值。

校验口径(README 4.2):规范序(自上而下、行优先、每像素 R,G,B)字节串的
字节和与 sha256。
"""

import hashlib


def checksums(pixels):
    """返回 (sum_rgb, sha256_hex)。"""
    return sum(pixels), hashlib.sha256(pixels).hexdigest()


def report_line(number, angle_deg, size_spec, sample, width, height, pixels):
    sum_rgb, sha = checksums(pixels)
    return ("%d angle=%d size=%s sample=%s w=%d h=%d pixels=%d "
            "sum_rgb=%d sha256=%s" % (
                number, angle_deg, size_spec, sample, width, height,
                width * height, sum_rgb, sha))
