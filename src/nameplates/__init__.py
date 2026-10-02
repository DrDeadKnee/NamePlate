"""Generate 3D-printable name plates for miniature bases."""

from .config import load_job
from .plate import BuildError, Nameplate, build_nameplate
from .specs import Backing, BaseSpec, BorderSpec, BorderType, Job, PlateSpec, Relief, SpecError
from .surfaces import FlatSurface, FrustumSurface, Surface, surface_for

__all__ = [
    "Backing",
    "BaseSpec",
    "BorderSpec",
    "BorderType",
    "BuildError",
    "FlatSurface",
    "FrustumSurface",
    "Job",
    "Nameplate",
    "PlateSpec",
    "Relief",
    "SpecError",
    "Surface",
    "build_nameplate",
    "load_job",
    "surface_for",
]
