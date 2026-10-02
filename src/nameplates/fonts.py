"""Font lookup: turn a name like "DejaVu Sans Bold" into a font file."""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from .specs import SpecError

# Searched in order; the project's own fonts/ directory wins.
FONT_DIRS = (
    Path("fonts"),
    Path.home() / ".fonts",
    Path.home() / ".local/share/fonts",
    Path("/usr/local/share/fonts"),
    Path("/usr/share/fonts"),
)
FONT_SUFFIXES = {".ttf", ".otf"}


def _normalise(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def available_fonts(font_dirs=FONT_DIRS) -> dict[str, Path]:
    """Normalised file stem -> path, for every font file under the search directories."""
    found: dict[str, Path] = {}
    for directory in font_dirs:
        if not Path(directory).is_dir():
            continue
        for path in sorted(Path(directory).rglob("*")):
            if path.suffix.lower() in FONT_SUFFIXES:
                found.setdefault(_normalise(path.stem), path)
    return found


def find_font(name: str, font_dirs=FONT_DIRS) -> Path:
    """Resolve a font by file path, or by name matched against font file names.

    "DejaVu Sans Bold" matches DejaVuSans-Bold.ttf: case, spaces and punctuation
    are ignored.
    """
    as_path = Path(name).expanduser()
    if as_path.suffix.lower() in FONT_SUFFIXES and as_path.is_file():
        return as_path
    fonts = available_fonts(font_dirs)
    match = fonts.get(_normalise(name))
    if match is None:
        close = difflib.get_close_matches(_normalise(name), fonts, n=3)
        hint = f" Closest: {', '.join(fonts[key].name for key in close)}." if close else ""
        raise SpecError(f"font {name!r} not found; add its .ttf or .otf file to fonts/.{hint}")
    return match
