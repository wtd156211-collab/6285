"""run / page 两条命令的编排。"""

import os

from . import bmp, engine, ops as ops_mod, page, report


class RunError(ValueError):
    """输入不可用(位图/清单缺失或不合法、目录不可写)。"""


def result_filename(ops_path, number):
    name = os.path.basename(ops_path)
    if name.lower().endswith(".txt"):
        name = name[:-4]
    return "%s.%02d.bmp" % (name, number)


def execute_run(ops_path, out_dir):
    """执行清单里的全部变换,写结果位图与 report.txt。

    全部算完并校验通过后才开始落盘,失败不留半成品。
    """
    try:
        image_path, ops = ops_mod.parse_ops(ops_path)
        width, height, src = bmp.read_bmp(image_path)
    except (ops_mod.OpsError, bmp.BmpError) as exc:
        raise RunError(str(exc))

    outputs = []
    lines = []
    for op in ops:
        tw = width if op.tw is None else op.tw
        th = height if op.th is None else op.th
        try:
            pixels, wo, ho = engine.transform(
                src, width, height, op.angle_deg, tw, th, op.sample)
        except engine.EngineError as exc:
            raise RunError(str(exc))
        outputs.append((result_filename(ops_path, op.number),
                        bmp.encode_bmp(wo, ho, pixels)))
        lines.append(report.report_line(
            op.number, op.angle_deg, op.size_spec, op.sample, wo, ho, pixels))

    try:
        os.makedirs(out_dir, exist_ok=True)
        if not os.path.isdir(out_dir):
            raise OSError("不是目录")
        for filename, data in outputs:
            with open(os.path.join(out_dir, filename), "wb") as f:
                f.write(data)
        with open(os.path.join(out_dir, "report.txt"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
    except OSError as exc:
        raise RunError("输出目录不可写: %s (%s)" % (out_dir, exc))
    return lines


def execute_page(ops_path, out_dir, html_path):
    """读清单与 run 的输出,生成自包含对比页面。"""
    try:
        image_path, ops = ops_mod.parse_ops(ops_path)
    except ops_mod.OpsError as exc:
        raise RunError(str(exc))

    results = []
    for op in ops:
        filename = result_filename(ops_path, op.number)
        result_path = os.path.join(out_dir, filename)
        if not os.path.isfile(result_path):
            raise RunError("缺少结果位图: %s(请先运行 run)" % result_path)
        results.append((op, filename))

    try:
        page.render_page(ops_path, image_path, ops, results, out_dir, html_path)
    except bmp.BmpError as exc:
        raise RunError(str(exc))
