"""affinepix: 24-bit BMP rotation and scaling with fixed sampling rules."""

from .bmp import Image, BmpError, encode_bmp, read_bmp
from .engine import apply
from .manifest import Op, ParseError, parse_manifest

__all__ = ["Image", "BmpError", "encode_bmp", "read_bmp", "apply", "Op", "ParseError", "parse_manifest"]
