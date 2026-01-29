#!/usr/bin/env python3
import argparse
import json
import sys
from dataclasses import dataclass
from typing import Optional, Tuple, List

import fitz  # PyMuPDF


# =========================
# Config (DEFAULT)
# =========================
@dataclass
class Opt:
    text: str = "LUNAS"
    rotate: float = -25.0
    opacity: float = 0.18

    # watermark size rule:
    # watermark width = 10% of main content width
    wmWidthPctOfContent: float = 0.15

    # micro shift relative to detected "total box"
    shiftXPctOfContent: float = 0.015  # geser kanan dikit
    shiftYPctOfContent: float = 0.010  # geser bawah dikit


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def parse_options(s: str) -> Opt:
    """
    Options optional; for safety if server sends it.
    """
    o = Opt()
    if not s:
        return o
    try:
        d = json.loads(s)
    except Exception:
        return o

    if isinstance(d, dict):
        o.text = str(d.get("text", o.text))
        o.rotate = float(d.get("rotate", o.rotate))
        o.opacity = float(d.get("opacity", o.opacity))
        o.wmWidthPctOfContent = float(d.get("wmWidthPctOfContent", o.wmWidthPctOfContent))
        o.shiftXPctOfContent = float(d.get("shiftXPctOfContent", o.shiftXPctOfContent))
        o.shiftYPctOfContent = float(d.get("shiftYPctOfContent", o.shiftYPctOfContent))
    return o


# =========================
# Content detection
# =========================
def pick_main_content_rect(page: fitz.Page) -> Optional[fitz.Rect]:
    """
    Union of meaningful text blocks, ignoring header/footer & far-left sidebar.
    """
    blocks = page.get_text("blocks")
    if not blocks:
        return None

    pw, ph = page.rect.width, page.rect.height

    # safe zone ignore header/footer
    y_top = ph * 0.12
    y_bot = ph * 0.92

    rects: List[fitz.Rect] = []
    for b in blocks:
        r = fitz.Rect(float(b[0]), float(b[1]), float(b[2]), float(b[3]))
        if r.is_empty or r.width < 30 or r.height < 10:
            continue
        if r.y1 < y_top or r.y0 > y_bot:
            continue

        # ignore far-left sidebar
        if r.x1 < pw * 0.25:
            continue

        rects.append(r)

    if not rects:
        return None

    u = rects[0]
    for r in rects[1:]:
        u |= r
    return u


def find_total_like_rect(page: fitz.Page) -> Optional[fitz.Rect]:
    """
    Find a rect around TOTAL/DUE area by scanning words.
    Strategy:
      - get words (x0,y0,x1,y1,text)
      - keep keywords (TOTAL, DUE, BALANCE, AMOUNT DUE, GRAND TOTAL, BALANCE DUE, etc.)
      - choose the one with largest (y + x) score => bottom-right-ish
      - expand that word rect to a "total box" heuristically
    """
    words = page.get_text("words")  # list of tuples
    if not words:
        return None

    keywords = [
        "total",
        "amount due",
        "balance due",
        "balance",
        "due",
        "grand total",
        "total due",
        "invoice total",
    ]

    # normalize word list to searchable items
    candidates: List[Tuple[fitz.Rect, str]] = []
    for w in words:
        x0, y0, x1, y1, text = float(w[0]), float(w[1]), float(w[2]), float(w[3]), str(w[4])
        t = " ".join(text.lower().split())
        if not t:
            continue
        # simple keyword check (word-level); good enough for invoices
        for k in keywords:
            if k in t:
                candidates.append((fitz.Rect(x0, y0, x1, y1), t))
                break

    if not candidates:
        return None

    pw, ph = page.rect.width, page.rect.height

    # choose bottom-right-ish candidate
    best = None
    best_score = -1.0
    for r, t in candidates:
        score = (r.y1 / ph) * 2.0 + (r.x1 / pw) * 1.0
        if score > best_score:
            best_score = score
            best = r

    if best is None:
        return None

    # Expand to approximate "total box":
    # invoices often have label left and amount right; so expand right & downward
    box = fitz.Rect(best)
    box.x0 -= pw * 0.10
    box.x1 += pw * 0.22
    box.y0 -= ph * 0.03
    box.y1 += ph * 0.08

    # clamp to page
    box.x0 = clamp(box.x0, 0, pw)
    box.x1 = clamp(box.x1, 0, pw)
    box.y0 = clamp(box.y0, 0, ph)
    box.y1 = clamp(box.y1, 0, ph)

    # avoid degenerate
    if box.width < 60 or box.height < 20:
        return None
    return box


# =========================
# Stamp rendering
# =========================
def draw_round_rect(shape: fitz.Shape, r: fitz.Rect, rad: float):
    rad = max(0.0, min(rad, r.width / 2.0, r.height / 2.0))
    x0, y0, x1, y1 = r.x0, r.y0, r.x1, r.y1

    shape.draw_line((x0 + rad, y0), (x1 - rad, y0))
    shape.draw_line((x1, y0 + rad), (x1, y1 - rad))
    shape.draw_line((x1 - rad, y1), (x0 + rad, y1))
    shape.draw_line((x0, y1 - rad), (x0, y0 + rad))

    shape.draw_curve((x1 - rad, y0), (x1, y0), (x1, y0 + rad))
    shape.draw_curve((x1, y1 - rad), (x1, y1), (x1 - rad, y1))
    shape.draw_curve((x0 + rad, y1), (x0, y1), (x0, y1 - rad))
    shape.draw_curve((x0, y0 + rad), (x0, y0), (x0 + rad, y0))


def fit_font_size(text: str, base_size: float, max_width: float, fontname: str) -> float:
    size = max(8.0, base_size)
    for _ in range(30):
        w = fitz.get_text_length(text, fontname=fontname, fontsize=size)
        if w <= max_width:
            return size
        size *= 0.92
    return max(8.0, size)


def make_stamp_png(opt: Opt, fontname: str, fontsize: float) -> Tuple[bytes, float, float]:
    """
    Return: (png_bytes, stamp_w_pt, stamp_h_pt)
    Uses pixmap size to place accurately after rotation.
    """
    text = opt.text
    red = (1, 0, 0)

    text_w = fitz.get_text_length(text, fontname=fontname, fontsize=fontsize)
    text_h = fontsize * 1.20

    stroke_w = max(6, fontsize * 0.1)

    pad_x = max(10.0, fontsize * 0.85) + stroke_w
    pad_y = max(10.0, fontsize * 0.15) + stroke_w

    w = text_w + pad_x * 5
    h = text_h + pad_y * 1.5

    stamp = fitz.open()
    sp = stamp.new_page(width=w, height=h)

    rect = sp.rect + (stroke_w / 2, stroke_w / 2, -stroke_w / 2, -stroke_w / 2)
    shape = sp.new_shape()

    radius = max(6.0, fontsize * 0.35)
    radius = min(radius, rect.width / 2.0, rect.height / 2.0)

    try:
        shape.draw_rect(rect, radius=radius)
    except Exception:
        draw_round_rect(shape, rect, radius)

    shape.finish(
    color=red,
    fill=None,
    width=stroke_w,
    closePath=True,
    lineCap=1,      # round cap
    lineJoin=1,     # round join  ✅ ini inti masalahnya
    stroke_opacity=opt.opacity,
)

    shape.insert_textbox(
        rect,
        text,
        fontname=fontname,
        fontsize=fontsize,
        color=red,
        fill_opacity=opt.opacity,
        align=fitz.TEXT_ALIGN_CENTER,
        render_mode=0,
    )

    shape.commit(overlay=True)

    zoom = 8.0
    m = fitz.Matrix(zoom, zoom).prerotate(opt.rotate)
    pix = sp.get_pixmap(matrix=m, alpha=True)

    png_bytes = pix.tobytes("png")
    stamp_w_pt = pix.width / zoom
    stamp_h_pt = pix.height / zoom

    stamp.close()
    return png_bytes, stamp_w_pt, stamp_h_pt


# =========================
# Placement logic
# =========================
def add_watermark(page: fitz.Page, opt: Opt):
    pw, ph = page.rect.width, page.rect.height

    content = pick_main_content_rect(page)
    total_box = find_total_like_rect(page)

    # If content missing, fallback to page rect
    content_rect = content if content is not None else page.rect

    # ✅ target watermark width = 10% content width
    wm_target_w = max(90.0, content_rect.width * opt.wmWidthPctOfContent)

    # find anchor point: center of total_box, else bottom-right-ish of content
    if total_box is not None:
        ax = total_box.x0 + total_box.width * 0.55
        ay = total_box.y0 + total_box.height * 0.55
    else:
        ax = content_rect.x0 + content_rect.width * 0.60
        ay = content_rect.y0 + content_rect.height * 0.62

    # apply micro shift relative to content (requested)
    ax += content_rect.width * opt.shiftXPctOfContent
    ay += content_rect.height * opt.shiftYPctOfContent

    fontname = "hebo"  # Helvetica-Bold

    # base font size is derived from watermark width target
    # "LUNAS" text width ~ 4-6 chars => fontsize roughly wm_target_w / 3..4
    base_size = max(10.0, wm_target_w / 3.2)

    # fit font size so that text width <= 70% of wm_target_w (padding included later)
    max_text_w = wm_target_w * 0.50
    fontsize = fit_font_size(opt.text, base_size, max_text_w, fontname)

    png, stamp_w, stamp_h = make_stamp_png(opt, fontname, fontsize)

    # after rotation, stamp_w/h are from pixmap. scale to meet wm_target_w
    if stamp_w > 0:
        scale = wm_target_w / stamp_w
    else:
        scale = 1.0

    stamp_w *= scale
    stamp_h *= scale
    safe_pad = max(stamp_w, stamp_h) * 0.15
    target = fitz.Rect(
        ax - stamp_w / 2,
        ay - stamp_h / 2,
        ax + stamp_w / 2,
        ay + stamp_h / 2,
    )

    # clamp into content rect so it doesn't fly out
    margin = 6.0
    minx = content_rect.x0 + margin
    maxx = content_rect.x1 - margin
    miny = content_rect.y0 + margin
    maxy = content_rect.y1 - margin

    dx = 0.0
    dy = 0.0
    if target.x0 < minx: dx = minx - target.x0
    if target.x1 > maxx: dx = maxx - target.x1
    if target.y0 < miny: dy = miny - target.y0
    if target.y1 > maxy: dy = maxy - target.y1

    target = target + (dx, dy, dx, dy)

    page.insert_image(
        target,
        stream=png,
        overlay=True,
        keep_proportion=True,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--options", required=False, default="")
    args = ap.parse_args()

    opt = parse_options(args.options)

    doc = fitz.open(args.input)
    for i in range(len(doc)):
        add_watermark(doc[i], opt)

    doc.save(args.output)
    doc.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
