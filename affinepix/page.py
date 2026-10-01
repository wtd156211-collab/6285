"""自包含对比页面(README 4.3)。

页面里的像素只来自原图与结果两张位图(base64 内嵌),像素宽高来自位图头的读取结果,
页面自身不重算任何几何;无时间戳、绝对路径、外部资源。
"""

import base64
import json
import html
import os

from . import bmp, report

_ZOOM = 8
_CROP = 32

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>位图变换对比 · {name}</title>
<style>
body {{ font-family: sans-serif; margin: 24px; background: #f5f5f5; color: #222; }}
h1 {{ font-size: 20px; }}
section {{ background: #fff; border: 1px solid #ddd; border-radius: 6px;
           padding: 16px 20px; margin: 0 0 24px; }}
h2 {{ font-size: 16px; margin: 0 0 12px; }}
.pair {{ display: flex; flex-wrap: wrap; gap: 24px; align-items: flex-start; }}
figure {{ margin: 0; }}
.pair canvas {{ max-width: 100%; height: auto; border: 1px solid #999;
                image-rendering: pixelated; background: #fff; }}
.zoom canvas {{ border: 1px solid #999; image-rendering: pixelated;
                background: repeating-conic-gradient(#e8e8e8 0% 25%, #fff 0% 50%) 0 / 16px 16px; }}
figcaption {{ font-size: 13px; color: #555; margin-top: 4px; }}
.meta {{ font-family: monospace; font-size: 12px; color: #444; margin: 12px 0 0;
         word-break: break-all; }}
.label {{ font-weight: bold; }}
</style>
</head>
<body>
<h1>位图变换对比 · {name}</h1>
{sections}
<script>
"use strict";
const SOURCE_IMAGE = "data:image/bmp;base64,{src_b64}";
const ENTRIES = {entries};
const ZOOM = {zoom};
const CROP = {crop};

function drawCanvas(canvas, img) {{
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
}}

function drawZoom(canvas, img, w, h) {{
  const cw = Math.min(CROP, w);
  const ch = Math.min(CROP, h);
  const sx = Math.floor((w - cw) / 2);
  const sy = Math.floor((h - ch) / 2);
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, sx, sy, cw, ch, 0, 0, canvas.width, canvas.height);
}}

function render(entry, srcImg) {{
  const num = entry.num;
  drawCanvas(document.getElementById("src" + num), srcImg);
  const dstImg = new Image();
  dstImg.onload = function () {{
    drawCanvas(document.getElementById("dst" + num), dstImg);
    drawZoom(document.getElementById("zoom" + num), dstImg, entry.dw, entry.dh);
  }};
  dstImg.src = entry.dst;
}}

const sourceImg = new Image();
sourceImg.onload = function () {{
  ENTRIES.forEach(function (e) {{ render(e, sourceImg); }});
}};
sourceImg.src = SOURCE_IMAGE;
</script>
</body>
</html>
"""


def _read_bytes(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError as exc:
        raise bmp.BmpError("无法读取文件: %s (%s)" % (path, exc))


def render_page(ops_path, image_path, ops, results, out_dir, html_path):
    """读源位图与 out_dir 下的结果位图,生成自包含 HTML 写到 html_path。

    results: [(Op, result_filename), ...];缺失或读不出的结果位图抛 BmpError。
    """
    name = os.path.basename(ops_path)
    if name.lower().endswith(".txt"):
        name = name[:-4]

    src_bytes = _read_bytes(image_path)
    sw, sh, _src_pixels = bmp.read_bmp(image_path)
    src_b64 = base64.b64encode(src_bytes).decode("ascii")

    sections = []
    entries = []
    for op, result_name in results:
        result_path = os.path.join(out_dir, result_name)
        dst_bytes = _read_bytes(result_path)
        dw, dh, dst_pixels = bmp.read_bmp(result_path)
        dst_b64 = base64.b64encode(dst_bytes).decode("ascii")
        sum_rgb, sha = report.checksums(dst_pixels)

        title = "#%d · angle=%d° · size=%s · sample=%s" % (
            op.number, op.angle_deg, op.size_spec, op.sample)
        zoom_w = min(_CROP, dw) * _ZOOM
        zoom_h = min(_CROP, dh) * _ZOOM
        section = (
            '<section>\n'
            '<h2>{title}</h2>\n'
            '<div class="pair">\n'
            '<figure><canvas id="src{num}" width="{sw}" height="{sh}">'
            '</canvas><figcaption><span class="label">原图</span> '
            '{sw}×{sh} px</figcaption></figure>\n'
            '<figure><canvas id="dst{num}" width="{dw}" height="{dh}">'
            '</canvas><figcaption><span class="label">结果</span> '
            '{dw}×{dh} px · {sample}</figcaption></figure>\n'
            '</div>\n'
            '<figure class="zoom" style="margin-top:12px">'
            '<canvas id="zoom{num}" width="{zw}" height="{zh}"></canvas>'
            '<figcaption><span class="label">像素放大 ×{zoom}</span>：'
            '结果图中心 {cw}×{ch} 像素区域（不平滑，逐像素显示）</figcaption>'
            '</figure>\n'
            '<p class="meta">pixels={pixels} sum_rgb={sum_rgb} '
            'sha256={sha}</p>\n'
            '</section>\n'
        ).format(
            title=html.escape(title), num=op.number, sw=sw, sh=sh,
            dw=dw, dh=dh, sample=html.escape(op.sample),
            zw=zoom_w, zh=zoom_h, zoom=_ZOOM,
            cw=min(_CROP, dw), ch=min(_CROP, dh),
            pixels=dw * dh, sum_rgb=sum_rgb, sha=sha)
        sections.append(section)
        entries.append({
            "num": op.number,
            "dst": "data:image/bmp;base64," + dst_b64,
            "dw": dw,
            "dh": dh,
        })

    page = _PAGE_TEMPLATE.format(
        name=html.escape(name),
        src_b64=src_b64,
        sections="".join(sections),
        entries=json.dumps(entries, separators=(",", ":")),
        zoom=_ZOOM,
        crop=_CROP)
    try:
        with open(html_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(page)
    except OSError as exc:
        raise bmp.BmpError("无法写出页面: %s (%s)" % (html_path, exc))
