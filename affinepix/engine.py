"""Transform engine: scale to target size, then rotate about the center.

One resampling pass per output pixel, following the fixed formulas:
  u = X + 0.5 - Wo/2, v = Y + 0.5 - Ho/2
  dx = u*cos - v*sin, dy = u*sin + v*cos
  px = tw/2 + dx, py = th/2 + dy
  fx = (px * W) / tw, fy = (py * H) / th
Out-of-bounds samples are black (0, 0, 0).
"""

import math
from operator import sub

from .bmp import Image


def _ceil9(value):
    return math.ceil(round(value, 9))


def output_size(tw, th, deg):
    theta = math.radians(deg)
    c = math.cos(theta)
    s = math.sin(theta)
    wo = _ceil9(abs(tw * c) + abs(th * s))
    ho = _ceil9(abs(tw * s) + abs(th * c))
    return wo, ho


def apply(image, deg, tw, th, sample):
    if sample == "nearest":
        rgb = _nearest(image, deg, tw, th)
    elif sample == "bilinear":
        rgb = _bilinear(image, deg, tw, th)
    else:
        raise ValueError("unknown sample mode: %r" % sample)
    wo, ho = output_size(tw, th, deg)
    return Image(wo, ho, rgb)


def _nearest(image, deg, tw, th):
    src = image.rgb
    width = image.width
    height = image.height
    wo, ho = output_size(tw, th, deg)
    theta = math.radians(deg)
    c = math.cos(theta)
    s = math.sin(theta)
    half_wo = wo / 2
    half_ho = ho / 2
    half_tw = tw / 2
    half_th = th / 2
    floor = math.floor
    out = bytearray(wo * ho * 3)
    pos = 0
    for y_out in range(ho):
        v = y_out + 0.5 - half_ho
        v_sin = v * s
        v_cos = v * c
        ixs = [floor(((half_tw + (x_out + 0.5 - half_wo) * c - v_sin) * width) / tw)
               for x_out in range(wo)]
        iys = [floor(((half_th + (x_out + 0.5 - half_wo) * s + v_cos) * height) / th)
               for x_out in range(wo)]
        for x_out in range(wo):
            ix = ixs[x_out]
            iy = iys[x_out]
            if 0 <= ix < width and 0 <= iy < height:
                src_pos = (iy * width + ix) * 3
                out[pos] = src[src_pos]
                out[pos + 1] = src[src_pos + 1]
                out[pos + 2] = src[src_pos + 2]
            pos += 3
    return bytes(out)


def _bilinear(image, deg, tw, th):
    src = image.rgb
    width = image.width
    height = image.height
    wo, ho = output_size(tw, th, deg)
    theta = math.radians(deg)
    c = math.cos(theta)
    s = math.sin(theta)
    half_wo = wo / 2
    half_ho = ho / 2
    half_tw = tw / 2
    half_th = th / 2
    floor = math.floor
    out = bytearray(wo * ho * 3)
    pos = 0

    if c == 1.0 and s == 0.0:
        # deg == 0: fx depends only on the column, fy only on the row.
        cols = []
        for x_out in range(wo):
            fx = ((half_tw + (x_out + 0.5 - half_wo)) * width) / tw
            x0 = floor(fx - 0.5)
            ax = fx - 0.5 - x0
            cols.append((x0, 1.0 - ax, ax, 0 <= x0 and x0 + 1 < width))
        for y_out in range(ho):
            fy = ((half_th + (y_out + 0.5 - half_ho)) * height) / th
            y0 = floor(fy - 0.5)
            ay = fy - 0.5 - y0
            y_ok = 0 <= y0 and y0 + 1 < height
            way = 1.0 - ay
            for x0, wax, ax, x_ok in cols:
                if x_ok and y_ok:
                    base = (y0 * width + x0) * 3
                    base2 = base + width * 3
                    w00 = wax * way
                    w10 = ax * way
                    w01 = wax * ay
                    w11 = ax * ay
                    for ch in range(3):
                        value = (w00 * src[base + ch] + w10 * src[base + 3 + ch]
                                 + w01 * src[base2 + ch] + w11 * src[base2 + 3 + ch])
                        out[pos + ch] = min(255, floor(value + 0.5))
                else:
                    p00 = _fetch(src, width, height, x0, y0)
                    p10 = _fetch(src, width, height, x0 + 1, y0)
                    p01 = _fetch(src, width, height, x0, y0 + 1)
                    p11 = _fetch(src, width, height, x0 + 1, y0 + 1)
                    w00 = wax * way
                    w10 = ax * way
                    w01 = wax * ay
                    w11 = ax * ay
                    for ch in range(3):
                        value = (w00 * p00[ch] + w10 * p10[ch]
                                 + w01 * p01[ch] + w11 * p11[ch])
                        out[pos + ch] = min(255, floor(value + 0.5))
                pos += 3
        return bytes(out)

    for y_out in range(ho):
        v = y_out + 0.5 - half_ho
        v_sin = v * s
        v_cos = v * c
        fxs = [((half_tw + (x_out + 0.5 - half_wo) * c - v_sin) * width) / tw
               for x_out in range(wo)]
        fys = [((half_th + (x_out + 0.5 - half_wo) * s + v_cos) * height) / th
               for x_out in range(wo)]
        x0s = list(map(floor, map(sub, fxs, [0.5] * wo)))
        y0s = list(map(floor, map(sub, fys, [0.5] * wo)))
        axs = list(map(sub, map(sub, fxs, [0.5] * wo), x0s))
        ays = list(map(sub, map(sub, fys, [0.5] * wo), y0s))
        for x_out in range(wo):
            x0 = x0s[x_out]
            y0 = y0s[x_out]
            ax = axs[x_out]
            ay = ays[x_out]
            wax = 1.0 - ax
            way = 1.0 - ay
            w00 = wax * way
            w10 = ax * way
            w01 = wax * ay
            w11 = ax * ay
            if 0 <= x0 and x0 + 1 < width and 0 <= y0 and y0 + 1 < height:
                base = (y0 * width + x0) * 3
                base2 = base + width * 3
                for ch in range(3):
                    value = (w00 * src[base + ch] + w10 * src[base + 3 + ch]
                             + w01 * src[base2 + ch] + w11 * src[base2 + 3 + ch])
                    out[pos + ch] = min(255, floor(value + 0.5))
            else:
                p00 = _fetch(src, width, height, x0, y0)
                p10 = _fetch(src, width, height, x0 + 1, y0)
                p01 = _fetch(src, width, height, x0, y0 + 1)
                p11 = _fetch(src, width, height, x0 + 1, y0 + 1)
                for ch in range(3):
                    value = (w00 * p00[ch] + w10 * p10[ch]
                             + w01 * p01[ch] + w11 * p11[ch])
                    out[pos + ch] = min(255, floor(value + 0.5))
            pos += 3
    return bytes(out)


def _fetch(src, width, height, ix, iy):
    if 0 <= ix < width and 0 <= iy < height:
        pos = (iy * width + ix) * 3
        return (src[pos], src[pos + 1], src[pos + 2])
    return (0, 0, 0)
