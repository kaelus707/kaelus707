"""Convert a photo to ascii_art.txt: python tools/img_to_ascii.py photo.jpg [width]"""
import sys
from PIL import Image, ImageOps

RAMP = "@%#*+=-:. "
src = sys.argv[1]
width = int(sys.argv[2]) if len(sys.argv) > 2 else 48
img = ImageOps.autocontrast(ImageOps.exif_transpose(Image.open(src)).convert("L"))
height = int(img.height / img.width * width * 0.5)  # chars are ~2x taller than wide
img = img.resize((width, height))
px = list(img.getdata())
rows = ["".join(RAMP[p * (len(RAMP) - 1) // 255] for p in px[r * width:(r + 1) * width])
        for r in range(height)]
open("ascii_art.txt", "w", encoding="utf-8").write("\n".join(rows) + "\n")
