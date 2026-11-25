#!/usr/bin/env python3
"""news-image-20261124: one-day world news image, Tuesday 24 November 2026.

Draws a 1024x1024 newspaper front page with a hand-rolled PNG writer, a
mini rasterizer, and an embedded 5x7 bitmap font. Python 3.13 stdlib only,
no network, fully deterministic: two runs write identical bytes.

Layout (1024x1024): masthead + hero (Riyadh PIF strike + Hormuz mine CLAIM,
visually separated fact vs unverified claim) + 3 featured boxes + 2-box
strip + 44-row UTC wire in 2 columns + date-check footer. The only date
shown anywhere is 24 November 2026.
"""
import os
import struct
import zlib

W, H = 1024, 1024

# --- palette ---
PAPER = (248, 246, 240)     # warm paper white
INK = (17, 17, 17)          # near-black text
NAVY = (11, 42, 74)         # masthead navy
RED = (155, 27, 27)         # dark red accent
GRAY = (96, 96, 96)         # secondary text
LINEC = (196, 192, 184)     # light rules
BOXC = (233, 231, 225)      # light box fill
CLAIM_BG = (250, 236, 234)  # light red tint for the claim box
CLAIM_BAR = (155, 27, 27)   # red bar on the claim box
WHITE = (255, 255, 255)

# --- 5x7 bitmap font: char -> 7 rows, each a 5-bit value (bit 4 = left pixel) ---
FONT = {
    " ": (0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00),
    "!": (0x04, 0x04, 0x04, 0x04, 0x04, 0x00, 0x04),
    '"': (0x0A, 0x0A, 0x0A, 0x00, 0x00, 0x00, 0x00),
    "#": (0x0A, 0x0A, 0x1F, 0x0A, 0x1F, 0x0A, 0x0A),
    "$": (0x04, 0x0F, 0x14, 0x0E, 0x05, 0x1E, 0x04),
    "%": (0x18, 0x19, 0x02, 0x04, 0x08, 0x13, 0x03),
    "&": (0x0C, 0x12, 0x14, 0x08, 0x15, 0x12, 0x0D),
    "'": (0x04, 0x04, 0x08, 0x00, 0x00, 0x00, 0x00),
    "(": (0x02, 0x04, 0x08, 0x08, 0x08, 0x04, 0x02),
    ")": (0x08, 0x04, 0x02, 0x02, 0x02, 0x04, 0x08),
    "*": (0x00, 0x04, 0x15, 0x0E, 0x15, 0x04, 0x00),
    "+": (0x00, 0x04, 0x04, 0x1F, 0x04, 0x04, 0x00),
    ",": (0x00, 0x00, 0x00, 0x00, 0x0C, 0x04, 0x08),
    "-": (0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00),
    ".": (0x00, 0x00, 0x00, 0x00, 0x00, 0x0C, 0x0C),
    "/": (0x01, 0x02, 0x02, 0x04, 0x08, 0x08, 0x10),
    "0": (0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E),
    "1": (0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "2": (0x0E, 0x11, 0x01, 0x06, 0x08, 0x10, 0x1F),
    "3": (0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E),
    "4": (0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02),
    "5": (0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E),
    "6": (0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E),
    "7": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08),
    "8": (0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E),
    "9": (0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C),
    ":": (0x00, 0x0C, 0x0C, 0x00, 0x0C, 0x0C, 0x00),
    ";": (0x00, 0x0C, 0x0C, 0x00, 0x0C, 0x04, 0x08),
    "<": (0x02, 0x04, 0x08, 0x10, 0x08, 0x04, 0x02),
    "=": (0x00, 0x00, 0x1F, 0x00, 0x1F, 0x00, 0x00),
    ">": (0x08, 0x04, 0x02, 0x01, 0x02, 0x04, 0x08),
    "?": (0x0E, 0x11, 0x01, 0x02, 0x04, 0x00, 0x04),
    "@": (0x0E, 0x11, 0x11, 0x16, 0x15, 0x10, 0x0E),
    "A": (0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "B": (0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E),
    "C": (0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E),
    "D": (0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E),
    "E": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F),
    "F": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10),
    "G": (0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F),
    "H": (0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "I": (0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "J": (0x01, 0x01, 0x01, 0x01, 0x01, 0x11, 0x0E),
    "K": (0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11),
    "L": (0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F),
    "M": (0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11),
    "N": (0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11),
    "O": (0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "P": (0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10),
    "Q": (0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D),
    "R": (0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11),
    "S": (0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E),
    "T": (0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    "U": (0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "V": (0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04),
    "W": (0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11),
    "X": (0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11),
    "Y": (0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04),
    "Z": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F),
    "[": (0x0E, 0x08, 0x08, 0x08, 0x08, 0x08, 0x0E),
    "\\": (0x10, 0x08, 0x08, 0x04, 0x02, 0x02, 0x01),
    "]": (0x0E, 0x02, 0x02, 0x02, 0x02, 0x02, 0x0E),
    "^": (0x04, 0x0A, 0x11, 0x00, 0x00, 0x00, 0x00),
    "_": (0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F),
    "`": (0x04, 0x04, 0x02, 0x00, 0x00, 0x00, 0x00),
    "a": (0x00, 0x00, 0x0E, 0x01, 0x0F, 0x11, 0x0F),
    "b": (0x10, 0x10, 0x16, 0x19, 0x11, 0x11, 0x1E),
    "c": (0x00, 0x00, 0x0E, 0x11, 0x10, 0x11, 0x0E),
    "d": (0x01, 0x01, 0x0D, 0x13, 0x11, 0x11, 0x0F),
    "e": (0x00, 0x00, 0x0E, 0x11, 0x1F, 0x10, 0x0E),
    "f": (0x06, 0x08, 0x08, 0x1E, 0x08, 0x08, 0x08),
    "g": (0x00, 0x0F, 0x11, 0x11, 0x0F, 0x01, 0x0E),
    "h": (0x10, 0x10, 0x16, 0x19, 0x11, 0x11, 0x11),
    "i": (0x04, 0x00, 0x0C, 0x04, 0x04, 0x04, 0x0E),
    "j": (0x02, 0x00, 0x06, 0x02, 0x02, 0x12, 0x0C),
    "k": (0x10, 0x10, 0x12, 0x14, 0x18, 0x14, 0x12),
    "l": (0x0C, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "m": (0x00, 0x00, 0x1A, 0x15, 0x15, 0x15, 0x15),
    "n": (0x00, 0x00, 0x16, 0x19, 0x11, 0x11, 0x11),
    "o": (0x00, 0x00, 0x0E, 0x11, 0x11, 0x11, 0x0E),
    "p": (0x00, 0x00, 0x1E, 0x11, 0x11, 0x1E, 0x10),
    "q": (0x00, 0x00, 0x0D, 0x13, 0x11, 0x0F, 0x01),
    "r": (0x00, 0x00, 0x16, 0x19, 0x10, 0x10, 0x10),
    "s": (0x00, 0x00, 0x0F, 0x10, 0x0E, 0x01, 0x1E),
    "t": (0x08, 0x08, 0x1E, 0x08, 0x08, 0x09, 0x06),
    "u": (0x00, 0x00, 0x11, 0x11, 0x11, 0x13, 0x0D),
    "v": (0x00, 0x00, 0x11, 0x11, 0x11, 0x0A, 0x04),
    "w": (0x00, 0x00, 0x11, 0x15, 0x15, 0x1B, 0x11),
    "x": (0x00, 0x00, 0x11, 0x0A, 0x04, 0x0A, 0x11),
    "y": (0x00, 0x00, 0x11, 0x11, 0x0F, 0x01, 0x0E),
    "z": (0x00, 0x00, 0x1F, 0x02, 0x04, 0x08, 0x1F),
    "{": (0x06, 0x08, 0x08, 0x07, 0x08, 0x08, 0x06),
    "|": (0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    "}": (0x0C, 0x02, 0x02, 0x1C, 0x02, 0x02, 0x0C),
    "~": (0x00, 0x00, 0x00, 0x0E, 0x15, 0x00, 0x00),
}

# --- framebuffer (RGB, 3 bytes per pixel) ---
fb = bytearray(bytes(PAPER) * (W * H))


def fill_rect(x, y, w, h, color):
    """Fill an axis-aligned rectangle, clipped to the canvas."""
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(W, x + w)
    y1 = min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    row = bytes(color) * (x1 - x0)
    n = len(row)
    for yy in range(y0, y1):
        o = (yy * W + x0) * 3
        fb[o:o + n] = row


def rect_outline(x, y, w, h, color, t=1):
    fill_rect(x, y, w, t, color)
    fill_rect(x, y + h - t, w, t, color)
    fill_rect(x, y, t, h, color)
    fill_rect(x + w - t, y, t, h, color)


def set_px(x, y, color):
    if 0 <= x < W and 0 <= y < H:
        o = (y * W + x) * 3
        fb[o:o + 3] = bytes(color)


def line(x0, y0, x1, y1, color):
    """Bresenham line."""
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        set_px(x0, y0, color)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def disc(cx, cy, r, color):
    """Filled circle."""
    for dy in range(-r, r + 1):
        dx = int((r * r - dy * dy) ** 0.5)
        fill_rect(cx - dx, cy + dy, 2 * dx + 1, 1, color)


def _glyph_runs(ch, scale):
    """Per glyph row, the runs of set pixels as (x0, x1) in scaled coords."""
    bits = FONT.get(ch, FONT["?"])
    runs = []
    for r in range(7):
        b = bits[r]
        row_runs = []
        c = 0
        while c < 5:
            if (b >> (4 - c)) & 1:
                c0 = c
                while c < 5 and ((b >> (4 - c)) & 1):
                    c += 1
                row_runs.append((c0 * scale, c * scale))
            else:
                c += 1
        runs.append(row_runs)
    return runs


def text_adv(scale, bold=False):
    """Horizontal advance per character at a given scale."""
    return 5 * scale + (2 if bold else 1)


def text_w(s, scale, bold=False):
    return len(s) * text_adv(scale, bold)


def draw_text(x, y, s, color, scale, bold=False):
    """Draw left-aligned text; returns the width in pixels.

    Bold is faked by stamping each run once more 1 px to the right.
    """
    rgb = bytes(color)
    adv = text_adv(scale, bold)
    cx = x
    for ch in s:
        runs = _glyph_runs(ch, scale)
        for r in range(7):
            for (x0, x1) in runs[r]:
                wpx = x1 - x0
                rowbytes = rgb * wpx
                for sy in range(scale):
                    yy = y + r * scale + sy
                    if yy < 0 or yy >= H:
                        continue
                    o = (yy * W + cx + x0) * 3
                    n = wpx * 3
                    fb[o:o + n] = rowbytes
                    if bold:
                        o2 = o + 3
                        fb[o2:o2 + n] = rowbytes
        cx += adv
    return cx - x


def draw_text_centered(cx, y, s, color, scale, bold=False):
    w = text_w(s, scale, bold)
    return draw_text(cx - w // 2, y, s, color, scale, bold)


def _png_chunk(typ, data):
    c = struct.pack(">I", len(data)) + typ + data
    c += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
    return c


def write_png(path):
    raw = b"".join(b"\x00" + bytes(fb[y * W * 3:(y + 1) * W * 3])
                   for y in range(H))
    png = b"\x89PNG\r\n\x1a\n"
    png += _png_chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += _png_chunk(b"IDAT", zlib.compress(raw, 9))
    png += _png_chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# --- content: 44 wire rows (43 verified + RSF Sudan), each <= 43 chars ---
# (time, headline); empty time = untimed item. Chronological by UTC.
WIRE = [
    ("01:00", "Hanoi gas blast kills 6, injures 14"),
    ("01:16", "Shenzhou-24 crew named, 1st Pakistani"),
    ("01:32", "Nepal quake 5.6; no casualties"),
    ("02:56", "Hasina plans return to Bangladesh"),
    ("04:00", "Zaporizhzhia hit; 2 killed, 40 hurt"),
    ("04:32", "Report: Commanders edge Bengals 22-20"),
    ("08:20", "Iran: no talks until 7 conditions met"),
    ("", "US warns citizens across Middle East"),
    ("", "Iran claims 3 tankers hit mines in Hormuz"),
    ("10:08", "Bitcoin drops below $60,000"),
    ("12:12", "Israel kills Hamas security chief"),
    ("12:22", "China probes Shanghai chief Chen"),
    ("12:24", "Zelensky admits hit on Sparta II"),
    ("", "Malaysia to send home 6,803 Myanmar"),
    ("", "UNAIDS: AIDS deaths lowest in 20+ years"),
    ("", "Gaza warns meningitis surge; 272 cases Oct"),
    ("13:52", "U2 announce 2027 North America tour"),
    ("", "Pope diaries reveal spiritual crisis"),
    ("16:45", "Galatasaray 1-0 Villa; Bodo 1-0 LASK"),
    ("17:01", "Houthi drone hits PIF Tower, 11 hurt"),
    ("", "Euclid finds most distant quasar ever"),
    ("", "CAS restores Senegal as AFCON champions"),
    ("19:40", "Putin vows retaliation on refineries"),
    ("", "Huawei guilty on 10 of 12 counts"),
    ("", "CIA, ODNI unclassified systems breached"),
    ("", "Trump awards Medal of Freedom to Giuliani"),
    ("", "Sarkozy, Bruni ordered to corruption trial"),
    ("", "Shein to pay $100m to FTC over deception"),
    ("", "Iraq orders federal control of Kurdish oil"),
    ("", "Colombia car bomb injures 23"),
    ("", "UK sanctions 5 Myanmar generals"),
    ("", "Democrats flip Tennessee House seat"),
    ("", "Trump pardons turkeys 'Freedom', 'Feathers'"),
    ("20:00", "Real Madrid 5-1 PSV; City 2-2 Napoli"),
    ("20:00", "Arsenal 1-1 Dortmund; Leipzig 3-1"),
    ("", "England beat Australia by 8 wickets"),
    ("", "Georgia top first College Football Playoff"),
    ("", "Turkish military helicopter crash kills 5"),
    ("21:00", "Dow crosses 50,000; Nasdaq falls 1.5%"),
    ("21:23", "Dell revenue doubles; backlog $132bn"),
    ("", "Macy's unveils 100th Thanksgiving parade"),
    ("", "RSF drone strikes kill 19 in Sudan"),
    ("", "Ulleung air-raid alert (Nov 24 KST)"),
    ("22:36", "Saudi orders Hodeidah port evacuated"),
]

FEATURED = [
    # (x, kicker, headline lines, summary lines)
    (24, "COURTS",
     ["HUAWEI GUILTY ON", "10 OF 12 COUNTS"],
     ["US jury convicts on bank", "fraud and sanctions;",
      "acquits on racketeering."]),
    (354, "MARKETS",
     ["NVIDIA SINKS 5.9%", "DOW TOPS 50,000"],
     ["Bitcoin falls below", "$60,000; Dell AI backlog",
      "hits $132bn."]),
    (684, "GAZA",
     ["ISRAEL KILLS", "HAMAS CHIEF"],
     ["7 dead in Gaza;", "meningitis surge warned,",
      "272 cases in Oct."]),
]


def fill_poly(points, color):
    """Scanline fill for a convex polygon."""
    ys = [p[1] for p in points]
    y0, y1 = min(ys), max(ys)
    n = len(points)
    for y in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            x0, yy0 = points[i]
            x1, yy1 = points[(i + 1) % n]
            if yy0 == yy1:
                continue
            if (yy0 <= y < yy1) or (yy1 <= y < yy0):
                t = (y - yy0) / (yy1 - yy0)
                xs.append(x0 + t * (x1 - x0))
        if len(xs) >= 2:
            xs.sort()
            fill_rect(int(xs[0]), y, int(xs[-1]) - int(xs[0]) + 1, 1, color)


def masthead():
    draw_text_centered(512, 6, "THE WORLD IN ONE DAY", NAVY, 7, bold=True)
    draw_text_centered(512, 58, "TUESDAY - 24 NOVEMBER 2026", INK, 4, bold=True)
    fill_rect(24, 88, 976, 4, NAVY)


def draw_tower_graphic():
    """Stylised PIF tower + drone (the strike is a fact; no burning tanker,
    no exploding mines drawn anywhere)."""
    # tower: tapered body, navy, with stepped crown
    fill_poly([(892, 360), (958, 360), (950, 215), (900, 215)], NAVY)
    fill_rect(906, 202, 38, 13, NAVY)
    fill_rect(912, 192, 26, 10, NAVY)
    fill_rect(918, 184, 14, 8, NAVY)
    # window lines
    for yy in range(228, 356, 12):
        line(903, yy, 947, yy, (120, 140, 165))
    # impact flash on the tower (red dot + radiating ticks)
    disc(925, 238, 6, RED)
    for (dx, dy) in ((-12, -8), (12, -8), (-12, 8), (12, 8)):
        line(925, 238, 925 + dx, 238 + dy, RED)
    # drone above-left, with a dotted flight path to the impact point
    for i in range(5):
        t = i / 4.0
        disc(int(862 + t * 58), int(182 + t * 50), 2, GRAY)
    disc(856, 178, 5, INK)
    for (dx, dy) in ((-13, -6), (13, -6), (-13, 6), (13, 6)):
        line(856, 178, 856 + dx, 178 + dy, INK)
        disc(856 + dx, 178 + dy, 3, GRAY)


def hero():
    draw_text(28, 100, "GULF WAR WIDENS", RED, 3, bold=True)
    draw_text(28, 128, "RIYADH STRIKE & HORMUZ MINE CLAIM", INK, 5, bold=True)
    # fact line (plain text): the PIF strike, 11 injured
    draw_text(28, 174, "Repeat Houthi drone hits PIF tower, 11 injured",
              INK, 2)
    # claim box: visually separated, tinted, labelled UNVERIFIED CLAIM
    fill_rect(28, 194, 812, 56, CLAIM_BG)
    fill_rect(28, 194, 6, 56, CLAIM_BAR)
    draw_text(44, 202, "UNVERIFIED CLAIM", RED, 2, bold=True)
    draw_text(44, 224, "IRGC claims 3 tankers hit mines in Hormuz; "
              "no CENTCOM response.", INK, 2)
    # summary line
    draw_text(28, 262, "Saudi coalition vows a firm response; "
              "orders Hodeidah port evacuated.", INK, 2)
    draw_tower_graphic()
    fill_rect(24, 368, 976, 2, LINEC)


def featured():
    for (x, kicker, head, summ) in FEATURED:
        rect_outline(x, 372, 314, 176, LINEC, 1)
        draw_text(x + 12, 386, kicker, RED, 2, bold=True)
        yy = 408
        for ln in head:
            draw_text(x + 12, yy, ln, INK, 3, bold=True)
            yy += 25
        yy = 464
        for ln in summ:
            draw_text(x + 12, yy, ln, INK, 2)
            yy += 17


def strip():
    # box 1: Putin / Zaporizhzhia
    rect_outline(24, 548, 480, 84, LINEC, 1)
    draw_text(36, 556, "UKRAINE", RED, 2, bold=True)
    draw_text(36, 572, "PUTIN VOWS RETALIATION", INK, 2, bold=True)
    draw_text(36, 587, "ZAPORIZHZHIA HIT KILLS 2, HURTS 40", INK, 2, bold=True)
    draw_text(36, 604, "Ukraine hits refineries; Moscow curbs", GRAY, 2)
    # box 2: Chen Jining / Malaysia
    rect_outline(520, 548, 480, 84, LINEC, 1)
    draw_text(532, 556, "ASIA", RED, 2, bold=True)
    draw_text(532, 572, "CHINA PROBES SHANGHAI BOSS CHEN", INK, 2, bold=True)
    draw_text(532, 589, "Malaysia to send home 6,803 Myanmar.", GRAY, 2)


def wire():
    draw_text(24, 634, "THE WORLD WIRE - TUESDAY 24 NOVEMBER 2026 (UTC)",
              NAVY, 2, bold=True)
    fill_rect(24, 650, 976, 2, NAVY)
    # 2 columns x 22 rows, 15 px pitch, 14 px glyphs
    for col in range(2):
        x = 24 + col * 496
        rows = WIRE[col * 22:(col + 1) * 22]
        for i, (t, head) in enumerate(rows):
            y = 654 + i * 15
            cx = x
            if t:
                draw_text(cx, y, t, RED, 2, bold=True)
                cx += 6 * text_adv(2, bold=True)
            draw_text(cx, y, head, INK, 2)


def footer():
    rect_outline(24, 986, 976, 20, NAVY, 1)
    draw_text(32, 989, "DATE CHECK - Every item happened or was first "
              "reported Tue 24 Nov 2026 (UTC).", INK, 2)
    draw_text_centered(512, 1010, "Reuters - AP - AFP - BBC - Al Jazeera - "
                       "UEFA - ESA - Xinhua", GRAY, 2)


def build():
    masthead()
    hero()
    featured()
    strip()
    wire()
    footer()


def main():
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    build()
    n = write_png(path)
    import hashlib
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    print("wrote %s (%d bytes) sha256=%s" % (path, n, h))


if __name__ == "__main__":
    main()
