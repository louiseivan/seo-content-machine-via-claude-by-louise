"""Hero image generator for Ryder blog posts.

Implements the brand template from the Figma Socials file (TEMPLATES AND
STYLES canvas, node 10975:4349) as applied in the published blog banners:
Ryder orange field with grain, engraved illustration bleeding off the
right edge, white Anek Latin Expanded ExtraBold uppercase title, Geist
subtitle, white Ryder logo. See visual-system.md for the spec.

Usage:
    python3 generate_visuals.py "Article Title" slug [out.png] ["Subtitle"]
    from generate_visuals import generate_hero
"""

import glob
import io
import os
import sys

from PIL import Image, ImageDraw, ImageFont

from common import AUTOPILOT_DIR, HEROES_DIR

W, H = 1200, 630
MARGIN = 56

ORANGE = (255, 70, 0)      # #FF4600 brand field
OFFWHITE = (250, 250, 250)  # #FAFAFA text
BLUE = (15, 59, 255)       # #0F3BFF brand field
BLACK = (10, 10, 10)       # black brand field

# Colorways from the Figma templates (thumbnail/talk3/BrandBG rows):
# field color, text color, engraving ink. On dark fields the ink flips to
# a light/accent color so line art stays visible. "light" mirrors the
# Thumbnail template row: paper field, blue type, natural black ink.
COLORWAYS = {
    "orange": {"field": ORANGE, "text": OFFWHITE, "ink": (26, 10, 0)},
    "blue":   {"field": BLUE,   "text": OFFWHITE, "ink": (2, 8, 40)},
    "black":  {"field": BLACK,  "text": OFFWHITE, "ink": ORANGE},
    "light":  {"field": OFFWHITE, "text": BLUE,   "ink": (20, 20, 20)},
}


def _colorway_for(slug):
    """Deterministic rotation: same article always renders the same way,
    but a batch of posts varies across the three colorways."""
    return list(COLORWAYS)[sum(slug.encode()) % len(COLORWAYS)]

FONTS_DIR = os.path.join(AUTOPILOT_DIR, "assets", "fonts")
BRAND_DIR = os.path.join(AUTOPILOT_DIR, "assets", "brand")
ANEK = os.path.join(FONTS_DIR, "AnekLatin-Variable.ttf")
GEIST = os.path.join(FONTS_DIR, "Geist-Variable.ttf")


def _anek(size, weight=800, width=125):
    f = ImageFont.truetype(ANEK, size)
    f.set_variation_by_axes([weight, width])  # axes order: wght, wdth
    return f


def _geist(size, weight=400):
    f = ImageFont.truetype(GEIST, size)
    f.set_variation_by_axes([weight])
    return f


def _wrap(draw, text, font, max_width):
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _grain(img, alpha=14):
    noise = Image.effect_noise((W, H), 48).convert("L")
    img.paste(Image.new("RGB", (W, H), (20, 5, 0)), (0, 0),
              noise.point(lambda p: alpha if p < 100 else 0))
    return img


def _brand_icon(height, color):
    """Ryder icon SVG recolored to the colorway's text color, rasterized."""
    path = os.path.join(BRAND_DIR, "ryder-icon.svg")
    if not os.path.exists(path):
        return None
    try:
        import cairosvg
        hex_color = "#%02X%02X%02X" % color
        with open(path) as f:
            svg = f.read().replace("#0F3BFF", hex_color)
        png = cairosvg.svg2png(bytestring=svg.encode(), output_height=height)
        return Image.open(io.BytesIO(png)).convert("RGBA")
    except Exception:
        return None


def _artwork(slug=None):
    """Engraved illustration for the right side. Preference order:
    slug-specific art in assets/brand/art/<slug>.png, then the generic
    gravure texture pulled from the Figma templates."""
    candidates = []
    if slug:
        candidates.append(os.path.join(BRAND_DIR, "art", f"{slug}.png"))
    candidates.append(os.path.join(BRAND_DIR, "gravure-tag.png"))
    for p in candidates:
        if os.path.exists(p):
            return Image.open(p).convert("RGBA")
    return None


def _place_art(img, art, ink_color=(26, 10, 0)):
    """Composite engraving art on the right, bleeding off the edge.

    Cutout art (real alpha channel) is pasted directly. Black-line-pen
    illustrations on white become an ink layer: line darkness becomes the
    alpha of `ink_color`, so white paper vanishes into the field color,
    matching the published banners."""
    alpha_min = art.getchannel("A").getextrema()[0]
    if alpha_min < 200:  # genuine cutout
        target_h = int(H * 1.35)
        art = art.resize((int(art.width * target_h / art.height), target_h))
        img.paste(art, (W - int(art.width * 0.72), (H - target_h) // 2), art)
        return

    gray = art.convert("L")
    bbox = gray.point(lambda p: 255 if p < 235 else 0).getbbox()
    if bbox:
        gray = gray.crop(bbox)
    target_h = int(H * 0.95)
    w = int(gray.width * target_h / gray.height)
    if w > int(W * 0.58):
        w = int(W * 0.58)
        target_h = int(gray.height * w / gray.width)
    gray = gray.resize((w, target_h))
    ink_alpha = gray.point(lambda p: max(0, 255 - p))
    ink = Image.new("RGB", gray.size, ink_color)
    img.paste(ink, (W - int(w * 0.76), (H - target_h) // 2), ink_alpha)


def _text_scrim(img, field):
    """Field-colored gradient over the left side (opaque until ~30% of the
    width, fading out by ~72%), so art never fights the type. Mirrors the
    white-to-transparent gradient the Figma templates use."""
    x0, x1 = int(W * 0.38), int(W * 0.80)
    ramp = Image.new("L", (W, 1), 0)
    for x in range(W):
        if x <= x0:
            v = 255
        elif x >= x1:
            v = 0
        else:
            v = int(255 * (x1 - x) / (x1 - x0))
        ramp.putpixel((x, 0), v)
    img.paste(Image.new("RGB", (W, H), field), (0, 0), ramp.resize((W, H)))


def generate_hero(title, slug, out_path=None, subtitle=None, colorway=None):
    os.makedirs(HEROES_DIR, exist_ok=True)
    out_path = out_path or os.path.join(HEROES_DIR, f"{slug}.png")

    cw = COLORWAYS[colorway or _colorway_for(slug)]
    img = Image.new("RGB", (W, H), cw["field"])

    # Engraved art, right side, bleeding off canvas
    art = _artwork(slug)
    if art:
        _place_art(img, art, cw["ink"])
        _text_scrim(img, cw["field"])

    if cw["field"] != BLACK:  # grain reads as texture on color fields only
        _grain(img)
    draw = ImageDraw.Draw(img)

    # Title: shrink until every line fits in the left ~64% of the canvas.
    # Nothing is ever truncated; the smallest size renders all lines.
    max_w = int(W * 0.64)
    for size in (96, 84, 72, 62, 54, 46, 40):
        font = _anek(size)
        lines = _wrap(draw, title.upper(), font, max_w)
        if len(lines) <= 4:
            break
    y = MARGIN
    for line in lines:
        draw.text((MARGIN, y), line, font=font, fill=cw["text"])
        y += int(size * 0.98)

    # Subtitle in Geist below the title block
    if subtitle:
        y += 18
        sub_font = _geist(27)
        for line in _wrap(draw, subtitle, sub_font, max_w)[:2]:
            draw.text((MARGIN, y), line, font=sub_font, fill=cw["text"])
            y += 36

    # Logo bottom-left: icon + wordmark
    icon = _brand_icon(42, cw["text"])
    x = MARGIN
    logo_y = H - MARGIN - 42
    if icon:
        img.paste(icon, (x, logo_y), icon)
        x += icon.width + 12
    draw.text((x, logo_y - 6), "Ryder", font=_anek(44, weight=800, width=110),
              fill=cw["text"])

    img.save(out_path, "PNG")
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit('usage: python3 generate_visuals.py "Title" slug [out.png] ["Subtitle"]')
    print(generate_hero(sys.argv[1], sys.argv[2],
                        sys.argv[3] if len(sys.argv) > 3 else None,
                        sys.argv[4] if len(sys.argv) > 4 else None))
