"""Draws the tool icons in flim/resources.

All icons share one flat style: 32x32 RGBA on a transparent background, drawn at
8x and downsampled, with the same axes, line weights and colour palette.

The palette is colour-blind safe (based on Okabe & Ito): two groups are always
green and magenta, never red and green; blue is used for single data series and
processing steps, gray for a third group. There is no red or orange.

Usage:
    uv run python scripts/make_icons.py [outdir]   # default: flim/resources
"""

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

S = 8  # supersampling factor
SIZE = 32

# palette
BLUE = (40, 100, 210, 255)  # single data series
LBLUE = (165, 195, 240, 255)
GREEN = (0, 158, 115, 255)  # group 1
LGREEN = (150, 215, 195, 255)
MAGENTA = (204, 51, 170, 255)  # group 2
LMAGENTA = (235, 170, 220, 255)
YELLOW = (240, 215, 70, 255)  # autoencoder bottleneck
NODE = (100, 150, 240, 255)  # autoencoder nodes
DARK = (32, 32, 32, 255)  # axes, outlines, text
GRAY = (128, 128, 128, 255)
LGRAY = (190, 190, 190, 255)
WHITE = (255, 255, 255, 255)
CLEAR = (0, 0, 0, 0)
# sequential, perceptually uniform (viridis samples)
VIRIDIS = [(68, 1, 84), (59, 82, 139), (33, 145, 140), (94, 201, 98), (253, 231, 37)]


# --- helpers ---------------------------------------------------------------


def canvas():
    im = Image.new("RGBA", (SIZE * S, SIZE * S), CLEAR)
    return im, ImageDraw.Draw(im)


def s(*v):
    return [x * S for x in v]


def px(w):
    return max(1, int(round(w * S)))


def circle(d, x, y, r, fill, outline=None, w=0):
    d.ellipse(s(x - r, y - r, x + r, y + r), fill=fill, outline=outline, width=px(w) if w else 0)


def line(d, pts, color, w=1.3):
    d.line([v * S for p in pts for v in p], fill=color, width=px(w), joint="curve")


def arrow(d, x0, y0, x1, y1, color, w=1.6, head=3.2):
    ang = math.atan2(y1 - y0, x1 - x0)
    bx, by = x1 - head * math.cos(ang), y1 - head * math.sin(ang)
    d.line(s(x0, y0, bx, by), fill=color, width=px(w))
    nx, ny = -math.sin(ang), math.cos(ang)
    h = head * 0.7
    d.polygon(s(x1, y1, bx + nx * h, by + ny * h, bx - nx * h, by - ny * h), fill=color)


def double_arrow(d, x, y0, y1, color, w=1.8, head=3.4):
    """Vertical double-headed arrow between y0 and y1."""
    m = (y0 + y1) / 2
    arrow(d, x, m, x, y0, color, w, head)
    arrow(d, x, m, x, y1, color, w, head)


def dashed(d, x0, x1, y, color, w=1.2, dash=2.2, gap=1.6):
    x = x0
    while x < x1:
        d.line(s(x, y, min(x + dash, x1), y), fill=color, width=px(w))
        x += dash + gap


def arc_arrow(d, cx, cy, r, start, end, color, w=1.6, head=3.2):
    """Arrow along a circular arc from angle start to end (degrees, clockwise)."""
    n = 24
    pts = [
        (cx + r * math.cos(math.radians(start + (end - start) * i / n)),
         cy + r * math.sin(math.radians(start + (end - start) * i / n)))
        for i in range(n + 1)
    ]
    line(d, pts[:-3], color, w)
    arrow(d, *pts[-4], *pts[-1], color, w=w, head=head)


def axes(d, x0=3, y0=2, x1=30, y1=29, w=1.3):
    d.line(s(x0, y0, x0, y1), fill=DARK, width=px(w))
    d.line(s(x0, y1, x1, y1), fill=DARK, width=px(w))


def table(d, x0, y0, x1, y1, cols, rows, header=LGRAY, w=1.1, fill=WHITE):
    """A table with a shaded header row; cols/rows are the number of cells."""
    d.rectangle(s(x0, y0, x1, y1), fill=fill, outline=DARK, width=px(w))
    rh = (y1 - y0) / rows
    if header:
        d.rectangle(s(x0, y0, x1, y0 + rh), fill=header, outline=DARK, width=px(w))
    for i in range(1, cols):
        x = x0 + (x1 - x0) * i / cols
        d.line(s(x, y0, x, y1), fill=DARK, width=px(w * 0.7))
    for j in range(1, rows):
        y = y0 + rh * j
        d.line(s(x0, y, x1, y), fill=DARK, width=px(w * 0.7))


def text(d, x, y, txt, size, color=DARK, bold=0.5):
    font = ImageFont.load_default(size=size * S)
    d.text((x * S, y * S), txt, fill=color, font=font, anchor="mm",
           stroke_width=px(bold), stroke_fill=color)


def label(d, x, y, txt, size, color=DARK, halo=1.6):
    """Bold text with a white halo, readable on top of a drawing.

    Uses DejaVu Sans Bold from matplotlib, so the result is the same everywhere.
    """
    import matplotlib

    path = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSans-Bold.ttf"
    font = ImageFont.truetype(str(path), size=size * S)
    d.text((x * S, y * S), txt, fill=color, font=font, anchor="mm",
           stroke_width=px(halo), stroke_fill=WHITE)


def gauss_pts(x0, x1, ybase, height, mu, sigma, n=40):
    pts = []
    for i in range(n + 1):
        t = (i / n - mu) / sigma
        pts.append((x0 + (x1 - x0) * i / n, ybase - height * math.exp(-0.5 * t * t)))
    return pts


def kde_curve(d, x0, x1, ybase, height, mu, sigma, color, w=0.9):
    line(d, gauss_pts(x0, x1, ybase, height, mu, sigma), color, w)


def rotated_ellipse(d, cx, cy, rx, ry, angle_deg, outline, width=1.0, fill=None):
    a = math.radians(angle_deg)
    pts = []
    for i in range(72):
        t = 2 * math.pi * i / 72
        x, y = rx * math.cos(t), ry * math.sin(t)
        pts.append((cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)))
    d.polygon([v * S for p in pts for v in p], outline=outline, fill=fill, width=px(width))


def ae_nodes(d, layers, x0, x1, y_mid, span, r=1.9):
    """Autoencoder: fully connected layers, the bottleneck layer in yellow."""
    cols = [x0 + (x1 - x0) * i / (len(layers) - 1) for i in range(len(layers))]
    pos = []
    for x, n in zip(cols, layers):
        h = span * (n - 1) / (max(layers) - 1)
        pos.append([(x, y_mid - h / 2 + (h * j / (n - 1) if n > 1 else h / 2)) for j in range(n)])
    for a, b in zip(pos, pos[1:]):
        for p in a:
            for q in b:
                d.line(s(*p, *q), fill=LGRAY, width=px(0.5))
    for li, layer in enumerate(pos):
        bottleneck = layers[li] == min(layers)
        for x, y in layer:
            circle(d, x, y, r, YELLOW if bottleneck else NODE)
    return pos


def gear(d, cx, cy, r, color, teeth=8):
    pts = []
    for i in range(teeth * 2):
        for k in (0, 1):
            a = (i + k * 0.9) * math.pi / teeth
            rr = r if i % 2 == 0 else r * 0.72
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon([v * S for p in pts for v in p], fill=color)
    circle(d, cx, cy, r * 0.32, CLEAR)


def badge(d, cx, cy, r=6.2):
    """White-rimmed blue disc for an action symbol in the corner of an icon."""
    circle(d, cx, cy, r + 1, WHITE)
    circle(d, cx, cy, r, BLUE)


def document(d, x0, y0, x1, y1, fold=4, fill=WHITE, w=1.2):
    d.polygon(s(x0, y0, x1 - fold, y0, x1, y0 + fold, x1, y1, x0, y1), fill=fill, outline=DARK, width=px(w))
    d.line(s(x1 - fold, y0, x1 - fold, y0 + fold, x1, y0 + fold), fill=DARK, width=px(w))


# --- File ------------------------------------------------------------------


def fileopen_icon():
    im, d = canvas()
    # folder with a document coming out of it
    d.polygon(s(2, 9, 11, 9, 13.5, 12, 29, 12, 29, 29, 2, 29), fill=LBLUE, outline=DARK, width=px(1.2))
    document(d, 8, 4, 22, 22)
    for y in (11, 14.5, 18):
        d.line(s(10.5, y, 19.5, y), fill=GRAY, width=px(1.1))
    d.polygon(s(2, 29, 6, 16, 31, 16, 29, 29), fill=BLUE, outline=DARK, width=px(1.2))
    return im


def import_icon():
    im, d = canvas()
    # several documents merged into one table
    for i, c in enumerate((GREEN, MAGENTA, GRAY)):
        x, y = 1 + i * 3.2, 1 + i * 3.2
        document(d, x, y, x + 10, y + 12, fold=3)
        d.rectangle(s(x + 2, y + 5, x + 8, y + 7), fill=c)
    arrow(d, 15, 12, 20.5, 17.5, DARK, w=1.7, head=3.4)
    table(d, 15, 19, 31, 31, 3, 3)
    return im


# --- Data ------------------------------------------------------------------


def filter_icon():
    im, d = canvas()
    # mixed dots enter a funnel, only one kind comes out
    for x, y, c in ((5, 3, GREEN), (10, 2, MAGENTA), (15, 3.5, GREEN),
                    (20, 2, MAGENTA), (25, 3, GREEN), (13, 6.5, MAGENTA), (20, 6.5, GREEN)):
        circle(d, x, y, 1.7, c)
    d.polygon(s(2, 9.5, 30, 9.5, 19, 20, 19, 27, 13, 30, 13, 20), fill=GRAY, outline=DARK, width=px(1.2))
    circle(d, 25, 22, 1.7, GREEN)
    circle(d, 25, 28, 1.7, GREEN)
    return im


def concatenate_icon():
    im, d = canvas()
    # two tables stacked into one longer table
    table(d, 1, 2, 12, 12, 2, 3, header=GREEN)
    table(d, 1, 18, 12, 28, 2, 3, header=MAGENTA)
    arrow(d, 13, 7, 18, 10.5, DARK, w=1.5, head=3)
    arrow(d, 13, 23, 18, 19.5, DARK, w=1.5, head=3)
    table(d, 19.5, 2, 31, 15, 2, 4, header=GREEN)
    table(d, 19.5, 15, 31, 28, 2, 4, header=None)
    d.rectangle(s(19.5, 15, 31, 18.25), fill=LMAGENTA, outline=DARK, width=px(1.1))
    d.line(s(25.25, 15, 25.25, 28), fill=DARK, width=px(0.8))
    return im


def merge_icon():
    im, d = canvas()
    # two tables joined side by side
    table(d, 1, 2, 9, 13, 1, 4, header=GREEN)
    table(d, 1, 17, 9, 28, 1, 4, header=MAGENTA)
    arrow(d, 10, 7.5, 14.5, 11.5, DARK, w=1.5, head=3)
    arrow(d, 10, 22.5, 14.5, 18.5, DARK, w=1.5, head=3)
    table(d, 16, 9, 31, 22, 2, 4, header=None)
    d.rectangle(s(16, 9, 23.5, 12.25), fill=GREEN, outline=DARK, width=px(1.1))
    d.rectangle(s(23.5, 9, 31, 12.25), fill=MAGENTA, outline=DARK, width=px(1.1))
    return im


def pivot_icon(reverse=False):
    im, d = canvas()
    # a column of the table becomes the header row (pivot) or vice versa
    table(d, 2, 2, 30, 30, 4, 4, header=None)
    d.rectangle(s(2, 2, 30, 9), fill=LBLUE, outline=DARK, width=px(1.1))
    d.rectangle(s(2, 2, 9, 30), fill=LGREEN, outline=DARK, width=px(1.1))
    d.rectangle(s(2, 2, 9, 9), fill=LGRAY, outline=DARK, width=px(1.1))
    for i in range(1, 4):
        d.line(s(2 + 7 * i, 2, 2 + 7 * i, 9), fill=DARK, width=px(0.8))
        d.line(s(2, 2 + 7 * i, 9, 2 + 7 * i), fill=DARK, width=px(0.8))
    if reverse:
        arc_arrow(d, 9, 9, 15, -5, 85, MAGENTA, w=2.2, head=4.2)
    else:
        arc_arrow(d, 9, 9, 15, 95, 5, MAGENTA, w=2.2, head=4.2)
    return im


def order_icon():
    im, d = canvas()
    # categorical columns swap places: the first and last trade positions
    table(d, 2, 11, 30, 30, 3, 4, header=None)
    for i, c in enumerate((GREEN, LGRAY, MAGENTA)):
        x = 2 + i * 28 / 3
        d.rectangle(s(x, 11, x + 28 / 3, 15.75), fill=c, outline=DARK, width=px(1.1))
    # two-headed arc from the first to the last column
    x0, x1, y = 6.7, 25.3, 9.5
    n = 30
    pts = [(x0 + (x1 - x0) * i / n, y - 7 * math.sin(math.pi * i / n)) for i in range(n + 1)]
    line(d, pts[3:-3], DARK, 1.6)
    arrow(d, *pts[4], *pts[0], DARK, w=1.6, head=3.4)
    arrow(d, *pts[-5], *pts[-1], DARK, w=1.6, head=3.4)
    return im


def sort_icon():
    im, d = canvas()
    # rows reordered by a numerical column: its values increase downwards
    table(d, 2, 2, 23, 30, 2, 5)
    shades = ((220, 232, 250), (175, 200, 242), (125, 160, 230), (80, 125, 220), (40, 100, 210))
    rh = 28 / 5
    for j, c in enumerate(shades[:4]):
        y = 2 + rh * (j + 1)
        d.rectangle(s(12.5, y, 23, y + rh), fill=c + (255,), outline=DARK, width=px(1.1))
    arrow(d, 27.5, 3, 27.5, 29, DARK, w=2.2, head=4.5)
    return im


# --- Analysis --------------------------------------------------------------


def categorize_icon():
    im, d = canvas()
    # price tag: continuous values are put into categories
    a = math.radians(45)
    shape = [(0, 0), (7, -6.5), (20, -6.5), (20, 6.5), (7, 6.5)]
    pts = [(3 + x * math.cos(a) - y * math.sin(a), 3 + x * math.sin(a) + y * math.cos(a)) for x, y in shape]
    d.polygon([v * S for p in pts for v in p], fill=BLUE)
    circle(d, 3 + 6 * math.cos(a), 3 + 6 * math.sin(a), 1.9, CLEAR)
    for i, c in enumerate((GREEN, MAGENTA, GRAY)):
        d.rectangle(s(21, 20 + i * 4, 31, 22.6 + i * 4), fill=c)
    return im


def summary_icon():
    im, d = canvas()
    # summary statistics of a table: a large sum sign over it
    table(d, 2, 3, 30, 29, 3, 5)
    sigma = ((23, 10), (23, 6.5), (9.5, 6.5), (17.5, 16), (9.5, 25.5), (23, 25.5), (23, 22))
    for color, w in ((WHITE, 6.5), (BLUE, 3.4)):
        line(d, sigma, color, w)
        for x, y in sigma:  # round joints and ends
            circle(d, x, y, w / 2, color)
    return im


def relchange_icon():
    im, d = canvas()
    # change relative to a reference: bars grow up or down from the reference line
    axes(d)
    ref = 16
    for x, h in ((6, -9), (12, 5), (18, -12), (24, 7)):
        d.rectangle(s(x, min(ref, ref - h), x + 4.5, max(ref, ref - h)), fill=GREEN if h < 0 else MAGENTA)
    dashed(d, 4, 30, ref, DARK, w=1.4)
    label(d, 8.5, 6.5, "%", 8, halo=1.0)
    return im


def barplot_icon():
    im, d = canvas()
    axes(d)
    for x, h, e in ((6, 13, 3), (13.5, 21, 4), (21, 9, 2.5)):
        d.rectangle(s(x, 29 - h, x + 5.5, 29), fill=BLUE)
        cx = x + 2.75
        d.line(s(cx, 29 - h - e, cx, 29 - h + e), fill=DARK, width=px(1))
        d.line(s(cx - 1.4, 29 - h - e, cx + 1.4, 29 - h - e), fill=DARK, width=px(1))
    return im


def boxplot_icon():
    im, d = canvas()
    axes(d)
    for x, lo, q1, med, q3, hi, fill, c in ((6, 26, 21, 18, 14, 8, LGREEN, GREEN),
                                            (17.5, 22, 15, 11, 8, 3, LMAGENTA, MAGENTA)):
        cx = x + 3.5
        d.line(s(cx, lo, cx, hi), fill=c, width=px(1.1))
        for y in (lo, hi):
            d.line(s(cx - 2, y, cx + 2, y), fill=c, width=px(1.1))
        d.rectangle(s(x, q3, x + 7, q1), fill=fill, outline=c, width=px(1.2))
        d.line(s(x, med, x + 7, med), fill=DARK, width=px(1.5))
    return im


def violin_icon():
    im, d = canvas()
    axes(d)
    for cx, mu, c in ((10.5, 0.62, GREEN), (22, 0.38, MAGENTA)):
        pts = gauss_pts(3, 27, 0, 1, mu, 0.17, n=48)
        right = [(cx + 0.6 + 4.6 * (-w), y) for y, w in pts]
        left = [(cx - 0.6 - 4.6 * (-w), y) for y, w in pts]
        poly = right + left[::-1]
        d.polygon([v * S for p in poly for v in p], fill=c)
        my = 3 + 24 * mu
        d.line(s(cx - 2.5, my, cx + 2.5, my), fill=WHITE, width=px(1.5))
    return im


def swarm_icon():
    im, d = canvas()
    axes(d)
    rows = ((25, 1), (22, 3), (19, 4), (16, 3), (13, 2), (10, 1))
    for cx, c, shift in ((10.5, GREEN, 0), (22, MAGENTA, -6)):
        for y, n in rows:
            for k in range(n):
                circle(d, cx + (k - (n - 1) / 2) * 2.8, y + shift + (0 if shift == 0 else 2), 1.25, c)
    return im


def histogram_icon():
    im, d = canvas()
    axes(d)
    hs = (2, 5, 10, 15, 12, 7, 5, 8, 13, 9, 4, 2)
    for i, h in enumerate(hs):
        x = 4.3 + i * 2.15
        d.rectangle(s(x, 28.4 - h * 1.5, x + 1.9, 28.4), fill=BLUE)
    return im


def kde_icon():
    im, d = canvas()
    axes(d)
    for mu, sg, h, fill, c in ((0.35, 0.15, 22, LGREEN, GREEN), (0.65, 0.17, 17, LMAGENTA, MAGENTA)):
        pts = gauss_pts(4, 30, 28.3, h, mu, sg)
        poly = pts + [(30, 28.3), (4, 28.3)]
        tmp = Image.new("RGBA", (SIZE * S, SIZE * S), CLEAR)
        ImageDraw.Draw(tmp).polygon([v * S for p in poly for v in p], fill=fill[:3] + (140,))
        d._image.alpha_composite(tmp)
        line(d, pts, c, 1.4)
    return im


def lineplot_icon():
    im, d = canvas()
    axes(d)
    pts = ((6, 23), (12, 16), (18, 18), (24.5, 9), (29, 6))
    band = [(x, y - 3.5) for x, y in pts] + [(x, y + 3.5) for x, y in pts[::-1]]
    d.polygon([v * S for p in band for v in p], fill=LBLUE)
    line(d, pts, BLUE, 1.5)
    for x, y in pts:
        circle(d, x, y, 1.6, BLUE)
    return im


def scatter_icon():
    im, d = canvas()
    axes(d)
    for x, y in ((7, 24), (9.5, 20.5), (12, 25), (11, 17), (14.5, 21)):
        circle(d, x, y, 1.7, GREEN)
    for x, y in ((18, 10), (21, 13.5), (23, 7), (25.5, 11), (27, 5.5)):
        circle(d, x, y, 1.7, MAGENTA)
    return im


def kmeans_icon():
    im, d = canvas()
    clusters = ((8, 9, GREEN, ((-3, -2), (2.5, -3), (-2, 3), (3, 2), (0, -0.5))),
                (24, 10, MAGENTA, ((-3, -1), (2, -3.5), (-1, 3), (3, 2.5), (0.5, 0))),
                (15, 24, GRAY, ((-3.5, 0), (2.5, -2.5), (-1, 3.5), (3.5, 2), (0, 0))))
    for cx, cy, c, offs in clusters:
        for dx, dy in offs:
            if c == GRAY:  # third group: different shape, not only a different colour
                d.rectangle(s(cx + dx - 1.4, cy + dy - 1.4, cx + dx + 1.4, cy + dy + 1.4), fill=c)
            else:
                circle(d, cx + dx, cy + dy, 1.5, c)
    for cx, cy, c, _ in clusters:
        for dx, dy in ((-1, -1), (1, -1)):
            d.line(s(cx - 2.3 * dx, cy - 2.3, cx + 2.3 * dx, cy + 2.3), fill=WHITE, width=px(2.6))
        for dx in (-1, 1):
            d.line(s(cx - 2 * dx, cy - 2, cx + 2 * dx, cy + 2), fill=DARK, width=px(1.4))
    return im


def gmm_icon():
    im, d = canvas()
    axes(d)
    for cx, cy, ang, col, light in ((13, 18, -35, GREEN, LGREEN), (20, 12, 25, MAGENTA, LMAGENTA)):
        rotated_ellipse(d, cx, cy, 10.5, 5.6, ang, outline=light, width=1.3)
        rotated_ellipse(d, cx, cy, 6.6, 3.5, ang, outline=col, width=1.3)
        rotated_ellipse(d, cx, cy, 2.6, 1.4, ang, outline=col, width=1.3, fill=col)
    return im


def ks_icon():
    im, d = canvas()
    # two cumulative distributions and their largest distance D; drawn on whole
    # pixels (2 px lines) and reduced with a box filter, so every edge is sharp
    im.info["crisp"] = True

    def rect(x0, y0, x1, y1, color):
        d.rectangle([x0 * S, y0 * S, x1 * S - 1, y1 * S - 1], fill=color)

    def ecdf(steps, color):
        levels = (27, 22, 17, 12, 7, 2)  # line centres, 5 px apart
        x = 4
        for xs, y0, y1 in zip(steps, levels, levels[1:]):
            rect(x, y0 - 1, xs + 1, y0 + 1, color)  # horizontal run
            rect(xs - 1, y1 - 1, xs + 1, y0 + 1, color)  # step up
            x = xs
        rect(x, levels[-1] - 1, 31, levels[-1] + 1, color)

    ecdf((6, 8, 10, 12, 14), GREEN)
    ecdf((13, 19, 22, 25, 28), MAGENTA)
    # D: the largest vertical distance, between x = 14 and 19
    rect(15, 6, 17, 18, BLUE)
    d.polygon(s(16, 3.5, 13, 7, 19, 7), fill=BLUE)
    d.polygon(s(16, 20.5, 13, 17, 19, 17), fill=BLUE)
    rect(2, 2, 4, 30, DARK)  # axes
    rect(2, 28, 31, 30, DARK)
    label(d, 25.5, 23.5, "KS", 9, halo=1.2)
    return im


def pca_icon():
    im, d = canvas()
    # point cloud with its two orthogonal principal axes
    import random

    a = math.radians(-30)
    c, s_ = math.cos(a), math.sin(a)
    cx, cy = 15, 15.5
    rnd = random.Random(3)
    for _ in range(24):
        u, v = rnd.gauss(0, 5.5), rnd.gauss(0, 1.8)
        circle(d, cx + u * c - v * s_, cy + u * s_ + v * c, 1.1, NODE)
    arrow(d, cx, cy, cx + 15.5 * c, cy + 15.5 * s_, MAGENTA, w=3.0, head=5.5)  # PC1
    arrow(d, cx, cy, cx + 15 * s_, cy - 15 * c, GREEN, w=3.0, head=5.5)  # PC2
    circle(d, cx, cy, 1.9, DARK)
    label(d, 16, 26.5, "PCA", 10.5)
    return im


def randomforest_icon():
    im, d = canvas()

    def tree(x, y, w, h, leaves):
        root = (x, y)
        mids = [(x - w / 2, y + h), (x + w / 2, y + h)]
        for m in mids:
            d.line(s(*root, *m), fill=DARK, width=px(0.9))
        lv = [(mids[0][0] - w / 4, y + 2 * h), (mids[0][0] + w / 4, y + 2 * h),
              (mids[1][0] - w / 4, y + 2 * h), (mids[1][0] + w / 4, y + 2 * h)]
        for i, l in enumerate(lv):
            d.line(s(*mids[i // 2], *l), fill=DARK, width=px(0.9))
        circle(d, *root, 1.9, BLUE)
        for m in mids:
            circle(d, *m, 1.6, BLUE)
        for l, c in zip(lv, leaves):
            circle(d, *l, 1.4, c)

    tree(9, 3, 8, 5.5, (GREEN, MAGENTA, GREEN, GREEN))
    tree(23, 3, 8, 5.5, (MAGENTA, GREEN, MAGENTA, MAGENTA))
    tree(16, 17, 8, 5.5, (GREEN, GREEN, MAGENTA, GREEN))
    return im


def heatmap_icon():
    im, d = canvas()
    vals = ((0, 1, 2, 4), (1, 3, 4, 2), (2, 4, 3, 1), (4, 2, 1, 0))
    for j, row in enumerate(vals):
        for i, v in enumerate(row):
            x, y = 2 + i * 7, 2 + j * 7
            d.rectangle(s(x, y, x + 7, y + 7), fill=VIRIDIS[v] + (255,))
    d.rectangle(s(2, 2, 30, 30), outline=DARK, width=px(1.1))
    return im


def seriesanalysis_icon():
    im, d = canvas()
    # one series across columns: its maximum, minimum and range
    axes(d)
    pts = ((6, 20), (11, 13), (16, 17), (21, 7), (25, 23))
    dashed(d, 4, 30, 7, GREEN, w=1.3)
    dashed(d, 4, 30, 23, MAGENTA, w=1.3)
    line(d, pts, BLUE, 1.5)
    for p in pts:
        circle(d, *p, 1.7, BLUE)
    double_arrow(d, 29, 7.5, 22.5, DARK, w=1.8, head=3.2)
    return im


def pairplot_icon():
    im, d = canvas()
    # 2x2 grid of panels: histograms on the diagonal, scatter off-diagonal
    for cx, cy in ((1, 1), (17, 1), (1, 17), (17, 17)):
        d.rectangle(s(cx, cy, cx + 14, cy + 14), outline=GRAY, width=px(1))
    for (cx, cy), hs in (((1, 1), (4, 9, 12, 6, 3)), ((17, 17), (3, 7, 12, 10, 5))):
        for i, h in enumerate(hs):
            x = cx + 1.5 + i * 2.4
            d.rectangle(s(x, cy + 13 - h, x + 2.0, cy + 13), fill=BLUE)
    pts = ((3, 10, GREEN), (5, 11.5, GREEN), (6, 6.5, GREEN), (8.5, 8.5, MAGENTA), (10, 4, MAGENTA), (12, 6, MAGENTA))
    for (cx, cy), flip in (((17, 1), False), ((1, 17), True)):
        for x0, y0, c in pts:
            x, y = (y0, x0) if flip else (x0, y0)
            x, y = (14 - x, 14 - y) if flip else (x, y)
            circle(d, cx + x, cy + y, 1.25, c)
    return im


def flirrplot_icon():
    im, d = canvas()
    # miniature of the FLIRR figure: scatter, three KDEs, FLIRR line plot, bar strip
    panel = dict(outline=GRAY, width=px(0.9))
    d.rectangle(s(0.5, 0.5, 13, 19), **panel)
    for x, y in ((3, 15), (4.5, 12), (6, 14), (7, 10)):
        circle(d, x, y, 1.2, GREEN)
    for x, y in ((8, 7), (9.5, 9), (10.5, 4.5), (11, 7)):
        circle(d, x, y, 1.2, MAGENTA)
    for i in range(3):
        x0 = 14.5 + i * 5.9
        d.rectangle(s(x0, 0.5, x0 + 5.2, 8.5), **panel)
        kde_curve(d, x0 + 0.5, x0 + 4.7, 7.8, 5.6, 0.38, 0.17, GREEN)
        kde_curve(d, x0 + 0.5, x0 + 4.7, 7.8, 5.6, 0.62, 0.17, MAGENTA)
    d.rectangle(s(14.5, 10, 31.5, 19), **panel)
    pts = ((16.5, 16.5), (22, 13.5), (27, 15), (30, 11.5))
    line(d, pts, BLUE, 1.4)
    for x, y in pts:
        circle(d, x, y, 1.1, BLUE)
    d.rectangle(s(0.5, 20.5, 31.5, 31.5), **panel)
    for i, (h, c) in enumerate(((6, GREEN), (8, MAGENTA), (4, GREEN), (7, MAGENTA), (5, GREEN), (9, MAGENTA))):
        x = 3 + i * 4.7
        d.rectangle(s(x, 30.5 - h, x + 3.2, 30.5), fill=c)
    return im


def _ae_with_badge(symbol):
    im, d = canvas()
    ae_nodes(d, (5, 3, 2, 3, 5), 3, 25, 12, 20)
    badge(d, 24.5, 24.5)
    symbol(d, 24.5, 24.5)
    return im


def aerun_icon():
    # autoencoder + play: apply a trained model
    return _ae_with_badge(lambda d, x, y: d.polygon(s(x - 2.2, y - 3.6, x - 2.2, y + 3.6, x + 3.8, y), fill=WHITE))


def aetrain_icon():
    # autoencoder + circular arrow: training iterations
    return _ae_with_badge(lambda d, x, y: arc_arrow(d, x, y, 3.4, 200, 500, WHITE, w=1.5, head=2.6))


def aeaugment_icon():
    # autoencoder + plus: generate additional data
    def plus(d, x, y):
        d.rectangle(s(x - 3.8, y - 1, x + 3.8, y + 1), fill=WHITE)
        d.rectangle(s(x - 1, y - 3.8, x + 1, y + 3.8), fill=WHITE)
    return _ae_with_badge(plus)


# --- Workflow --------------------------------------------------------------


def workflow_icon():
    im, d = canvas()
    # generic workflow: data -> processing steps -> result
    table(d, 1, 2, 11, 11, 2, 3)
    arrow(d, 11.5, 6.5, 17, 6.5, GRAY, w=1.6, head=3)
    circle(d, 23, 6.5, 5, BLUE)
    arrow(d, 23, 12, 23, 17.5, GRAY, w=1.6, head=3)
    circle(d, 23, 23.5, 5, BLUE)
    arrow(d, 17.5, 23.5, 12, 23.5, GRAY, w=1.6, head=3)
    document(d, 2, 17, 11, 30, fold=3)
    for y, c in ((22, GREEN), (25.5, MAGENTA)):
        d.rectangle(s(4, y - 1, 9, y + 1), fill=c)
    return im


def flirrworkflow_icon():
    im, d = canvas()
    # table -> FLIRR ratio -> bar chart
    table(d, 1, 3, 12, 14, 3, 3)
    arrow(d, 13.5, 8.5, 20, 8.5, GRAY, w=1.6, head=3)
    circle(d, 25, 8.5, 5, BLUE)
    d.line(s(22.5, 10.5, 27.5, 6.5), fill=WHITE, width=px(1.4))  # ratio slash
    arrow(d, 25, 14.5, 25, 19.5, GRAY, w=1.6, head=3)
    axes(d, x0=5, y0=21, x1=31, y1=31, w=1.2)
    for i, (h, c) in enumerate(((5, GREEN), (8, MAGENTA), (6, GREEN), (9, MAGENTA))):
        x = 8 + i * 5.6
        d.rectangle(s(x, 30 - h, x + 4, 30), fill=c)
    return im


def aetuneworkflow_icon():
    im, d = canvas()
    ae_nodes(d, (5, 3, 2, 3, 5), 3, 25, 12, 20)
    gear(d, 24.5, 24.5, 7, BLUE)
    return im


def aefeatureworkflow_icon():
    im, d = canvas()
    # encoder half of an autoencoder feeding a 2D latent space plot
    ae_nodes(d, (5, 3, 2), 2.5, 12, 16, 24)
    arrow(d, 14, 16, 18.5, 16, GRAY, w=1.6, head=3)
    axes(d, x0=20, y0=5, x1=31.5, y1=30, w=1.2)
    for x, y in ((23, 9), (25.5, 7.5), (24.5, 11.5), (26.5, 10.5)):
        circle(d, x, y, 1.4, MAGENTA)
    for x, y in ((27, 22), (29.5, 24), (28, 26), (25.5, 25)):
        circle(d, x, y, 1.4, GREEN)
    return im


# --- application icon ------------------------------------------------------

NAVY = (22, 38, 84, 255)


def thick_line(pts, half):
    """Outline of a polyline of width 2 * half, as one smooth polygon."""
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        (xa, ya), (xb, yb) = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        n = math.hypot(xb - xa, yb - ya)
        nx, ny = -(yb - ya) / n * half, (xb - xa) / n * half
        left.append((x + nx, y + ny))
        right.append((x - nx, y - ny))
    return left + right[::-1]


def _app_icon_detailed(r):
    """32-unit layout for 32 px and larger; r(x0, y0, x1, y1) draws a rectangle."""
    d, k = r.draw, r.k
    d.rounded_rectangle(r.q(1, 1, 31, 31), radius=7 * k, fill=NAVY)
    r(6, 11, 8, 25, LBLUE)  # excitation pulse (blue laser)
    star = []  # spark on top of the pulse: 8-pointed, long vertical/horizontal rays
    for i in range(16):
        a = math.pi * i / 8 - math.pi / 2
        rad = (6.6 if i % 4 == 0 else 3.6) if i % 2 == 0 else 1.3
        star.append((7 + rad * math.cos(a), 7 + rad * math.sin(a)))  # may touch the edge
    d.polygon(r.q(*[v for p in star for v in p]), fill=WHITE)
    heights = (17, 10, 6, 4, 2, 1)  # photon histogram of the decay
    for i, h in enumerate(heights):
        r(10 + 3 * i, 25 - h, 12 + 3 * i, 25, GREEN)
    # fitted exponential, just above the bar tops
    pts = [(11 + 3 * t, 23.6 - 17 * math.exp(-0.53 * t)) for t in (j / 20 for j in range(-4, 105))]
    d.polygon(r.q(*[v for p in thick_line(pts, 0.75) for v in p]), fill=MAGENTA)
    r(5, 25, 27, 27, WHITE)  # time axis


def _app_icon_simple(r):
    """16-unit layout for small sizes: whole-pixel shapes only, no curve."""
    r.draw.rounded_rectangle(r.q(0, 0, 16, 16), radius=3.5 * r.k, fill=NAVY)
    r(3, 6, 4, 12, LBLUE)
    r(3, 0, 4, 5, WHITE)  # spark: a plus sign of whole pixels
    r(1, 2, 6, 3, WHITE)
    for i, h in enumerate((8, 5, 3, 2, 1)):
        r(5 + 2 * i, 12 - h, 6 + 2 * i, 12, GREEN)
    r(2, 12, 14, 13, WHITE)


class _Grid:
    """Draws on a grid of units that maps to whole pixels of the target size."""

    def __init__(self, size, units, oversample=4):
        self.size, self.os = size, oversample
        self.k = size / units * oversample
        self.im = Image.new("RGBA", (size * oversample, size * oversample), CLEAR)
        self.draw = ImageDraw.Draw(self.im)

    def q(self, *v):
        return [x * self.k for x in v]

    def __call__(self, x0, y0, x1, y1, color):
        # PIL rectangles include the end pixel
        self.draw.rectangle([round(x0 * self.k), round(y0 * self.k),
                             round(x1 * self.k) - 1, round(y1 * self.k) - 1], fill=color)

    def image(self):
        return self.im.reduce(self.os)  # box filter: aligned edges stay sharp


def app_icon(size):
    """Fluorescence decay: excitation pulse, photon histogram and its fit."""
    simple = size < 32 or size % 32
    grid = _Grid(size, 16 if simple else 32)
    (_app_icon_simple if simple else _app_icon_detailed)(grid)
    return grid.image()


def save_app_icon(outdir):
    app_icon(256).save(outdir / "flimanalyzer.png")
    sizes = (16, 32, 48, 64, 128, 256)
    images = [app_icon(n) for n in sizes]
    images[-1].save(outdir / "flimanalyzer.ico", sizes=[(n, n) for n in sizes], append_images=images[:-1])

ICONS = {
    # File
    "fileopen.png": fileopen_icon,
    "import.png": import_icon,
    # Data
    "concatenate.png": concatenate_icon,
    "filter.png": filter_icon,
    "merge.png": merge_icon,
    "order.png": order_icon,
    "pivot.png": pivot_icon,
    "sort.png": sort_icon,
    "unpivot.png": lambda: pivot_icon(reverse=True),
    # Analysis
    "aeaugment.png": aeaugment_icon,
    "aerun.png": aerun_icon,
    "aetrain.png": aetrain_icon,
    "barplot.png": barplot_icon,
    "boxplot.png": boxplot_icon,
    "categorize.png": categorize_icon,
    "flirrplot.png": flirrplot_icon,
    "gmm.png": gmm_icon,
    "heatmap.png": heatmap_icon,
    "histogram.png": histogram_icon,
    "kde.png": kde_icon,
    "kmeans.png": kmeans_icon,
    "ks.png": ks_icon,
    "lineplot.png": lineplot_icon,
    "pairplot.png": pairplot_icon,
    "pca.png": pca_icon,
    "randomforest.png": randomforest_icon,
    "relchange.png": relchange_icon,
    "scatter.png": scatter_icon,
    "seriesanalysis.png": seriesanalysis_icon,
    "summary.png": summary_icon,
    "swarmplot.png": swarm_icon,
    "violinplot.png": violin_icon,
    # Workflow
    "workflow.png": workflow_icon,
    "flirrworkflow.png": flirrworkflow_icon,
    "aetuneworkflow.png": aetuneworkflow_icon,
    "aefeatureworkflow.png": aefeatureworkflow_icon,
}


def main(outdir):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for name, draw in ICONS.items():
        im = draw()
        crisp = im.info.get("crisp")  # pixel-aligned drawing: average, don't sharpen
        im.resize((SIZE, SIZE), Image.BOX if crisp else Image.LANCZOS).save(outdir / name)
    save_app_icon(outdir)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "flim" / "resources")
