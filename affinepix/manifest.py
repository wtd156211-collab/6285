"""Parsing of transform manifests (samples/ops/<name>.txt)."""

import re

_SIZE_RE = re.compile(r"^([1-9][0-9]*)x([1-9][0-9]*)$")
_ANGLE_RE = re.compile(r"^-?[0-9]+$")


class ParseError(ValueError):
    """Raised when a manifest line does not match the required format."""


class Op:
    __slots__ = ("angle", "size_token", "tw", "th", "sample")

    def __init__(self, angle, size_token, tw, th, sample):
        self.angle = angle
        self.size_token = size_token
        self.tw = tw
        self.th = th
        self.sample = sample


def parse_manifest(text):
    # size=- leaves tw/th as None; the caller fills them from the image.
    image_path = None
    ops = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if image_path is None:
            if " " in line or not line.startswith("image="):
                raise ParseError("first non-comment line must be image=<path>")
            image_path = line[len("image="):]
            if not image_path:
                raise ParseError("empty image path")
            continue
        fields = line.split(" ")
        if len(fields) != 3:
            raise ParseError("bad transform line: %r" % line)
        values = {}
        for field, key in zip(fields, ("angle", "size", "sample")):
            prefix = key + "="
            if not field.startswith(prefix):
                raise ParseError("transform fields must be angle/size/sample in order")
            values[key] = field[len(prefix):]
        angle_token = values["angle"]
        size_token = values["size"]
        sample = values["sample"]
        if not _ANGLE_RE.match(angle_token):
            raise ParseError("angle must be an integer: %r" % angle_token)
        angle = int(angle_token)
        if not -180 <= angle <= 180:
            raise ParseError("angle out of range: %r" % angle_token)
        if sample not in ("nearest", "bilinear"):
            raise ParseError("sample must be nearest or bilinear")
        if size_token == "-":
            tw = th = None
        else:
            match = _SIZE_RE.match(size_token)
            if match is None:
                raise ParseError("size must be <w>x<h> or '-': %r" % size_token)
            tw = int(match.group(1))
            th = int(match.group(2))
            if tw > 4096 or th > 4096:
                raise ParseError("size out of range: %r" % size_token)
        ops.append(Op(angle, size_token, tw, th, sample))
    if image_path is None:
        raise ParseError("manifest has no image line")
    return image_path, ops
