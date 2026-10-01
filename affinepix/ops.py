"""变换清单解析。

格式(README 4.1):
  image=<位图路径>
  angle=<整数度> size=<宽x高|-> sample=<nearest|bilinear>
'#' 注释与空行忽略;第一条有效行必须是 image=,其余每行一条变换,编号从 1 起。
"""

from collections import namedtuple

from . import engine

Op = namedtuple("Op", "number angle_deg size_spec tw th sample")


class OpsError(ValueError):
    """清单缺失或不合法。"""


def parse_ops(path):
    """解析清单,返回 (image_path, [Op, ...])。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        raise OpsError("无法读取清单: %s (%s)" % (path, exc))

    image_path = None
    ops = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if image_path is None:
            if not line.startswith("image="):
                raise OpsError(
                    "%s:%d 首条有效行必须是 image=<路径>" % (path, lineno))
            image_path = line[len("image="):].strip()
            if not image_path:
                raise OpsError("%s:%d image= 路径为空" % (path, lineno))
            continue
        ops.append(_parse_op_line(line, path, lineno, len(ops) + 1))

    if image_path is None:
        raise OpsError("清单为空,缺少 image= 行: %s" % path)
    if not ops:
        raise OpsError("清单没有任何变换: %s" % path)
    return image_path, ops


def _parse_op_line(line, path, lineno, number):
    fields = line.split(" ")
    if len(fields) != 3:
        raise OpsError(
            "%s:%d 变换行必须是 3 个字段(单空格分隔)" % (path, lineno))
    angle_f, size_f, sample_f = fields

    if not angle_f.startswith("angle="):
        raise OpsError("%s:%d 第一个字段必须是 angle=" % (path, lineno))
    try:
        angle = int(angle_f[len("angle="):], 10)
    except ValueError:
        raise OpsError("%s:%d angle 必须是整数度" % (path, lineno))

    if not size_f.startswith("size="):
        raise OpsError("%s:%d 第二个字段必须是 size=" % (path, lineno))
    size_spec = size_f[len("size="):]
    if size_spec == "-":
        tw = th = None
    else:
        parts = size_spec.split("x")
        if len(parts) != 2:
            raise OpsError("%s:%d size 必须是 <宽>x<高> 或 -" % (path, lineno))
        try:
            tw, th = int(parts[0], 10), int(parts[1], 10)
        except ValueError:
            raise OpsError("%s:%d size 宽高必须是整数" % (path, lineno))
        if tw <= 0 or th <= 0:
            raise OpsError("%s:%d size 宽高必须为正" % (path, lineno))

    if not sample_f.startswith("sample="):
        raise OpsError("%s:%d 第三个字段必须是 sample=" % (path, lineno))
    sample = sample_f[len("sample="):]
    if sample not in engine.SAMPLE_MODES:
        raise OpsError(
            "%s:%d sample 必须是 nearest 或 bilinear" % (path, lineno))

    return Op(number, angle, size_spec, tw, th, sample)
