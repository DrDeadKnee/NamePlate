"""The finished name plate and the pipeline that produces it."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import trimesh

from . import builder, meshing
from .fonts import FONT_DIRS, find_font
from .specs import PlateSpec
from .surfaces import FrustumSurface, Surface


class BuildError(RuntimeError):
    """The geometry came out unusable."""


@dataclass(frozen=True)
class Nameplate:
    """A built plate: what was asked for, where it goes, and the resulting mesh."""

    spec: PlateSpec
    surface: Surface
    mesh: trimesh.Trimesh
    width: float  # mm, across the plate before bending
    height: float  # mm, up the plate
    font_size: float
    warnings: tuple[str, ...] = ()

    def export_stl(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.mesh.export(path)
        return path

    def summary(self) -> str:
        text = f"{self.width:.1f} x {self.height:.1f} mm, font size {self.font_size:.2f}"
        if isinstance(self.surface, FrustumSurface):
            text += f", wraps {math.degrees(self.surface.arc_angle(self.width)):.0f} deg"
        return text


def build_nameplate(
    spec: PlateSpec, surface: Surface, *, mesh_deviation: float = 0.01, font_dirs=FONT_DIRS
) -> Nameplate:
    font_path = find_font(spec.font, font_dirs)
    layout = builder.fit_layout(spec, builder.measure_text(spec.text, font_path), surface.default_height())
    if isinstance(surface, FrustumSurface) and surface.arc_angle(layout.width) >= 2 * math.pi:
        raise BuildError(f"a {layout.width:.1f} mm plate wraps more than once around the base")

    flat = meshing.tessellate(builder.build_flat(spec, font_path, layout), mesh_deviation)
    vertices, faces = meshing.refine(flat.vertices, flat.faces, surface.max_step(mesh_deviation))
    mesh = trimesh.Trimesh(surface.map(vertices), faces, process=False)
    if not mesh.is_watertight:
        raise BuildError(f"mesh for {spec.text!r} is not watertight; the font may have overlapping outlines")
    return Nameplate(spec, surface, mesh, layout.width, layout.height, layout.font_size, layout.warnings)
