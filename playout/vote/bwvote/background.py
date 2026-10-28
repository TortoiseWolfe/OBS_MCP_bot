"""The still picture behind the live text: blurred cover, the cover itself, and the words that never change."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H = 1280, 720


def build(cover, font, out):
    f = lambda n: ImageFont.truetype(str(Path(font).expanduser()), n)
    art = Image.open(Path(cover).expanduser()).convert("RGB")
    bg = art.resize((W, W)).crop((0, (W - H) // 2, W, (W - H) // 2 + H)).filter(ImageFilter.GaussianBlur(24))
    bg = ImageEnhance.Brightness(bg).enhance(0.35)
    d = ImageDraw.Draw(bg, "RGBA")
    d.rounded_rectangle((660, 30, 1250, 690), 24, fill=(10, 8, 24, 190))
    bg.paste(art.resize((600, 600)), (30, 60))
    d.text((690, 52), "NOW PLAYING", font=f(28), fill=(255, 196, 64))
    d.text((690, 400), "Vote in chat!", font=f(36), fill=(255, 255, 255))
    d.text((690, 446), "!up  = I like it     !down  = not for me", font=f(26), fill=(190, 230, 255))
    d.text((690, 500), "TOP SONGS SO FAR", font=f(24), fill=(255, 196, 64))
    d.text((690, 660), "Music made with AI", font=f(20), fill=(170, 170, 190))
    out = Path(out)
    tmp = out.with_name(out.stem + ".tmp.png")
    bg.save(tmp)
    tmp.replace(out)  # ffmpeg re-reads this file every frame: it must never see half a picture
