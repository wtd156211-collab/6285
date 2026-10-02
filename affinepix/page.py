"""Self-contained comparison page built from engine outputs.

The page embeds the source and result bitmaps as base64 and lets the
browser read dimensions and pixels straight out of those bytes; no
geometry is recomputed in the page.
"""

import base64
import json

ZOOM_FACTOR = 8
ZOOM_CROP_W = 32
ZOOM_CROP_H = 24

_CSS = """
body { font-family: sans-serif; margin: 16px; background: #f4f4f4; color: #222; }
h1 { font-size: 20px; }
section { background: #fff; border: 1px solid #ccc; border-radius: 4px;
          padding: 12px 16px; margin-bottom: 16px; }
h2 { font-size: 15px; margin: 4px 0 8px; font-family: monospace; }
.meta { font-family: monospace; font-size: 12px; color: #555; margin-bottom: 8px; }
.row { display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap; }
figure { margin: 0; }
figcaption { font-size: 12px; color: #444; margin-top: 4px; }
canvas { border: 1px solid #999; background: #fff; image-rendering: pixelated; }
.zoom { margin-top: 10px; }
.zoom .label { font-size: 12px; color: #444; margin-bottom: 4px; }
""".strip()

_JS = r"""
function parseBmp(bytes) {
  var view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (bytes.length < 54 || bytes[0] !== 0x42 || bytes[1] !== 0x4d) {
    throw new Error("not a BMP");
  }
  var offset = view.getUint32(10, true);
  var width = view.getInt32(18, true);
  var height = view.getInt32(22, true);
  var bits = view.getUint16(28, true);
  var compression = view.getUint32(30, true);
  if (bits !== 24 || compression !== 0 || width <= 0 || height <= 0) {
    throw new Error("unsupported BMP");
  }
  var stride = Math.floor((width * 3 + 3) / 4) * 4;
  return { width: width, height: height, offset: offset, stride: stride, bytes: bytes };
}

function decode(b64) {
  var text = atob(b64);
  var bytes = new Uint8Array(text.length);
  for (var i = 0; i < text.length; i++) bytes[i] = text.charCodeAt(i);
  return bytes;
}

function toImageData(bmp) {
  var out = new ImageData(bmp.width, bmp.height);
  var dst = out.data;
  for (var y = 0; y < bmp.height; y++) {
    var row = bmp.offset + (bmp.height - 1 - y) * bmp.stride;
    for (var x = 0; x < bmp.width; x++) {
      var src = row + x * 3;
      var pos = (y * bmp.width + x) * 4;
      dst[pos] = bmp.bytes[src + 2];
      dst[pos + 1] = bmp.bytes[src + 1];
      dst[pos + 2] = bmp.bytes[src];
      dst[pos + 3] = 255;
    }
  }
  return out;
}

function draw(canvas, bmp) {
  canvas.width = bmp.width;
  canvas.height = bmp.height;
  canvas.getContext("2d").putImageData(toImageData(bmp), 0, 0);
}

function drawZoom(canvas, bmp, cropW, cropH, factor) {
  var w = Math.min(cropW, bmp.width);
  var h = Math.min(cropH, bmp.height);
  var x0 = Math.floor((bmp.width - w) / 2);
  var y0 = Math.floor((bmp.height - h) / 2);
  var crop = new ImageData(w, h);
  var dst = crop.data;
  for (var y = 0; y < h; y++) {
    var row = bmp.offset + (bmp.height - 1 - (y0 + y)) * bmp.stride;
    for (var x = 0; x < w; x++) {
      var src = row + (x0 + x) * 3;
      var pos = (y * w + x) * 4;
      dst[pos] = bmp.bytes[src + 2];
      dst[pos + 1] = bmp.bytes[src + 1];
      dst[pos + 2] = bmp.bytes[src];
      dst[pos + 3] = 255;
    }
  }
  var tmp = document.createElement("canvas");
  tmp.width = w;
  tmp.height = h;
  tmp.getContext("2d").putImageData(crop, 0, 0);
  canvas.width = w * factor;
  canvas.height = h * factor;
  var ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(tmp, 0, 0, canvas.width, canvas.height);
}

window.addEventListener("DOMContentLoaded", function () {
  var source = parseBmp(decode(DATA.source));
  DATA.sections.forEach(function (section) {
    var result = parseBmp(decode(section.bmp));
    draw(document.getElementById("src-" + section.index), source);
    draw(document.getElementById("dst-" + section.index), result);
    document.getElementById("srcdim-" + section.index).textContent =
      source.width + "×" + source.height;
    document.getElementById("dstdim-" + section.index).textContent =
      result.width + "×" + result.height;
    drawZoom(document.getElementById("zoom-" + section.index), result,
             DATA.zoomCropW, DATA.zoomCropH, DATA.zoomFactor);
  });
});
""".strip()

_SECTION_TEMPLATE = """<section>
<h2>#{index} angle={angle} size={size} sample={sample}</h2>
<div class="meta">w={w} h={h} pixels={pixels} sum_rgb={sum_rgb} sha256={sha256}</div>
<div class="row">
<figure><canvas id="src-{index}"></canvas><figcaption>原图 <span id="srcdim-{index}"></span> 像素</figcaption></figure>
<figure><canvas id="dst-{index}"></canvas><figcaption>结果 <span id="dstdim-{index}"></span> 像素</figcaption></figure>
</div>
<div class="zoom">
<div class="label">结果像素放大视图（中心区域，{factor}× 最近邻放大）</div>
<canvas id="zoom-{index}"></canvas>
</div>
</section>"""


def build_page(source_bmp, sections):
    """sections: list of dicts with index/angle/size/sample/w/h/pixels/
    sum_rgb/sha256 and the result BMP bytes under key "bmp"."""
    data = {
        "source": base64.b64encode(source_bmp).decode("ascii"),
        "zoomFactor": ZOOM_FACTOR,
        "zoomCropW": ZOOM_CROP_W,
        "zoomCropH": ZOOM_CROP_H,
        "sections": [
            {"index": section["index"], "bmp": base64.b64encode(section["bmp"]).decode("ascii")}
            for section in sections
        ],
    }
    parts = []
    for section in sections:
        parts.append(_SECTION_TEMPLATE.format(
            index=section["index"],
            angle=section["angle"],
            size=section["size"],
            sample=section["sample"],
            w=section["w"],
            h=section["h"],
            pixels=section["pixels"],
            sum_rgb=section["sum_rgb"],
            sha256=section["sha256"],
            factor=ZOOM_FACTOR,
        ))
    body = "\n".join(parts)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        "<title>affinepix 对比页面</title>\n"
        "<style>\n" + _CSS + "\n</style>\n</head>\n<body>\n"
        "<h1>affinepix 变换对比</h1>\n"
        + body + "\n"
        "<script>\nvar DATA = " + json.dumps(data, ensure_ascii=True) + ";\n"
        + _JS + "\n</script>\n</body>\n</html>\n"
    )
