"""Generate static/og-image.png (1200x630) from logo-tb.png on brand background."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
LOGO = STATIC / "logo-tb.png"
OUT = STATIC / "og-image.png"

W, H = 1200, 630
BG_TOP = (10, 10, 14)
BG_BOTTOM = (24, 20, 8)
GOLD = (212, 175, 55)
WHITE = (245, 245, 245)
MUTED = (170, 170, 170)

img = Image.new("RGB", (W, H), BG_TOP)
for y in range(H):
    t = y / (H - 1)
    r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
    g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
    b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
    for x in range(W):
        img.putpixel((x, y), (r, g, b))

draw = ImageDraw.Draw(img, "RGBA")
glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gdraw = ImageDraw.Draw(glow)
gdraw.ellipse((-200, -300, 700, 500), fill=(212, 175, 55, 40))
gdraw.ellipse((700, 300, 1500, 900), fill=(212, 175, 55, 25))
img.paste(glow, (0, 0), glow)

logo = Image.open(LOGO).convert("RGBA")
target_w = 520
ratio = target_w / logo.width
logo = logo.resize((target_w, int(logo.height * ratio)), Image.LANCZOS)
lx = (W - logo.width) // 2
ly = 110
img.paste(logo, (lx, ly), logo)

def load_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()

title_font = load_font(64, bold=True)
sub_font = load_font(32, bold=False)
url_font = load_font(28, bold=True)

title = "TRADING BONUS HUB"
sub = "Bonus - Rebate - Khuyen mai san moi nhat"
url = "tradingbonushub.com"

def draw_centered(text, y, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, y), text, font=font, fill=fill)

draw_centered(title, ly + logo.height + 40, title_font, GOLD)
draw_centered(sub, ly + logo.height + 120, sub_font, WHITE)

draw.rectangle((0, H - 70, W, H), fill=(0, 0, 0, 180))
draw_centered(url, H - 55, url_font, GOLD)

img.save(OUT, "PNG", optimize=True)
print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
