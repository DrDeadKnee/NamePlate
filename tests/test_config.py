import pytest

from nameplates.config import job_from_dict, load_job, merge
from nameplates.specs import Backing, BorderType, Relief, SpecError


def test_built_in_defaults_apply_when_only_text_is_given():
    job = job_from_dict({"base_type": {"model": "gw-40mm"}, "plate_specs": {"text": "BOB"}})
    (plate,) = job.plates
    assert job.backing is Backing.BASE
    assert job.tolerance == 0.01
    assert plate.relief is Relief.RAISED
    assert plate.width is None and plate.height is None
    assert plate.border.border_type is BorderType.NONE


def test_catalog_supplies_base_dimensions_and_explicit_values_override():
    job = job_from_dict({"base_type": {"model": "gw-40mm", "height": 5}, "plate_specs": {"text": "BOB"}})
    assert (job.base.bottom_d, job.base.top_d, job.base.height) == (39, 37, 5)


def test_unknown_base_model_needs_dimensions():
    with pytest.raises(SpecError, match="not in the catalog"):
        job_from_dict({"base_type": {"model": "acme-99mm"}, "plate_specs": {"text": "BOB"}})
    job = job_from_dict(
        {"base_type": {"model": "acme-99mm", "height": 3, "top_d": 97, "bottom_d": 99}, "plate_specs": {"text": "BOB"}}
    )
    assert job.base.bottom_d == 99


def test_naming_a_model_discards_dimensions_from_lower_layers():
    defaults = {"base_type": {"model": "gw-40mm", "height": 4.5, "top_d": 37, "bottom_d": 39}}
    merged = merge(defaults, {"base_type": {"model": "acme-99mm"}})
    assert merged["base_type"] == {"model": "acme-99mm"}
    # Without a model, explicit values still layer over the lower layer.
    assert merge(defaults, {"base_type": {"height": 5}})["base_type"]["top_d"] == 37


def test_names_share_plate_specs_and_may_override_them():
    job = job_from_dict(
        {
            "base_type": {"model": "gw-40mm"},
            "plate_specs": {"text": "IGNORED", "thickness": 2, "border": {"border_type": "rim"}},
            "names": ["ANN", {"text": "BOB", "relief": "engraved", "border": {"width": 0.5}}, 99],
        }
    )
    ann, bob, number = job.plates
    assert (ann.text, bob.text, number.text) == ("ANN", "BOB", "99")
    assert ann.thickness == bob.thickness == 2
    assert ann.relief is Relief.RAISED and bob.relief is Relief.ENGRAVED
    assert bob.border.border_type is BorderType.RIM and bob.border.width == 0.5


def test_fit_and_blank_sizes_mean_automatic():
    job = job_from_dict(
        {"backing": "flat", "plate_specs": {"text": "BOB", "width": "fit", "height": 8, "border": {"border_type": None}}}
    )
    (plate,) = job.plates
    assert plate.width is None and plate.height == 8
    assert job.base is None


@pytest.mark.parametrize(
    "data, message",
    [
        ({"plate_specs": {"text": "BOB", "colour": "red"}}, "unknown plate_specs"),
        ({"plate_specs": {"text": "BOB"}, "basetype": {}}, "unknown top-level"),
        ({"plate_specs": {"text": "BOB", "relief": "sideways"}}, "relief must be one of"),
        ({"plate_specs": {"text": "BOB", "thickness": "thick"}}, "must be a number"),
        ({"plate_specs": {"font": "DejaVu Sans"}}, "no text given"),
        ({"plate_specs": {"text": "BOB"}, "names": []}, "non-empty list"),
        ({"plate_specs": {"text": "BOB", "relief": "engraved", "relief_depth": 2}}, "cut through"),
        ({"plate_specs": {"text": "BOB"}}, "needs a model"),
    ],
)
def test_bad_configs_are_rejected(data, message):
    with pytest.raises(SpecError, match=message):
        job_from_dict(data)


def test_load_job_layers_defaults_job_file_and_overrides(tmp_path):
    defaults = tmp_path / "default.yml"
    defaults.write_text("base_type: {model: gw-40mm}\nplate_specs: {text: DEFAULT, thickness: 2, padding: 1}\n")
    job_file = tmp_path / "job.yml"
    job_file.write_text("name: team\nplate_specs: {padding: 0.5}\nnames: [ANN, BOB]\n")

    job = load_job(job_file, defaults=defaults)
    assert job.name == "team"
    assert [plate.text for plate in job.plates] == ["ANN", "BOB"]
    assert all(plate.thickness == 2 and plate.padding == 0.5 for plate in job.plates)

    single = load_job(job_file, defaults=defaults, overrides={"names": None, "plate_specs": {"text": "CAT"}})
    assert [plate.text for plate in single.plates] == ["CAT"]


def test_missing_job_file_is_reported(tmp_path):
    with pytest.raises(SpecError, match="cannot read"):
        load_job(tmp_path / "nope.yml", defaults=None)
