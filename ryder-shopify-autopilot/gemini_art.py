"""Topic artwork with Google Gemini, using the house prompt in visual-system.md.

    python3 gemini_art.py <slug> "<concrete subject>"

Writes assets/brand/art/<slug>.png (1280x720, pure white ground) and prints
the path. Generates with the best image model the key can use, checks the
result with a Gemini text model for text, faces and logos, and retries once
with a fresh image if the check fails. Exits non-zero when it can't produce
clean art, so the caller can fall back to engrave_art.py.

Needs GEMINI_API_KEY in CLAUDE OUTPUTS/Ryder One/shopify.env. Never prints it.
"""
import base64
import io
import json
import os
import sys
import urllib.error
import urllib.request

from PIL import Image

from common import load_env
from generate_visuals import BRAND_DIR

API = "https://generativelanguage.googleapis.com/v1beta"
IMAGE_MODELS = ["gemini-3-pro-image", "gemini-3.1-flash-image",
                "gemini-2.5-flash-image"]
CHECK_MODELS = ["gemini-flash-latest", "gemini-3.5-flash", "gemini-3-flash-preview"]
W, H = 1280, 720

HOUSE_PROMPT = (
    "A black and white realistic editorial illustration made with black line "
    "pen, showing {subject}, engraving/gravure hatching style, pure white "
    "background, single centered subject, absolutely no text, no letters, no "
    "words, no numbers, no watermark, no faces, no logo. Fine cross-hatched pen "
    "shading like a banknote engraving. 16:9 image. Compose the subject taller "
    "than it is wide, filling the middle of the frame from near the top to "
    "near the bottom, with empty white space on the left and right. Screens, "
    "labels and paper show only plain lines, never readable characters.")

CHECK_PROMPT = (
    "Look at this illustration. Answer with one JSON object only, no prose: "
    '{"text": true|false, "face": true|false, "logo": true|false, '
    '"white_background": true|false, "subject_ok": true|false}. '
    '"text" is true if any letters, words, digits or readable characters '
    'appear anywhere. "face" is true for any human or animal face. "logo" is '
    'true for any brand mark. "subject_ok" is true if it clearly shows: {subject}.')


def _post(model, body):
    req = urllib.request.Request(
        f"{API}/models/{model}:generateContent",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "x-goog-api-key": os.environ["GEMINI_API_KEY"]})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.load(resp)


def _first_working(models, body):
    errors = []
    for model in models:
        try:
            return model, _post(model, body)
        except urllib.error.HTTPError as e:
            errors.append(f"{model}: HTTP {e.code} "
                          f"{e.read()[:160].decode(errors='replace')}")
        except (urllib.error.URLError, TimeoutError) as e:
            errors.append(f"{model}: {e}")
    raise RuntimeError("; ".join(errors))


def generate(subject):
    body = {"contents": [{"parts": [{"text": HOUSE_PROMPT.format(subject=subject)}]}],
            "generationConfig": {"responseModalities": ["IMAGE"],
                                 "imageConfig": {"aspectRatio": "16:9"}}}
    model, data = _first_working(IMAGE_MODELS, body)
    for cand in data.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            blob = part.get("inlineData") or part.get("inline_data")
            if blob and blob.get("data"):
                return model, Image.open(io.BytesIO(base64.b64decode(blob["data"])))
    raise RuntimeError(f"{model} returned no image "
                       f"(finish: {[c.get('finishReason') for c in data.get('candidates', [])]})")


def check(img, subject):
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=85)
    body = {"contents": [{"parts": [
        {"inlineData": {"mimeType": "image/jpeg",
                        "data": base64.b64encode(buf.getvalue()).decode()}},
        {"text": CHECK_PROMPT.replace("{subject}", subject)}]}],
        "generationConfig": {"responseMimeType": "application/json"}}
    _, data = _first_working(CHECK_MODELS, body)
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    verdict = json.loads(text[text.find("{"):text.rfind("}") + 1])
    problems = [k for k in ("text", "face", "logo") if verdict.get(k)]
    problems += [k for k in ("white_background", "subject_ok") if not verdict.get(k)]
    return problems


def normalize(img):
    """Flatten onto pure white and fit 1280x720 (see ryder-hero-art rule:
    off-white grounds show as a pasted box on the hero)."""
    img = img.convert("RGBA")
    ground = Image.new("RGBA", img.size, (255, 255, 255, 255))
    gray = Image.alpha_composite(ground, img).convert("L")
    gray = gray.point(lambda p: 255 if p > 238 else p)
    scale = min(W / gray.width, H / gray.height)
    gray = gray.resize((int(gray.width * scale), int(gray.height * scale)), Image.LANCZOS)
    out = Image.new("L", (W, H), 255)
    out.paste(gray, ((W - gray.width) // 2, (H - gray.height) // 2))
    return out.convert("RGB")


def make_art(slug, subject, tries=2):
    out_path = os.path.join(BRAND_DIR, "art", f"{slug}.png")
    last = None
    for attempt in range(1, tries + 1):
        model, img = generate(subject)
        img = normalize(img)
        problems = check(img, subject)
        if not problems:
            img.save(out_path, optimize=True)
            bbox = img.convert("L").point(lambda p: 255 if p < 235 else 0).getbbox()
            ratio = (bbox[2] - bbox[0]) / (bbox[3] - bbox[1]) if bbox else 0
            return {"slug": slug, "ok": True, "path": out_path, "model": model,
                    "attempts": attempt, "width_to_height": round(ratio, 2)}
        last = problems
    return {"slug": slug, "ok": False, "error": f"rejected after {tries} tries: {last}"}


def main(argv):
    if len(argv) != 3:
        raise SystemExit(__doc__)
    load_env(required_keys=("GEMINI_API_KEY",))
    try:
        result = make_art(argv[1], argv[2])
    except RuntimeError as e:
        result = {"slug": argv[1], "ok": False, "error": str(e)[:400]}
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
