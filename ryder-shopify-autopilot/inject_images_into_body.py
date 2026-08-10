"""Inject body images into article HTML.

Inserts <figure> blocks after H2 closings, round-robin across the images
provided. Skipped entirely when PUSH_HERO_ONLY=1 (the default), so this
only runs when a batch deliberately ships body visuals.

Usage:
    python3 inject_images_into_body.py body.html img1.png img2.png > out.html
    from inject_images_into_body import inject_images
"""

import re
import sys


def inject_images(html, image_urls, alt_texts=None):
    """Place one image after every other H2, in document order."""
    if not image_urls:
        return html
    alt_texts = alt_texts or [""] * len(image_urls)
    pieces = re.split(r"(</h2>)", html, flags=re.I)
    out, img_i, h2_i = [], 0, 0
    for piece in pieces:
        out.append(piece)
        if piece.lower() == "</h2>":
            h2_i += 1
            if h2_i % 2 == 0 and img_i < len(image_urls):
                alt = alt_texts[img_i] if img_i < len(alt_texts) else ""
                out.append(
                    f'\n<figure><img src="{image_urls[img_i]}" alt="{alt}" '
                    f'loading="lazy" style="width:100%;height:auto;"></figure>\n')
                img_i += 1
    return "".join(out)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit("usage: python3 inject_images_into_body.py body.html img... ")
    with open(sys.argv[1]) as f:
        print(inject_images(f.read(), sys.argv[2:]))
