"""Draw small car trim textures from period ZAZ-968 and VAZ-2101/2106 references."""
import random

SIZE = 128
STRIP = 20
DIGITS = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "6": ("111", "100", "111", "101", "111"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
    "A": ("010", "101", "111", "101", "101"),
    "M": ("101", "111", "111", "101", "101"),
    " ": ("000", "000", "000", "000", "000"),
}
# Atlas rows run from bottom to top in both renderers.
GRILLE = {"ZAZ": 0, "2101": 1, "2106": 2}
PLATE = {"ZAZ": 3, "2101": 4, "2106": 5}


def build_atlas():
    rng = random.Random(9682106)
    texels = bytearray(4 * SIZE * SIZE)

    def put(x, y, color):
        i = (y * SIZE + x) * 4
        texels[i:i+4] = bytes((*color, 255))

    def mark(x, y, width, height, paint):
        for dx in range(width):
            for dy in range(height):
                put(x + dx, y + dy, paint)

    for model, row in GRILLE.items():
        y0 = row * STRIP
        for y in range(STRIP):
            for x in range(SIZE):
                if model == "ZAZ":
                    tone = 150 if y in (0, 19) else 42 if 4 < y < 15 else 78
                elif y in (0, 19) or x < 2 or x >= 126:
                    tone = 109
                elif y in (1, 18):
                    tone = 195
                elif model == "2101":
                    tone = 177 if y % 3 == 0 else 61 if x % 7 < 5 else 106
                else:
                    tone = 90 if y % 4 == 0 or x % 8 == 0 else 45
                tone += rng.randint(-7, 7)
                put(x, y0 + y, (tone + 5, tone + 1, tone - 5))
        if model == "ZAZ":
            mark(49, y0 + 8, 30, 3, (181, 181, 165))
        else:
            mark(58, y0 + 2, 12, 16, (173, 165, 147))
            mark(60, y0 + 4, 8, 12, (110, 44, 38))
            for y, width in enumerate((7, 5, 3, 1)):
                mark(64 - width // 2, y0 + 6 + y, width, 1, (210, 204, 187))
            mark(64, y0 + 10, 1, 3, (207, 200, 184))

    for model, row in PLATE.items():
        y0 = row * STRIP
        pale = model != "2101"
        for y in range(STRIP):
            for x in range(SIZE):
                shade = (193 if pale else 54) + rng.randint(-9, 9)
                if not 1 <= y < 19 or not 2 <= x < 126:
                    shade += 32 if not pale else -70
                put(x, y0 + y, (shade + 8, shade + 5, shade))
        ink = (43, 41, 37) if pale else (212, 207, 181)
        
        number = {"ZAZ": "3A3 968M", "2101": "1042", "2106": "2360"}[model]
        scale, step = (2, 12) if model == "ZAZ" else (3, 16)
        start = (SIZE - step * len(number)) // 2
        for column, digit in enumerate(number):
            for line, pixels in enumerate(reversed(DIGITS[digit])):
                for bit, active in enumerate(pixels):
                    if active == "1":
                        mark(start + column * step + bit * scale, y0 + 5 + line * 2, scale, 2, ink)
        mark(8, y0 + 9, 2, 2, (108, 102, 89))
        mark(118, y0 + 9, 2, 2, (108, 102, 89))
    return texels
