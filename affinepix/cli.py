"""Command line interface: python -m affinepix run|page ..."""

import argparse
import hashlib
import os
import sys

from .bmp import BmpError, encode_bmp, read_bmp
from .engine import apply
from .manifest import ParseError, parse_manifest
from .page import build_page

USAGE_ERROR = 2
INPUT_ERROR = 1


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(USAGE_ERROR, "usage error: %s\n" % message)


def _build_parser():
    parser = _Parser(prog="python -m affinepix")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("manifest")
    run.add_argument("--out", required=True)
    page = sub.add_parser("page")
    page.add_argument("manifest")
    page.add_argument("--dir", required=True)
    page.add_argument("--html", required=True)
    return parser


def _load_manifest(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        raise BmpError("cannot read manifest %s: %s" % (path, exc))
    image_path, ops = parse_manifest(text)
    if not ops:
        raise ParseError("manifest has no transforms")
    return image_path, ops


def _load_image(path):
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        raise BmpError("cannot read bitmap %s: %s" % (path, exc))
    return read_bmp(data)


def _report_line(index, op, image):
    pixels = image.width * image.height
    sum_rgb = sum(image.rgb)
    digest = hashlib.sha256(image.rgb).hexdigest()
    return "%d angle=%d size=%s sample=%s w=%d h=%d pixels=%d sum_rgb=%d sha256=%s" % (
        index, op.angle, op.size_token, op.sample,
        image.width, image.height, pixels, sum_rgb, digest,
    )


def _output_name(manifest_path, index):
    stem = os.path.splitext(os.path.basename(manifest_path))[0]
    return "%s.%02d.bmp" % (stem, index)


def _cmd_run(args):
    image_path, ops = _load_manifest(args.manifest)
    image = _load_image(image_path)
    results = []
    lines = []
    for index, op in enumerate(ops, 1):
        if op.tw is None:
            op.tw = image.width
            op.th = image.height
        out_image = apply(image, op.angle, op.tw, op.th, op.sample)
        results.append((_output_name(args.manifest, index), encode_bmp(out_image)))
        lines.append(_report_line(index, op, out_image))
    report = "".join(line + "\n" for line in lines)

    try:
        os.makedirs(args.out, exist_ok=True)
    except OSError as exc:
        raise BmpError("cannot create output directory: %s" % exc)
    written = []
    try:
        for name, data in results:
            target = os.path.join(args.out, name)
            with open(target, "wb") as handle:
                handle.write(data)
            written.append(target)
        report_path = os.path.join(args.out, "report.txt")
        with open(report_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(report)
        written.append(report_path)
    except OSError as exc:
        for target in written:
            try:
                os.unlink(target)
            except OSError:
                pass
        raise BmpError("cannot write output: %s" % exc)
    return 0


def _parse_report_line(line):
    fields = line.split(" ")
    if len(fields) != 9:
        raise ParseError("bad report line: %r" % line)
    try:
        index = int(fields[0])
    except ValueError:
        raise ParseError("bad report index: %r" % fields[0])
    values = {}
    for field in fields[1:]:
        if "=" not in field:
            raise ParseError("bad report field: %r" % field)
        key, value = field.split("=", 1)
        values[key] = value
    required = {"angle", "size", "sample", "w", "h", "pixels", "sum_rgb", "sha256"}
    if set(values) != required:
        raise ParseError("report fields mismatch")
    return index, values


def _cmd_page(args):
    image_path, ops = _load_manifest(args.manifest)
    try:
        with open(image_path, "rb") as handle:
            source_data = handle.read()
    except OSError as exc:
        raise BmpError("cannot read bitmap %s: %s" % (image_path, exc))
    image = read_bmp(source_data)
    for op in ops:
        if op.tw is None:
            op.tw = image.width
            op.th = image.height

    report_path = os.path.join(args.dir, "report.txt")
    try:
        with open(report_path, "r", encoding="utf-8") as handle:
            report_text = handle.read()
    except OSError as exc:
        raise BmpError("cannot read report %s: %s" % (report_path, exc))
    report_lines = [line for line in report_text.split("\n") if line]
    if len(report_lines) != len(ops):
        raise BmpError("report line count does not match manifest")

    sections = []
    for index, (op, line) in enumerate(zip(ops, report_lines), 1):
        report_index, values = _parse_report_line(line)
        if report_index != index:
            raise BmpError("report index mismatch on line %d" % index)
        name = _output_name(args.manifest, index)
        result_path = os.path.join(args.dir, name)
        try:
            with open(result_path, "rb") as handle:
                result_data = handle.read()
        except OSError as exc:
            raise BmpError("cannot read result bitmap %s: %s" % (result_path, exc))
        result_image = read_bmp(result_data)
        if result_image.width != int(values["w"]) or result_image.height != int(values["h"]):
            raise BmpError("result dimensions do not match report for %s" % name)
        sections.append({
            "index": index,
            "angle": op.angle,
            "size": op.size_token,
            "sample": op.sample,
            "w": result_image.width,
            "h": result_image.height,
            "pixels": values["pixels"],
            "sum_rgb": values["sum_rgb"],
            "sha256": values["sha256"],
            "bmp": result_data,
        })

    html = build_page(source_data, sections)
    try:
        parent = os.path.dirname(os.path.abspath(args.html))
        os.makedirs(parent, exist_ok=True)
        with open(args.html, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(html)
    except OSError as exc:
        raise BmpError("cannot write page: %s" % exc)
    return 0


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            return _cmd_run(args)
        return _cmd_page(args)
    except (BmpError, ParseError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return INPUT_ERROR


if __name__ == "__main__":
    sys.exit(main())
