import dataclasses
import math

import pytest
import trimesh

from nameplates import cli
from nameplates.builder import TextMetrics, fit_layout
from nameplates.fonts import find_font
from nameplates.plate import build_nameplate
from nameplates.specs import BorderSpec, BorderType, PlateSpec, Relief, SpecError
from nameplates.surfaces import FlatSurface, FrustumSurface

GW40 = FrustumSurface(bottom_d=39, top_d=37, height=4.5, tolerance=0.01)
# Caps-only text 5 units wide per unit of font size, and the same with a descender.
CAPS = TextMetrics(left=0.1, right=5.1, bottom=0.0, top=0.7, cap_height=0.7)
DESCENDING = dataclasses.replace(CAPS, bottom=-0.25)


def test_capitals_fill_the_height_and_width_follows_the_text():
    layout = fit_layout(PlateSpec("BOB", padding=0.5), CAPS, default_height=4.5)
    assert math.isclose(layout.font_size, 3.5 / 0.7)
    assert math.isclose(layout.width, 5 * layout.font_size + 1)
    assert not layout.warnings
    # Ink is centred across the plate and the baseline sits on the bottom padding.
    assert math.isclose(layout.text_origin[0] + layout.font_size * 0.1, -(layout.width - 1) / 2)
    assert math.isclose(layout.text_origin[1], 0.5)


def test_descenders_use_the_padding_without_changing_the_font_size():
    plain = fit_layout(PlateSpec("BOB", padding=1.5), CAPS, default_height=6)
    descending = fit_layout(PlateSpec("Bog", padding=1.5), DESCENDING, default_height=6)
    assert math.isclose(plain.font_size, descending.font_size)
    assert plain.text_origin[1] == descending.text_origin[1]
    assert not descending.warnings


def test_font_shrinks_when_glyphs_would_leave_the_plate():
    layout = fit_layout(PlateSpec("Bog", padding=0.2), DESCENDING, default_height=4.5)
    assert layout.warnings
    assert math.isclose(layout.text_origin[1] + layout.font_size * DESCENDING.bottom, 0, abs_tol=1e-9)


def test_exact_width_is_kept_and_long_text_shrinks_to_fit():
    roomy = fit_layout(PlateSpec("BOB", width=40, padding=0.5), CAPS, default_height=4.5)
    assert roomy.width == 40 and not roomy.warnings and math.isclose(roomy.font_size, 5)
    tight = fit_layout(PlateSpec("BOB", width=11, padding=0.5), CAPS, default_height=4.5)
    assert tight.width == 11 and tight.warnings and math.isclose(tight.font_size, 2)


def test_explicit_font_size_and_height():
    layout = fit_layout(PlateSpec("BOB", font_size=2, height=8), CAPS, default_height=4.5)
    assert layout.height == 8 and layout.font_size == 2
    assert math.isclose(layout.text_origin[1], (8 - 2 * 0.7) / 2)  # capitals centred up the plate
    too_big = fit_layout(PlateSpec("BOB", font_size=50, height=8), CAPS, default_height=4.5)
    assert too_big.warnings and too_big.font_size < 50


def test_layout_errors():
    with pytest.raises(SpecError, match="explicit height"):
        fit_layout(PlateSpec("BOB"), CAPS, default_height=None)
    with pytest.raises(SpecError, match="no room"):
        fit_layout(PlateSpec("BOB", padding=3), CAPS, default_height=4.5)


def test_font_lookup_by_name_path_and_miss(tmp_path):
    (tmp_path / "Fancy-Bold.ttf").touch()
    assert find_font("fancy bold", [tmp_path]) == tmp_path / "Fancy-Bold.ttf"
    assert find_font(str(tmp_path / "Fancy-Bold.ttf"), []) == tmp_path / "Fancy-Bold.ttf"
    with pytest.raises(SpecError, match="Closest: Fancy-Bold.ttf"):
        find_font("Fancy Bald", [tmp_path])


def test_curved_plate_is_printable_and_hugs_the_base():
    plate = build_nameplate(PlateSpec("AB 12"), GW40)
    assert plate.mesh.is_watertight and plate.mesh.is_winding_consistent and plate.mesh.volume > 0
    assert math.isclose(plate.height, GW40.slant)
    x, y, z = plate.mesh.vertices.T
    radius_at_wall = 1.01 * (19.5 - z / 4.5)
    assert ((x**2 + y**2) ** 0.5 >= radius_at_wall - 1e-6).all()  # nothing cuts into the base
    assert math.isclose(z.min(), 0, abs_tol=1e-9)
    assert y.max() < 0  # sits on the -Y side


def test_flat_plate_has_the_requested_size():
    plate = build_nameplate(PlateSpec("AB", width=20, height=8), FlatSurface())
    assert plate.mesh.is_watertight
    assert plate.mesh.extents == pytest.approx([20, 8, 2.0])  # 1.5 thick + 0.5 raised text


def test_relief_and_border_change_the_solid_as_expected():
    size = dict(width=20, height=8)
    blank_volume = 20 * 8 * 1.5
    raised = build_nameplate(PlateSpec("AB", **size), FlatSurface())
    engraved = build_nameplate(PlateSpec("AB", relief=Relief.ENGRAVED, **size), FlatSurface())
    rimmed = build_nameplate(PlateSpec("AB", border=BorderSpec(BorderType.RIM, width=0.5), **size), FlatSurface())

    ink = raised.mesh.volume - blank_volume
    assert ink > 0
    assert engraved.mesh.extents[2] == pytest.approx(1.5)
    # Same lettering either way, so engraving removes what raising adds.
    assert blank_volume - engraved.mesh.volume == pytest.approx(ink, rel=1e-3)
    rim_volume = (20 * 8 - 19 * 7) * 0.5
    assert rimmed.mesh.is_watertight
    assert rimmed.mesh.volume > blank_volume + rim_volume  # rim plus (smaller) lettering


def test_cli_batch_writes_one_stl_per_name(tmp_path, capsys):
    job = tmp_path / "job.yml"
    job.write_text("name: Test Team\nbase_type: {model: gw-40mm}\nnames: [AB, CD, AB]\n")
    out = tmp_path / "out"
    assert cli.main(["batch", str(job), "-o", str(out), "--defaults", str(job)]) == 0
    assert sorted(path.name for path in out.iterdir()) == ["ab-2.stl", "ab.stl", "cd.stl"]
    assert trimesh.load(out / "cd.stl").is_watertight
    assert "wraps" in capsys.readouterr().out


def test_cli_single_overrides_and_failures(tmp_path, capsys):
    config = tmp_path / "config.yml"
    config.write_text("base_type: {model: gw-40mm}\nnames: [AB, CD]\n")
    target = tmp_path / "one.stl"
    common = [str(config), "--defaults", str(config)]

    assert cli.main(["single", *common]) == 1
    assert "use `nameplates batch`" in capsys.readouterr().err
    assert cli.main(["single", *common, "--text", "EF", "--font", "No Such Font", "-o", str(target)]) == 1
    assert "not found" in capsys.readouterr().err and not target.exists()
    assert cli.main(["single", *common, "--text", "EF", "--relief", "engraved", "-o", str(target)]) == 0
    assert trimesh.load(target).is_watertight
