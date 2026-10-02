import math

import numpy as np
import pytest
import trimesh

from nameplates.meshing import refine
from nameplates.surfaces import FlatSurface, FrustumSurface

GW40 = dict(bottom_d=39, top_d=37, height=4.5)


def test_plate_back_lies_on_the_toleranced_cone():
    surface = FrustumSurface(**GW40, tolerance=0.01)
    rng = np.random.default_rng(0)
    back = np.column_stack([rng.uniform(-20, 20, 200), rng.uniform(0, surface.slant, 200), np.zeros(200)])
    x, y, z = surface.map(back).T
    expected_radius = 1.01 * (19.5 - z / 4.5)  # the wall narrows 1 mm in radius over its 4.5 mm height
    assert np.allclose(np.hypot(x, y), expected_radius)
    assert z.min() >= 0 and z.max() <= 4.5


def test_plate_sits_centred_on_the_front_of_the_base_and_reads_left_to_right():
    surface = FrustumSurface(**GW40)
    centre, right, front = surface.map(np.array([[0, 0, 0], [1, 0, 0], [0, 0, 1]]))
    assert np.allclose(centre, [0, -19.5, 0])
    assert right[0] > centre[0]  # +u runs to the viewer's right when looking at the base from -Y
    assert np.linalg.norm(front[:2]) > np.linalg.norm(centre[:2])  # +w points away from the base
    assert math.isclose(np.linalg.norm(front - centre), 1)


def test_default_height_is_the_wall_slant_and_width_is_arc_length():
    surface = FrustumSurface(**GW40)
    assert math.isclose(surface.default_height(), math.hypot(4.5, 1))
    assert math.isclose(surface.arc_angle(math.pi * 19), math.pi)  # half way round at the mean radius


def test_flat_surface_leaves_points_alone_and_needs_no_refinement():
    points = np.arange(12, dtype=float).reshape(4, 3)
    assert np.array_equal(FlatSurface().map(points), points)
    assert not np.isfinite(FlatSurface().max_step(0.01)).any()


@pytest.mark.parametrize("step", [(0.7, np.inf, np.inf), (1.5, 0.4, np.inf), (0.3, 0.3, 0.3)])
def test_refine_keeps_mesh_watertight_and_within_step(step):
    box = trimesh.creation.box(extents=(10, 4, 2))
    vertices, faces = refine(box.vertices, box.faces, np.array(step))
    mesh = trimesh.Trimesh(vertices, faces, process=False)
    assert mesh.is_watertight and mesh.is_winding_consistent
    assert math.isclose(mesh.volume, 80)
    extents = np.abs(vertices[mesh.edges[:, 0]] - vertices[mesh.edges[:, 1]]).max(axis=0)
    assert (extents <= np.array(step) + 1e-9).all()


def test_refine_does_nothing_without_a_limit():
    box = trimesh.creation.box(extents=(10, 4, 2))
    vertices, faces = refine(box.vertices, box.faces, np.full(3, np.inf))
    assert len(vertices) == len(box.vertices) and len(faces) == len(box.faces)


def test_bent_mesh_stays_within_the_deviation():
    surface = FrustumSurface(**GW40)
    deviation = 0.01
    box = trimesh.creation.box(extents=(30, 4, 1.5))
    box.apply_translation((0, 2, 0.75))
    vertices, faces = refine(box.vertices, box.faces, surface.max_step(deviation))
    mesh = trimesh.Trimesh(vertices, faces, process=False)
    # A straight edge cuts inside the curve it stands for, most of all at its midpoint.
    ends = vertices[mesh.edges_unique]
    chord_mid = surface.map(ends[:, 0]) / 2 + surface.map(ends[:, 1]) / 2
    true_mid = surface.map(ends.mean(axis=1))
    sag = np.hypot(*true_mid.T[:2]) - np.hypot(*chord_mid.T[:2])
    # The limit is set at the plate back; the front face is at a slightly larger radius.
    assert 0.5 * deviation < sag.max() <= deviation * 1.15
