"""Turning a flat solid into a triangle mesh fine enough to bend."""

from __future__ import annotations

import numpy as np
import trimesh


def tessellate(solid, deviation: float) -> trimesh.Trimesh:
    """Triangulate a build123d shape, welding the per-face vertices OCCT hands back."""
    vertices, triangles = solid.tessellate(deviation)
    points = np.array([(p.X, p.Y, p.Z) for p in vertices])
    return trimesh.Trimesh(points, np.array(triangles), process=True)


def refine(vertices: np.ndarray, faces: np.ndarray, max_step: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Split every edge whose extent along some axis exceeds `max_step` for that axis.

    Both faces sharing an edge get the same midpoint vertex, so a watertight mesh
    stays watertight however unevenly it is refined.
    """
    vertices = np.asarray(vertices, dtype=float)
    faces = np.asarray(faces, dtype=np.int64)
    max_step = np.asarray(max_step, dtype=float)
    if not np.isfinite(max_step).any():
        return vertices, faces

    while True:
        corners = vertices[faces]
        # Edge k of a face runs from corner k to corner k + 1.
        too_long = (np.abs(np.roll(corners, -1, axis=1) - corners) > max_step).any(axis=2)
        count = too_long.sum(axis=1)
        if not count.any():
            return vertices, faces

        # Rotate each face so its long edges come first: one long edge becomes edge 0,
        # two become edges 0 and 1.
        one, two, three = count == 1, count == 2, count == 3
        start = np.zeros(len(faces), dtype=np.int64)
        start[one] = too_long[one].argmax(axis=1)
        start[two] = (too_long[two].argmin(axis=1) + 1) % 3
        order = (start[:, None] + np.arange(3)) % 3
        faces = np.take_along_axis(faces, order, axis=1)
        too_long = np.take_along_axis(too_long, order, axis=1)

        # One new vertex per long edge, keyed by its sorted endpoints.
        ends = np.sort(np.stack([faces, np.roll(faces, -1, axis=1)], axis=2), axis=2)
        keys = ends[..., 0] * len(vertices) + ends[..., 1]
        unique_keys, inverse = np.unique(keys[too_long], return_inverse=True)
        midpoint = np.full(keys.shape, -1, dtype=np.int64)
        midpoint[too_long] = len(vertices) + inverse
        low, high = np.divmod(unique_keys, len(vertices))
        vertices = np.vstack([vertices, (vertices[low] + vertices[high]) / 2])

        a, b, c = faces.T
        ab, bc, ca = midpoint.T
        pieces = [faces[count == 0]]
        for mask, triangles in (
            (one, [(a, ab, c), (ab, b, c)]),
            (two, [(ab, b, bc), (a, ab, bc), (a, bc, c)]),
            (three, [(a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)]),
        ):
            pieces += [np.column_stack([corner[mask] for corner in tri]) for tri in triangles]
        faces = np.vstack(pieces)
