"""Enumerates fonts available for captions: the bundled ones plus everything
installed in Windows.

For each face we need three things the GUI and the renderer disagree about:
  - an absolute path, because renderer.py loads faces by path;
  - a CSS family/weight, because the live preview draws with the system font;
  - whether it can actually draw Cyrillic, since most display faces cannot and
    silently fall back to boxes.

The scan takes a second or two over a few hundred files, so it is cached and
only redone when the font folders change.
"""

import os
import sys
import json
import glob

from PIL import ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
CACHE_PATH = os.path.join(BASE_DIR, "cache", "fonts.json")

FONT_DIRS = [
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts"),
]

EXTENSIONS = (".ttf", ".otf", ".ttc")

# Style keyword -> CSS weight. Longest match wins, so "extrabold" is checked
# before "bold".
WEIGHT_WORDS = [
    ("extrablack", 900), ("extrabold", 800), ("ultrabold", 800),
    ("semibold", 600), ("demibold", 600), ("extralight", 200), ("ultralight", 200),
    ("black", 900), ("heavy", 900), ("bold", 700), ("medium", 500),
    ("regular", 400), ("normal", 400), ("book", 400),
    ("light", 300), ("thin", 100), ("hairline", 100),
]

CYRILLIC_PROBE = "АБЯжэ"

# Style tokens that may be glued to the family name ("Stem-ExtraLightItalic").
# Longest first so "extralight" wins over "light".
STYLE_TOKENS = [
    "extrablack", "extrabold", "ultrabold", "semibold", "demibold",
    "extralight", "ultralight", "hairline", "black", "heavy", "bold",
    "medium", "regular", "normal", "book", "light", "thin",
    "italic", "oblique",
]

TOKEN_LABELS = {
    "extrablack": "ExtraBlack", "extrabold": "ExtraBold", "ultrabold": "UltraBold",
    "semibold": "SemiBold", "demibold": "DemiBold", "extralight": "ExtraLight",
    "ultralight": "UltraLight", "hairline": "Hairline", "black": "Black",
    "heavy": "Heavy", "bold": "Bold", "medium": "Medium", "regular": "Regular",
    "normal": "Normal", "book": "Book", "light": "Light", "thin": "Thin",
    "italic": "Italic", "oblique": "Oblique",
}


def _css_weight(style_name):
    s = (style_name or "").lower().replace(" ", "").replace("-", "")
    for word, weight in WEIGHT_WORDS:
        if word in s:
            return weight
    return 400


def _split_style_tokens(tail):
    """Splits a glued style tail like 'ExtraLightItalic' into its tokens."""
    rest = tail.lower().replace(" ", "").replace("-", "").replace("_", "")
    found = []
    progressed = True
    while rest and progressed:
        progressed = False
        for token in STYLE_TOKENS:
            if rest.startswith(token):
                found.append(token)
                rest = rest[len(token):]
                progressed = True
                break
    return (found, rest) if not rest else (found, rest)


def _css_stack(family, style, raw_family):
    """Candidate CSS families, most specific first.

    Windows registers some faces as families of their own ("Arial Black",
    "Arial Narrow", "Segoe UI Semibold") while others live as weights inside
    one family ("Stem" + weight 700). Listing the variants lets the browser
    pick whichever actually exists instead of silently substituting a
    different typeface.
    """
    variants = []
    generic = style.lower() in ("regular", "normal", "book")
    if style and not generic:
        variants.append(f"{family} {style}")
        # e.g. "Narrow" is part of the family name, "Bold" is a weight
        keep = [t for t in style.split() if t.lower() not in STYLE_TOKENS]
        if keep:
            variants.append(f"{family} {' '.join(keep)}")
    variants.append(family)
    if raw_family and raw_family != family:
        variants.append(raw_family)

    seen, out = set(), []
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _split_family_style(family, style):
    """Returns (family, style) fit for display and for CSS.

    Some OTFs (Stem, for one) report a PostScript-ish family of 'Stem-Bold'
    and a style PIL cannot read at all ('?'). Left alone that yields a CSS
    family Windows does not know, so the preview silently falls back to another
    typeface, and every face looks like weight 400.
    """
    style = (style or "").strip()
    style_ok = style and style != "?" and not style.startswith("?")
    if style_ok and "-" not in family:
        return family, style

    # Try to peel a style tail off the family name.
    for separator in ("-", " "):
        if separator in family:
            head, _, tail = family.rpartition(separator)
            tokens, leftover = _split_style_tokens(tail)
            if tokens and not leftover and head:
                return head, " ".join(TOKEN_LABELS[t] for t in tokens)

    if style_ok:
        return family, style
    return family, "Regular"


def _glyph_raster(font, ch):
    mask = font.getmask(ch)
    return bytes(mask) if mask.size != (0, 0) else b""


def _covers_cyrillic(font):
    """A face 'has' Cyrillic when its Cyrillic glyphs differ from .notdef."""
    try:
        notdef = _glyph_raster(font, "\uffff")
        return all(_glyph_raster(font, ch) != notdef for ch in CYRILLIC_PROBE)
    except Exception:
        return False


def _describe(path):
    try:
        font = ImageFont.truetype(path, 40)
        raw_family, raw_style = font.getname()
    except Exception:
        return None
    if not raw_family:
        return None

    family, style = _split_family_style(raw_family, raw_style)
    label = family if style.lower() in ("regular", "normal", "book") else f"{family} {style}"

    css_stack = _css_stack(family, style, raw_family)

    return {
        "path": path,
        "family": family,
        "style": style,
        "label": label,
        "css_family": family,
        "css_stack": css_stack,
        "css_weight": _css_weight(style),
        "css_italic": "italic" in style.lower() or "oblique" in style.lower(),
        "cyrillic": _covers_cyrillic(font),
        "source": "system",
    }


def _bundled():
    """Curated faces shipped with the app; these keep their @font-face names."""
    from renderer import BUNDLED_FONT_LABELS  # single source of truth for the UI
    out = []
    for value, meta in BUNDLED_FONT_LABELS.items():
        file_path = value.partition("#")[0]
        abs_path = os.path.join(BASE_DIR, file_path)
        if not os.path.exists(abs_path):
            continue
        out.append({
            "path": value,                      # keeps the #Variation suffix
            "family": meta["css_family"],
            "style": meta.get("style", ""),
            "label": meta["label"],
            "css_family": meta["css_family"],
            "css_stack": [meta["css_family"]],
            "css_weight": meta.get("css_weight", 400),
            "css_italic": False,
            "cyrillic": meta.get("cyrillic", True),
            "source": "bundled",
        })
    return out


def _signature():
    """Cheap fingerprint of the font folders, to know when to rescan."""
    parts = []
    for d in FONT_DIRS:
        if d and os.path.isdir(d):
            try:
                parts.append(f"{d}:{os.path.getmtime(d)}:{len(os.listdir(d))}")
            except OSError:
                continue
    return "|".join(parts)


def scan_system_fonts():
    seen = {}
    for directory in FONT_DIRS:
        if not directory or not os.path.isdir(directory):
            continue
        for ext in EXTENSIONS:
            for path in glob.glob(os.path.join(directory, "*" + ext)):
                info = _describe(path)
                if not info:
                    continue
                # One entry per family+style; first file found wins.
                key = (info["family"].lower(), info["style"].lower())
                seen.setdefault(key, info)
    return sorted(seen.values(), key=lambda f: (f["family"].lower(), f["css_weight"]))


def list_fonts(force_rescan=False):
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    signature = _signature()

    if not force_rescan and os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached.get("signature") == signature:
                return _bundled() + cached["system"]
        except Exception:
            pass

    system = scan_system_fonts()
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"signature": signature, "system": system}, f, ensure_ascii=False)
    except Exception:
        pass

    return _bundled() + system


if __name__ == "__main__":
    import time
    t0 = time.time()
    fonts = list_fonts(force_rescan=True)
    cyr = [f for f in fonts if f["cyrillic"]]
    print(f"{len(fonts)} faces ({len(cyr)} with Cyrillic) in {time.time()-t0:.1f}s")
    for f in fonts[:10]:
        print(f"  {f['label']:40} cyr={f['cyrillic']} w={f['css_weight']} {f['source']}")
