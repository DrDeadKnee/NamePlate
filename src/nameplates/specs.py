"""Plain data describing what to build. Nothing here touches CAD or mesh code."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class SpecError(ValueError):
    """A spec or config value is missing, malformed, or inconsistent."""


class Relief(StrEnum):
    RAISED = "raised"
    ENGRAVED = "engraved"


class Backing(StrEnum):
    BASE = "base"
    FLAT = "flat"


class BorderType(StrEnum):
    NONE = "none"
    RIM = "rim"


@dataclass(frozen=True)
class BorderSpec:
    border_type: BorderType = BorderType.NONE
    width: float = 0.4  # mm, measured in from the plate edge
    height: float | None = None  # mm above the plate face; None = same as the text relief depth

    def __post_init__(self):
        if self.width <= 0:
            raise SpecError(f"border width must be positive, got {self.width}")
        if self.height is not None and self.height <= 0:
            raise SpecError(f"border height must be positive, got {self.height}")

    @property
    def inset(self) -> float:
        """How much of the plate edge the border takes up."""
        return 0.0 if self.border_type is BorderType.NONE else self.width


@dataclass(frozen=True)
class PlateSpec:
    """One name plate. Sizes are mm; None for a size means "work it out"."""

    text: str
    font: str = "DejaVu Sans Bold"
    thickness: float = 1.5
    relief: Relief = Relief.RAISED
    relief_depth: float = 0.5
    width: float | None = None  # None = fit the text
    height: float | None = None  # None = the target surface's natural height
    font_size: float | None = None  # None = fill the plate height
    padding: float = 0.6  # clear space between the text and the plate edge or border
    border: BorderSpec = field(default_factory=BorderSpec)

    def __post_init__(self):
        if not self.text.strip():
            raise SpecError("plate text is empty")
        for name in ("thickness", "relief_depth"):
            if getattr(self, name) <= 0:
                raise SpecError(f"{name} must be positive, got {getattr(self, name)}")
        for name in ("width", "height", "font_size"):
            value = getattr(self, name)
            if value is not None and value <= 0:
                raise SpecError(f"{name} must be positive, got {value}")
        if self.padding < 0:
            raise SpecError(f"padding cannot be negative, got {self.padding}")
        if self.relief is Relief.ENGRAVED and self.relief_depth >= self.thickness:
            raise SpecError(
                f"engraving depth {self.relief_depth} would cut through a {self.thickness} mm plate"
            )


@dataclass(frozen=True)
class BaseSpec:
    """A miniature base: a slice of a cone, wider at the bottom."""

    height: float
    top_d: float
    bottom_d: float
    geometry: str = "round"
    model: str | None = None

    def __post_init__(self):
        for name in ("height", "top_d", "bottom_d"):
            if getattr(self, name) <= 0:
                raise SpecError(f"base {name} must be positive, got {getattr(self, name)}")


@dataclass(frozen=True)
class Job:
    """Everything one run needs: the target surface and the plates to make for it."""

    name: str
    backing: Backing
    plates: tuple[PlateSpec, ...]
    base: BaseSpec | None = None
    tolerance: float = 0.01  # fraction by which the plate back is straighter than the base
    mesh_deviation: float = 0.01  # mm, how far the mesh may stray from the true surface

    def __post_init__(self):
        if self.backing is Backing.BASE and self.base is None:
            raise SpecError("backing is 'base' but no base_type was given")
        if self.tolerance < 0:
            raise SpecError(f"tolerance cannot be negative, got {self.tolerance}")
        if self.mesh_deviation <= 0:
            raise SpecError(f"mesh_deviation must be positive, got {self.mesh_deviation}")
