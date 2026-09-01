# -*- coding: utf-8 -*-
"""Generates every texture and icon the Alamo skin needs (no binaries in git).

Run:  python3 tools/make_media.py
"""
import os
import math

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.join(HERE, '..', 'plugin.video.alamo')
SKIN_MEDIA = os.path.join(ADDON, 'resources', 'skins', 'Default', 'media')
MEDIA = os.path.join(ADDON, 'resources', 'media')

GOLD = (232, 180, 74)
DIM = (154, 154, 166)


def save(image, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    image.save(path)
    print('wrote', os.path.normpath(path))


# -- skin textures ---------------------------------------------------------

def white():
    save(Image.new('RGBA', (16, 16), (255, 255, 255, 255)),
         os.path.join(SKIN_MEDIA, 'white.png'))


def fade(name, horizontal=False, size=256):
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    pixels = image.load()
    for i in range(size):
        alpha = int(255 * (1 - i / (size - 1.0)) ** 1.4) if horizontal \
            else int(255 * (i / (size - 1.0)) ** 1.4)
        for j in range(size):
            if horizontal:
                pixels[i, j] = (0, 0, 0, alpha)
            else:
                pixels[j, i] = (0, 0, 0, alpha)
    save(image, os.path.join(SKIN_MEDIA, name))


def frame():
    """A rounded 4px border used as the focus ring (9-slice, border=10)."""
    size, radius, thickness = 64, 12, 4
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([1, 1, size - 2, size - 2], radius=radius,
                           outline=(255, 255, 255, 255), width=thickness)
    save(image, os.path.join(SKIN_MEDIA, 'frame.png'))


def spinner():
    size = 96
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    for index in range(12):
        angle = index * math.pi / 6
        alpha = int(30 + 225 * index / 11.0)
        x = size / 2 + math.cos(angle) * 34
        y = size / 2 + math.sin(angle) * 34
        draw.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(255, 255, 255, alpha))
    save(image, os.path.join(SKIN_MEDIA, 'spinner.png'))


def check():
    image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.line([(12, 34), (26, 48), (52, 16)], fill=(255, 255, 255, 255),
              width=8, joint='curve')
    save(image, os.path.join(SKIN_MEDIA, 'check.png'))


def logo():
    """Wordmark: THE ALAMO with a gold star."""
    from PIL import ImageFont
    image = Image.new('RGBA', (416, 116), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = None
    for candidate in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                      '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'):
        if os.path.exists(candidate):
            font = ImageFont.truetype(candidate, 46)
            break
    small = None
    if font:
        small = ImageFont.truetype(font.path, 20)
    draw.text((66, 34), 'ALAMO', font=font, fill=(255, 255, 255, 255))
    if small:
        draw.text((68, 12), 'T H E', font=small, fill=GOLD)
    # star
    points = []
    cx, cy, outer, inner = 30, 58, 24, 10
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        radius = outer if i % 2 == 0 else inner
        points.append((cx + math.cos(angle) * radius,
                       cy + math.sin(angle) * radius))
    draw.polygon(points, fill=GOLD)
    save(image, os.path.join(SKIN_MEDIA, 'logo.png'))


# -- nav icons -------------------------------------------------------------

def _icon(draw_fn, name, size=96):
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw_fn(draw, size)
    save(image, os.path.join(MEDIA, name))


def nav_icons():
    w = (255, 255, 255, 255)

    def home(d, s):
        d.polygon([(s * .5, s * .16), (s * .88, s * .5), (s * .12, s * .5)], fill=w)
        d.rectangle([s * .24, s * .48, s * .76, s * .84], fill=w)

    def movies(d, s):
        d.rounded_rectangle([s * .12, s * .22, s * .88, s * .78], radius=8,
                            outline=w, width=6)
        for i in range(4):
            x = s * (.22 + i * .19)
            d.rectangle([x, s * .12, x + s * .08, s * .24], fill=w)
            d.rectangle([x, s * .76, x + s * .08, s * .88], fill=w)

    def tv(d, s):
        d.rounded_rectangle([s * .1, s * .26, s * .9, s * .74], radius=8,
                            outline=w, width=6)
        d.line([(s * .3, s * .84), (s * .7, s * .84)], fill=w, width=6)
        d.line([(s * .5, s * .74), (s * .5, s * .84)], fill=w, width=6)

    def sports(d, s):
        d.ellipse([s * .12, s * .12, s * .88, s * .88], outline=w, width=6)
        d.line([(s * .5, s * .12), (s * .5, s * .88)], fill=w, width=5)
        d.arc([s * .3, s * .12, s * 1.1, s * .88], 100, 260, fill=w, width=5)
        d.arc([s * -.1, s * .12, s * .7, s * .88], 280, 80, fill=w, width=5)

    def search(d, s):
        d.ellipse([s * .16, s * .16, s * .68, s * .68], outline=w, width=7)
        d.line([(s * .62, s * .62), (s * .86, s * .86)], fill=w, width=8)

    def mylist(d, s):
        d.polygon([(s * .24, s * .12), (s * .76, s * .12), (s * .76, s * .88),
                   (s * .5, s * .66), (s * .24, s * .88)], outline=w, width=6)

    def settings(d, s):
        d.ellipse([s * .3, s * .3, s * .7, s * .7], outline=w, width=7)
        for i in range(8):
            angle = i * math.pi / 4
            x1 = s * .5 + math.cos(angle) * s * .34
            y1 = s * .5 + math.sin(angle) * s * .34
            x2 = s * .5 + math.cos(angle) * s * .46
            y2 = s * .5 + math.sin(angle) * s * .46
            d.line([(x1, y1), (x2, y2)], fill=w, width=7)

    for fn, name in ((home, 'nav_home.png'), (movies, 'nav_movies.png'),
                     (tv, 'nav_tv.png'), (sports, 'nav_sports.png'),
                     (search, 'nav_search.png'), (mylist, 'nav_mylist.png'),
                     (settings, 'nav_settings.png')):
        _icon(fn, name)


def sports_tile():
    """Fallback artwork for sports items with no image."""
    width, height = 500, 750
    image = Image.new('RGB', (width, height), (12, 12, 18))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        shade = int(10 + 26 * (y / height))
        draw.line([(0, y), (width, y)], fill=(shade, shade, shade + 6))
    points = []
    cx, cy, outer, inner = width / 2, height / 2, 120, 52
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        radius = outer if i % 2 == 0 else inner
        points.append((cx + math.cos(angle) * radius,
                       cy + math.sin(angle) * radius))
    draw.polygon(points, fill=GOLD)
    image = image.filter(ImageFilter.SMOOTH)
    save(image, os.path.join(MEDIA, 'sports_tile.png'))


def main():
    white()
    fade('fade_bottom.png')
    fade('fade_left.png', horizontal=True)
    frame()
    spinner()
    check()
    logo()
    nav_icons()
    sports_tile()


if __name__ == '__main__':
    main()
