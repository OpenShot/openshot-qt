#!/usr/bin/env python3
import os
from openshot import QtImageReader, ColorMap
from PIL import Image, ImageDraw, ImageFont, ImageOps
from classes.info import PATH

# Path to your source JPG
SOURCE = "../images/effect-background.jpg"
# Directory of LUT sub-folders
BASE_DIR = "."
# Frame index to read/apply (1 = first frame)
FRAME_NUMBER = 1
# Output directory for generated JPEGs
OUTPUT_DIR = os.path.join(PATH, "..", "doc", "images", "colors")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Parameters for border and text
BORDER_SIZE = 5
FONT_SIZE   = 85
TEXT_OFFSET = 30

# Load a font for overlay text
try:
    FONT = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        FONT_SIZE
    )
except Exception:
    FONT = ImageFont.load_default()

gallery = {}

for category in sorted(os.listdir(BASE_DIR)):
    folder = os.path.join(BASE_DIR, category)
    if not os.path.isdir(folder):
        continue

    gallery[category] = []
    prefix = category.replace(os.sep, "_")

    for fname in sorted(os.listdir(folder)):
        if not fname.lower().endswith(".cube"):
            continue

        cube_path = os.path.join(folder, fname)
        name_base = os.path.splitext(fname)[0]
        out_name  = f"{prefix}_{name_base}.jpg"
        out_path  = os.path.join(OUTPUT_DIR, out_name)

        # Read the source image
        reader = QtImageReader(SOURCE)
        reader.Open()
        frame = reader.GetFrame(FRAME_NUMBER)

        # Apply the LUT
        effect = ColorMap(cube_path)
        result = effect.GetFrame(frame, FRAME_NUMBER)

        # Save downscaled JPEG at 90% quality
        result.Save(out_path, 0.35, "JPG", 90)

        # Add larger border and overlay larger text
        try:
            img = Image.open(out_path).convert("RGB")
            bordered = ImageOps.expand(img, border=BORDER_SIZE, fill="white")

            draw = ImageDraw.Draw(bordered)
            text = name_base.replace("_", " ")
            bbox = draw.textbbox((0, 0), text, font=FONT)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            x = (bordered.width - tw) // 2
            y = bordered.height - BORDER_SIZE - th - TEXT_OFFSET
            draw.text((x, y), text, fill="white", font=FONT)

            bordered.save(out_path, "JPEG", quality=90)
        except Exception as e:
            print(f"Warning: could not annotate {out_path}: {e}")

        gallery[category].append(out_name)

# Emit Sphinx-friendly gallery RST to stdout
for category, images in gallery.items():
    title = category.replace("_", " ").title()
    print(title)
    print("^" * len(title))
    print()
    print(".. container:: gallery")
    print()
    for img_name in images:
        print(f"   .. image:: images/colors/{img_name}")
        print("      :width: 30%")
        print()
    print()
