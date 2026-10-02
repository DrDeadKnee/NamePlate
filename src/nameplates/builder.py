"""Builds the flat plate solid: body, text and border, in plate coordinates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from build123d import Align, Box, Pos, Text, TextAlign, extrude

from .specs import BorderType, PlateSpec, Relief, SpecError

_REFERENCE_FONT_SIZE = 10.0
_BOTTOM = (Align.CENTER, Align.CENTER, Align.MIN)


@dataclass(frozen=True)
class TextMetrics:
    """Extents of a string's ink per unit of font size, from the left end of its baseline."""

    left: float
    right: float
    bottom: float  # negative when glyphs descend below the baseline
    top: float
    cap_height: float


@dataclass(frozen=True)
class Layout:
    """Resolved sizes for one plate, in mm."""

    width: float
    height: float
    font_size: float
    text_origin: tuple[float, float]  # left end of the baseline, in plate (u, v)
    warnings: tuple[str, ...] = ()


def _text_sketch(text: str, font_path: Path, font_size: float):
    # With this alignment the sketch origin is the left end of the baseline.
    return Text(text, font_size, font_path=str(font_path), text_align=(TextAlign.LEFT, TextAlign.BOTTOM))


def measure_text(text: str, font_path: Path) -> TextMetrics:
    ink = _text_sketch(text, font_path, _REFERENCE_FONT_SIZE).bounding_box()
    if ink.size.X <= 0 or ink.size.Y <= 0:
        raise SpecError(f"text {text!r} has no visible glyphs in {font_path.name}")
    cap_top = _text_sketch("H", font_path, _REFERENCE_FONT_SIZE).bounding_box().max.Y
    if cap_top <= 0:  # no usable H in this font; size by the text's own height instead
        cap_top = ink.max.Y
    values = (ink.min.X, ink.max.X, ink.min.Y, ink.max.Y, cap_top)
    return TextMetrics(*(value / _REFERENCE_FONT_SIZE for value in values))


def fit_layout(spec: PlateSpec, metrics: TextMetrics, default_height: float | None) -> Layout:
    """Work out the plate size, font size and text position.

    Capital letters fill the plate height between the margins unless a font size
    is given, so every plate of the same height gets the same lettering whatever
    its text. Descenders may dip into the padding. The font is only shrunk when
    glyphs would otherwise leave the plate face or overrun an explicit width.
    """
    height = spec.height if spec.height is not None else default_height
    if height is None:
        raise SpecError("a flat plate needs an explicit height")
    edge = spec.border.inset
    margin = spec.padding + edge
    room_up = height - 2 * margin
    if room_up <= 0:
        raise SpecError(f"a {height:.2f} mm tall plate has no room for text inside {margin:.2f} mm margins")

    warnings = []
    font_size = room_up / metrics.cap_height
    if spec.font_size is not None:
        if spec.font_size > font_size * (1 + 1e-9):
            warnings.append(f"font size {spec.font_size:g} is too tall for the plate; shrunk to {font_size:.2f}")
        else:
            font_size = spec.font_size

    # The capitals are centred on the plate; the tallest and deepest glyphs must stay on its face.
    reach = max(metrics.cap_height / 2 - metrics.bottom, metrics.top - metrics.cap_height / 2)
    limit = (height / 2 - edge) / reach
    if font_size > limit * (1 + 1e-9):
        font_size = limit
        warnings.append(f"glyphs reach past the plate face; font size shrunk to {font_size:.2f}")

    ink_width = metrics.right - metrics.left
    if spec.width is None:
        width = font_size * ink_width + 2 * margin
    else:
        width = spec.width
        room_across = width - 2 * margin
        if room_across <= 0:
            raise SpecError(f"a {width:.2f} mm wide plate has no room for text inside {margin:.2f} mm margins")
        if font_size * ink_width > room_across * (1 + 1e-9):
            font_size = room_across / ink_width
            warnings.append(f"text is too long for a {width:g} mm plate; font size shrunk to {font_size:.2f}")

    origin = (
        -font_size * (metrics.left + metrics.right) / 2,
        (height - font_size * metrics.cap_height) / 2,
    )
    return Layout(width, height, font_size, origin, tuple(warnings))


def _rim(spec: PlateSpec, layout: Layout):
    height = spec.border.height if spec.border.height is not None else spec.relief_depth
    inner_width = layout.width - 2 * spec.border.width
    inner_height = layout.height - 2 * spec.border.width
    if inner_width <= 0 or inner_height <= 0:
        raise SpecError(f"a {spec.border.width} mm border leaves nothing of the plate face")
    outer = Box(layout.width, layout.height, height, align=_BOTTOM)
    inner = Box(inner_width, inner_height, height, align=_BOTTOM)
    return Pos(0, layout.height / 2, spec.thickness) * (outer - inner)


# Border builders take (spec, layout) and return a solid to fuse onto the plate.
BORDERS = {
    BorderType.RIM: _rim,
}


def build_flat(spec: PlateSpec, font_path: Path, layout: Layout):
    """The plate as a solid: u across (centred), v up from 0, w out from the back at 0."""
    plate = Pos(0, layout.height / 2, 0) * Box(layout.width, layout.height, spec.thickness, align=_BOTTOM)

    letters = extrude(_text_sketch(spec.text, font_path, layout.font_size), spec.relief_depth)
    if spec.relief is Relief.RAISED:
        plate += Pos(*layout.text_origin, spec.thickness) * letters
    else:
        plate -= Pos(*layout.text_origin, spec.thickness - spec.relief_depth) * letters

    if spec.border.border_type is not BorderType.NONE:
        plate += BORDERS[spec.border.border_type](spec, layout)
    return plate
