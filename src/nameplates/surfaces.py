"""Target surfaces a plate can be fitted to.

Every plate is designed flat, in plate coordinates:

    u  across the plate, 0 at its centre
    v  up the plate, 0 at its bottom edge
    w  out from the back of the plate, 0 where it touches the target

A surface maps those points into 3D. To support a new kind of target (a scanned
mesh, a height map, ...) implement the Surface protocol; nothing else changes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from .specs import Backing, Job, SpecError

NO_LIMIT = np.full(3, np.inf)


class Surface(Protocol):
    def default_height(self) -> float | None:
        """Plate height that suits this surface, or None if it has no opinion."""

    def max_step(self, deviation: float) -> np.ndarray:
        """Longest (u, v, w) extent a mesh edge may have so that, once mapped, it stays
        within `deviation` mm of the true surface. inf where the map is linear."""

    def map(self, points: np.ndarray) -> np.ndarray:
        """Map (n, 3) plate coordinates to (n, 3) model coordinates."""


@dataclass(frozen=True)
class FlatSurface:
    def default_height(self) -> float | None:
        return None

    def max_step(self, deviation: float) -> np.ndarray:
        return NO_LIMIT

    def map(self, points: np.ndarray) -> np.ndarray:
        return np.asarray(points, dtype=float)


@dataclass(frozen=True)
class FrustumSurface:
    """The side wall of a cone slice, e.g. a round miniature base standing on z = 0.

    `tolerance` scales both radii up, so the plate back is slightly straighter than
    the wall it sits against. The plate is centred on the -Y side of the base.
    Widths are true arc lengths on the plate back half way up the wall, which keeps
    lines of text level.
    """

    bottom_d: float
    top_d: float
    height: float
    tolerance: float = 0.0

    @property
    def _radii(self) -> tuple[float, float]:
        scale = (1 + self.tolerance) / 2
        return self.bottom_d * scale, self.top_d * scale

    @property
    def slant(self) -> float:
        bottom_r, top_r = self._radii
        return math.hypot(self.height, bottom_r - top_r)

    @property
    def reference_radius(self) -> float:
        return sum(self._radii) / 2

    def arc_angle(self, width: float) -> float:
        """Angle in radians that a plate of the given width wraps around the base."""
        return width / self.reference_radius

    def default_height(self) -> float | None:
        return self.slant

    def max_step(self, deviation: float) -> np.ndarray:
        # A chord across an arc of radius r strays e^2 / 8r from it.
        return np.array([math.sqrt(8 * deviation * self.reference_radius), np.inf, np.inf])

    def map(self, points: np.ndarray) -> np.ndarray:
        bottom_r, top_r = self._radii
        u, v, w = np.asarray(points, dtype=float).T
        # In the (radius, z) plane: `up` runs along the wall, `out` is its outward normal.
        up = np.array([top_r - bottom_r, self.height]) / self.slant
        out = np.array([up[1], -up[0]])
        radius = bottom_r + v * up[0] + w * out[0]
        z = v * up[1] + w * out[1]
        angle = u / self.reference_radius
        return np.column_stack([radius * np.sin(angle), -radius * np.cos(angle), z])


def surface_for(job: Job) -> Surface:
    if job.backing is Backing.FLAT:
        return FlatSurface()
    base = job.base
    if base.geometry != "round":
        raise SpecError(f"{base.geometry} bases are not supported yet, only round")
    return FrustumSurface(base.bottom_d, base.top_d, base.height, job.tolerance)
