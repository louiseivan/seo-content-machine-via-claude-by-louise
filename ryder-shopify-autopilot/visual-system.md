# Ryder blog hero visual system

Source of truth: the Figma Socials file, TEMPLATES AND STYLES canvas
(node 10975-4349, figma.com/design/7yYsWdOnV4Ttgz6oZ55OBA), as applied
in the published blog banners (see ~/Downloads/"↪ 📘 Blog banners" for
shipped examples, e.g. the STX Staking banner). Adopted 2026-08-10,
replacing the interim neutral dark design. `generate_visuals.py`
implements this spec.

## Canvas

- 1200 x 630 px PNG (Open Graph / Shopify featured image)
- Field: one of three colorways (below), edge to edge
- Subtle dark grain over orange/blue fields (skipped on black)
- 56 px margins (scaled from the 40 px @1280 Figma templates)

## Colorways

Four, matching the Figma template rows (thumbnail light / orange /
talk3 blue / BrandBG black). Assigned per article: `hero_colorway` in
meta.json wins; otherwise a deterministic slug-hash rotation picks one,
so reruns are stable but a batch varies. Balance a batch by hand via
the meta files.

| Colorway | Field | Text | Engraving ink |
|---|---|---|---|
| orange | `#FF4600` | `#FAFAFA` | near-black `(26,10,0)` |
| blue | `#0F3BFF` | `#FAFAFA` | dark navy `(2,8,40)` |
| black | `#0A0A0A` | `#FAFAFA` | orange `#FF4600` |
| light | `#FAFAFA` | `#0F3BFF` | natural black `(20,20,20)` |

Whenever artwork is present, a field-colored gradient scrim (opaque to
38% of the width, fading out by 80%) sits between art and type — the
same white-to-transparent gradient trick the Figma templates use — so
titles and subtitles never fight the engraving.

## Brand tokens (from Figma global vars)

| Token | Value | Use |
|---|---|---|
| Orange | `#FF4600` | background field |
| Off-white | `#FAFAFA` | all text and logo on orange |
| Blue | `#0F3BFF` | accent; the icon's native color, recolored to off-white on orange heroes |

## Typography

| Role | Font | Setting |
|---|---|---|
| Title | Anek Latin (variable) | weight 800, width 125 ("Expanded ExtraBold"), UPPERCASE, line height 0.98, autoshrink 96→40 px until every line fits (max 4 lines preferred, never truncate) |
| Subtitle | Geist (variable) | weight 400, 27 px, sentence case, max 2 lines |
| Wordmark | Anek Latin | weight 800, width 110, "Ryder" |

Fonts live in `assets/fonts/` (AnekLatin-Variable.ttf, Geist-Variable.ttf,
Poppins-Regular.ttf; all OFL-licensed from Google Fonts).

## Layout

- Title block: top-left at (56, 56), constrained to left 64% of canvas
- Subtitle: 18 px below the title block
- Logo: bottom-left, icon (42 px, `assets/brand/ryder-icon.svg` recolored
  `#0F3BFF` → `#FAFAFA`) + wordmark, baseline-aligned
- Artwork: engraved-style illustration on the right, scaled to ~135% of
  canvas height, bleeding off the right edge, behind the grain

## Artwork (topic-specific, per article)

Each article gets its own engraving at `assets/brand/art/<slug>.png`;
the generic Recovery Tag engraving (`assets/brand/gravure-tag.png`) is
only the fallback when no slug art exists. Two accepted formats:

- Black-line-pen illustration on white (the normal case): the generator
  crops to content, scales to the right side, and converts line darkness
  into the colorway's ink so the white paper disappears into the field.
- Transparent-background cutout: pasted as-is at 135% canvas height.

House generation prompt (from the Figma canvas, works in any image
model, incl. vidiq_generate_thumbnail): "A black and white realistic
editorial illustration made with black line pen, showing <subject>,
engraving/gravure hatching style, pure white background, single centered
subject, absolutely no text, no letters, no words, no watermark, no
faces, no logo. Fine cross-hatched pen shading like a banknote
engraving. 16:9." Pick a subject that is a concrete object standing for
the article's topic (dice for randomness, vault door for cold storage,
balance scale for comparisons), not an abstract concept.

Reference renders from Figma are in `assets/brand/`
(template-thumbnail-1.png, template-brandbg.png).

## Text rules

- Banner title = the article's `seo_title` with any trailing "| Ryder"
  stripped (short and punchy beats the full H1)
- Subtitle = `hero_subtitle` from the article's meta.json: public-facing
  copy, not the internal content_angle
- Alt text = `hero_alt`, mentioning "Ryder self-custody hardware wallet"
