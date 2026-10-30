"""Convert a portrait photo into ASCII art for the profile card.

Writes two versions, because the card has two themes:
  face.light.txt  dark pixels get dense characters (dark text on a light card)
  face.dark.txt   light pixels get dense characters (light text on a dark card)

Usage:
  python3 scripts/make_ascii.py <photo> [options]

Options:
  --cols N          characters per line (default 84)
  --rows N          lines (default 52)
  --crop X,Y,W,H    crop the photo to this box (pixels) before converting
  --remove-bg MODEL remove the background with a MediaPipe selfie segmentation
                    model (.tflite); needs `pip install mediapipe`
  --contrast F      contrast boost, 0.7-1.6 (default 1.4)
  --gamma F         < 1 brightens mid-tones, > 1 darkens them (default 1.0)
  --sharpen F       unsharp-mask strength (default 1.2)
  --ramp NAME       character set: simple, portrait, detailed (default portrait)
  --preview PNG     also save the cut-out photo, to check the crop and mask

A transparent PNG works too: transparent pixels become empty space.
"""
import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent

RAMPS = {
    "simple": " .-+*#@",
    "portrait": " .,:;irsXA253hMHGS#9B&@",
    "detailed": " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
}

CHAR_ASPECT = 1.875   # line height / character width, matching build.py's face font
SUPERSAMPLE = 3
CUTOUT = 0.08         # cells less covered than this are background


def calibrate(chars):
    """Order characters by how much ink they put on screen in a monospace font."""
    try:
        path = subprocess.run(["fc-match", "-f", "%{file}", "monospace"],
                              capture_output=True, text=True).stdout.strip()
        font = ImageFont.truetype(path, 48)
    except (OSError, ValueError):
        return list(chars)
    ink = []
    for order, ch in enumerate(dict.fromkeys(chars)):
        img = Image.new("L", (64, 64))
        ImageDraw.Draw(img).text((32, 32), ch, font=font, fill=255, anchor="mm")
        ink.append((np.asarray(img).sum(), order, ch))
    return [ch for _, _, ch in sorted(ink)]


def remove_background(rgb, model):
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision

    options = vision.ImageSegmenterOptions(base_options=BaseOptions(model_asset_path=model),
                                           output_confidence_masks=True)
    with vision.ImageSegmenter.create_from_options(options) as segmenter:
        result = segmenter.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(rgb)))
        background = result.confidence_masks[0].numpy_view().squeeze().copy()
    alpha = Image.fromarray(((1 - background) * 255).astype(np.uint8)).resize(rgb.size)
    alpha = np.asarray(alpha.filter(ImageFilter.GaussianBlur(1)), dtype=np.float32) / 255
    return np.clip((alpha - 0.08) / 0.72, 0, 1)


def fit_aspect(img, aspect):
    """Centre-crop to width / height == aspect."""
    w, h = img.size
    if w / h > aspect:
        nw = round(h * aspect)
        return img.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    nh = round(w / aspect)
    return img.crop((0, 0, w, nh))  # keep the top: that's where the face is


def box_blur(a):
    p = np.pad(a, 1, mode="edge")
    return sum(p[y:y + a.shape[0], x:x + a.shape[1]] for y in range(3) for x in range(3)) / 9


def convert(args):
    img = Image.open(args.photo)
    alpha = img.getchannel("A") if img.mode in ("RGBA", "LA") else None
    img = img.convert("RGB")
    if args.crop:
        box = tuple(int(v) for v in args.crop.split(","))
        box = (box[0], box[1], box[0] + box[2], box[1] + box[3])
        img = img.crop(box)
        alpha = alpha.crop(box) if alpha else None

    if args.remove_bg:
        mask = remove_background(img, args.remove_bg)
    elif alpha:
        mask = np.asarray(alpha, dtype=np.float32) / 255
    else:
        mask = np.ones((img.height, img.width), dtype=np.float32)
    rgba = img.copy()
    rgba.putalpha(Image.fromarray((mask * 255).astype(np.uint8)))
    rgba = fit_aspect(rgba, args.cols / (args.rows * CHAR_ASPECT))
    if args.preview:
        preview = Image.new("RGB", rgba.size, "white")
        preview.paste(rgba, mask=rgba.getchannel("A"))
        preview.save(args.preview)

    # Average SUPERSAMPLE x SUPERSAMPLE samples per character cell.
    big = np.asarray(rgba.resize((args.cols * SUPERSAMPLE, args.rows * SUPERSAMPLE), Image.LANCZOS),
                     dtype=np.float32) / 255
    a = big[..., 3]
    luma = (0.299 * big[..., 0] + 0.587 * big[..., 1] + 0.114 * big[..., 2]) * a
    cells = lambda m: m.reshape(args.rows, SUPERSAMPLE, args.cols, SUPERSAMPLE).mean(axis=(1, 3))
    cover = cells(a)
    luma = cells(luma) / np.maximum(cover, 1e-6)
    person = cover >= CUTOUT

    # Stretch the person's tones to 0..1, then contrast, gamma and sharpen.
    lo, hi = np.percentile(luma[person], [1, 99])
    v = np.clip((luma - lo) / max(hi - lo, 1e-6), 0, 1)
    v = np.clip((v - 0.5) * args.contrast + 0.5, 0, 1) ** args.gamma
    v = np.clip(v + (v - box_blur(v)) * args.sharpen, 0, 1)

    ramp = calibrate(RAMPS[args.ramp])

    def render(density):
        # Index 1 at least, so dark-on-dark parts (hair in dark mode) keep their outline.
        idx = np.clip((density * (len(ramp) - 1)).round().astype(int), 1, len(ramp) - 1)
        return "\n".join("".join(ramp[i] if person[y, x] else " " for x, i in enumerate(row)).rstrip()
                         for y, row in enumerate(idx)) + "\n"

    return render(1 - v), render(v)


def main():
    if "--help" in sys.argv[1:] or len(sys.argv) < 2:
        print(__doc__.strip())
        return
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("photo")
    p.add_argument("--cols", type=int, default=84)
    p.add_argument("--rows", type=int, default=52)
    p.add_argument("--crop")
    p.add_argument("--remove-bg")
    p.add_argument("--contrast", type=float, default=1.4)
    p.add_argument("--gamma", type=float, default=1.0)
    p.add_argument("--sharpen", type=float, default=1.2)
    p.add_argument("--ramp", choices=RAMPS, default="portrait")
    p.add_argument("--preview")
    args = p.parse_args()
    args.contrast = min(1.6, max(0.7, args.contrast))

    light, dark = convert(args)
    (ROOT / "face.light.txt").write_text(light)
    (ROOT / "face.dark.txt").write_text(dark)
    print(light)


if __name__ == "__main__":
    main()
