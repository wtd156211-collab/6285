"""位图变换引擎:先缩放到目标尺寸,再绕中心旋转,单次重采样。

口径见 README 第三节。关键数值顺序:
  u = X+0.5-Wo/2, v = Y+0.5-Ho/2
  dx = u*cos - v*sin, dy = u*sin + v*cos
  px = tw/2 + dx, py = th/2 + dy
  fx = (px*W)/tw, fy = (py*H)/th          # 先乘后除
列方向的 u*cos、u*sin 预计算;只是把同样的乘法结果缓存起来,取值与逐像素直算完全一致。
"""

import math

NEAREST = "nearest"
BILINEAR = "bilinear"
SAMPLE_MODES = (NEAREST, BILINEAR)


class EngineError(ValueError):
    """变换参数非法。"""


def ceil9(value):
    """先四舍五入到 9 位小数再向上取整,避免 90/180 度多出像素。"""
    return math.ceil(round(value, 9))


def canvas_size(tw, th, cos_t, sin_t):
    wo = ceil9(abs(tw * cos_t) + abs(th * sin_t))
    ho = ceil9(abs(tw * sin_t) + abs(th * cos_t))
    return wo, ho


def transform(src, width, height, deg, tw, th, sample):
    """对规范序 RGB 像素做一次「缩放 + 绕中心旋转」。

    返回 (pixels, wo, ho)。sample 必须由调用方(清单)指定,引擎不自选。
    """
    if sample not in SAMPLE_MODES:
        raise EngineError("未知采样方式: %r" % (sample,))
    if tw <= 0 or th <= 0:
        raise EngineError("目标尺寸必须为正")
    if width <= 0 or height <= 0:
        raise EngineError("源尺寸必须为正")

    theta = deg * math.pi / 180.0
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    wo, ho = canvas_size(tw, th, cos_t, sin_t)

    half_wo = wo / 2.0
    half_ho = ho / 2.0
    u_cos = [(x + 0.5 - half_wo) * cos_t for x in range(wo)]
    u_sin = [(x + 0.5 - half_wo) * sin_t for x in range(wo)]

    out = bytearray(wo * ho * 3)
    ctx = _Ctx(src, width, height, out, wo, ho, tw, th,
               u_cos, u_sin, sin_t, cos_t, half_ho)
    if sample == NEAREST:
        ctx.resample_nearest()
    else:
        ctx.resample_bilinear()
    return bytes(out), wo, ho


class _Ctx:
    def __init__(self, src, width, height, out, wo, ho, tw, th,
                 u_cos, u_sin, sin_t, cos_t, half_ho):
        self.src = src
        self.W = width
        self.H = height
        self.out = out
        self.wo = wo
        self.ho = ho
        self.tw = tw
        self.th = th
        self.u_cos = u_cos
        self.u_sin = u_sin
        self.sin_t = sin_t
        self.cos_t = cos_t
        self.half_ho = half_ho

    def resample_nearest(self):
        src = self.src
        W = self.W
        H = self.H
        wo = self.wo
        ho = self.ho
        tw = self.tw
        th = self.th
        out = self.out
        u_cos = self.u_cos
        u_sin = self.u_sin
        sin_t = self.sin_t
        cos_t = self.cos_t
        half_ho = self.half_ho
        floor = math.floor
        tw2 = tw / 2.0
        th2 = th / 2.0
        wmax = W - 1
        hmax = H - 1
        row_len = wo * 3

        for y in range(ho):
            v = y + 0.5 - half_ho
            v_sin = v * sin_t
            v_cos = v * cos_t
            dst_base = y * row_len
            for x in range(wo):
                dx = u_cos[x] - v_sin
                dy = u_sin[x] + v_cos
                fx = ((tw2 + dx) * W) / tw
                fy = ((th2 + dy) * H) / th
                ix = floor(fx)
                iy = floor(fy)
                if 0 <= ix <= wmax and 0 <= iy <= hmax:
                    si = (iy * W + ix) * 3
                    di = dst_base + x * 3
                    out[di] = src[si]
                    out[di + 1] = src[si + 1]
                    out[di + 2] = src[si + 2]

    def resample_bilinear(self):
        src = self.src
        W = self.W
        H = self.H
        wo = self.wo
        ho = self.ho
        tw = self.tw
        th = self.th
        out = self.out
        u_cos = self.u_cos
        u_sin = self.u_sin
        sin_t = self.sin_t
        cos_t = self.cos_t
        half_ho = self.half_ho
        floor = math.floor
        tw2 = tw / 2.0
        th2 = th / 2.0
        xmin = 0
        xmax = W - 2
        ymax = H - 2
        src_row = W * 3
        row_len = wo * 3

        for y in range(ho):
            v = y + 0.5 - half_ho
            v_sin = v * sin_t
            v_cos = v * cos_t
            dst_base = y * row_len
            for x in range(wo):
                dx = u_cos[x] - v_sin
                dy = u_sin[x] + v_cos
                fx = ((tw2 + dx) * W) / tw
                fy = ((th2 + dy) * H) / th

                gx = fx - 0.5
                gy = fy - 0.5
                x0 = floor(gx)
                y0 = floor(gy)
                ax = gx - x0
                ay = gy - y0
                di = dst_base + x * 3

                if xmin <= x0 <= xmax and 0 <= y0 <= ymax:
                    si = y0 * src_row + x0 * 3
                    sj = si + src_row
                    wx0 = 1.0 - ax
                    wy0 = 1.0 - ay
                    w00 = wx0 * wy0
                    w10 = ax * wy0
                    w01 = wx0 * ay
                    w11 = ax * ay

                    r = (w00 * src[si] + w10 * src[si + 3]
                         + w01 * src[sj] + w11 * src[sj + 3])
                    g = (w00 * src[si + 1] + w10 * src[si + 4]
                         + w01 * src[sj + 1] + w11 * src[sj + 4])
                    b = (w00 * src[si + 2] + w10 * src[si + 5]
                         + w01 * src[sj + 2] + w11 * src[sj + 5])
                    ir = floor(r + 0.5)
                    ig = floor(g + 0.5)
                    ib = floor(b + 0.5)
                    out[di] = 255 if ir > 255 else (0 if ir < 0 else ir)
                    out[di + 1] = 255 if ig > 255 else (0 if ig < 0 else ig)
                    out[di + 2] = 255 if ib > 255 else (0 if ib < 0 else ib)
                else:
                    self._bilinear_edge(x0, y0, ax, ay, di)

    def _bilinear_edge(self, x0, y0, ax, ay, di):
        src = self.src
        W = self.W
        H = self.H
        src_row = W * 3
        wx0 = 1.0 - ax
        wy0 = 1.0 - ay
        weights = (
            (x0, y0, wx0 * wy0),
            (x0 + 1, y0, ax * wy0),
            (x0, y0 + 1, wx0 * ay),
            (x0 + 1, y0 + 1, ax * ay),
        )
        r = g = b = 0.0
        for cx, cy, w in weights:
            if 0 <= cx < W and 0 <= cy < H:
                si = cy * src_row + cx * 3
                r += w * src[si]
                g += w * src[si + 1]
                b += w * src[si + 2]
        self.out[di] = _round_clamp(r)
        self.out[di + 1] = _round_clamp(g)
        self.out[di + 2] = _round_clamp(b)


def _round_clamp(value):
    iv = math.floor(value + 0.5)
    if iv < 0:
        return 0
    if iv > 255:
        return 255
    return iv
