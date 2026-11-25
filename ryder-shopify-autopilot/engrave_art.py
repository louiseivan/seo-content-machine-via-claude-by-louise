"""Topic artwork without an image model: banknote-style engravings from SVG.

visual-system.md asks for a black line-pen engraving of one concrete object
on pure white, with fine cross-hatched shading and no text, faces or logos.
This renders that look locally, so the cloud server needs no image API.

Input is a small SVG on a 1280x720 canvas that draws the subject as simple
shapes. Mark each filled shape's shading with a `data-tone` attribute:

    0  paper (white, outline only)
    1  light      - fine single hatching
    2  mid        - hatching + cross-hatching
    3  dark       - dense cross-hatching
    4  deepest    - dense triple hatching (cast shadows, holes)

Optional `data-angle` (degrees) turns the hatching to follow a surface.
Shapes are hatched inside their own outline, then stroked with a pen line;
plain `<line>`/`<polyline>`/unfilled paths stay as ink lines. Later shapes
paint over earlier ones, as on paper.

Usage:
    python3 engrave_art.py subject.svg assets/brand/art/<slug>.png
"""
import io
import math
import re
import sys
import xml.etree.ElementTree as ET

import cairosvg
from PIL import Image, ImageFilter

W, H = 1280, 720
SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

# tone -> list of (angle offset, spacing px, stroke width)
TONES = {
    1: [(0, 9.0, 1.1)],
    2: [(0, 7.0, 1.2), (90, 9.0, 1.0)],
    3: [(0, 5.0, 1.4), (90, 5.5, 1.3)],
    4: [(0, 3.6, 1.6), (90, 3.8, 1.5), (45, 4.2, 1.3)],
}
FILLED = {"path", "rect", "circle", "ellipse", "polygon"}
FORBIDDEN = ("<text", "<image", "<use", "href=", "<foreignObject", "<script")


def _q(tag):
    return f"{{{SVG_NS}}}{tag}"


def _hatch_pattern(pid, tone, angle):
    pat = ET.Element(_q("pattern"), id=pid, patternUnits="userSpaceOnUse",
                     width="40", height="40",
                     patternTransform=f"rotate({angle})")
    for offset, spacing, width in TONES[tone]:
        g = ET.SubElement(pat, _q("g"), transform=f"rotate({offset} 20 20)")
        # oversize so rotated lines still tile the 40px cell
        y = -40.0
        while y < 80:
            ET.SubElement(g, _q("line"), x1="-40", y1=f"{y:.2f}", x2="80",
                          y2=f"{y:.2f}", stroke="#000",
                          **{"stroke-width": f"{width}"})
            y += spacing
    # pattern width must be a multiple of every spacing to tile cleanly
    lcm = 1.0
    for _, spacing, _ in TONES[tone]:
        lcm = max(lcm, spacing)
    size = max(40, math.ceil(lcm * 8))
    pat.set("width", str(size))
    pat.set("height", str(size))
    return pat


def build_svg(src):
    """Return an engraving-ready SVG string from the subject SVG."""
    low = src.lower()
    for bad in FORBIDDEN:
        if bad.lower() in low:
            raise ValueError(f"subject SVG may not contain {bad!r} "
                             "(no text, images or external references)")
    root = ET.fromstring(src)
    root.set("width", str(W))
    root.set("height", str(H))
    root.set("viewBox", f"0 0 {W} {H}")
    defs = root.find(_q("defs"))
    if defs is None:
        defs = ET.Element(_q("defs"))
        root.insert(0, defs)
    made = {}
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag not in FILLED:
            continue
        tone = int(el.get("data-tone", "0"))
        if not 0 <= tone <= 4:
            raise ValueError("data-tone must be 0-4")
        angle = float(el.get("data-angle", "35"))
        if tone == 0:
            fill = "#fff"
        else:
            pid = f"h{tone}_{int(angle) % 180}"
            if pid not in made:
                defs.append(_hatch_pattern(pid, tone, angle))
                made[pid] = True
            fill = f"url(#{pid})"
        if el.get("fill") != "none":
            el.set("fill", fill)
        el.set("stroke", "#000")
        el.set("stroke-width", el.get("stroke-width", "3.2"))
        el.set("stroke-linejoin", "round")
        el.set("stroke-linecap", "round")
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag in ("line", "polyline"):
            el.set("fill", "none")
            el.set("stroke", "#000")
            el.set("stroke-width", el.get("stroke-width", "2.4"))
            el.set("stroke-linecap", "round")
    # white paper behind everything
    root.insert(1, ET.Element(_q("rect"), x="0", y="0", width=str(W),
                              height=str(H), fill="#fff"))
    return ET.tostring(root, encoding="unicode")


def render(src, out_path):
    svg = build_svg(src)
    png = cairosvg.svg2png(bytestring=svg.encode(), output_width=W * 2,
                           output_height=H * 2, background_color="white")
    img = Image.open(io.BytesIO(png)).convert("L")
    # slight softening + downsample gives the printed-ink edge of a gravure
    img = img.filter(ImageFilter.GaussianBlur(0.5)).resize((W, H), Image.LANCZOS)
    img = img.point(lambda p: 255 if p > 232 else max(0, int(p * 0.82)))
    img.convert("RGB").save(out_path, optimize=True)
    bbox = img.point(lambda p: 255 if p < 235 else 0).getbbox()
    if not bbox:
        raise ValueError("rendered art is blank")
    ratio = (bbox[2] - bbox[0]) / (bbox[3] - bbox[1])
    if ratio > 0.85:
        print(f"warning: drawing is {ratio:.2f}x as wide as tall; above ~0.85 "
              "it runs under the hero headline. Redraw taller and narrower.",
              file=sys.stderr)
    return out_path


def main(argv):
    if len(argv) != 3:
        raise SystemExit(__doc__)
    with open(argv[1]) as f:
        src = f.read()
    print(render(src, argv[2]))


if __name__ == "__main__":
    main(sys.argv)
