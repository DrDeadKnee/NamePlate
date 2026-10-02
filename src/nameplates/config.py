"""Reads YAML configs into specs.

Settings are layered, later layers winning: built-in defaults, the defaults file
(configs/default.yml), the job file, then any overrides such as CLI flags. In a
batch job, each entry under `names` is layered over the shared `plate_specs`.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import yaml

from .specs import Backing, BaseSpec, BorderSpec, BorderType, Job, PlateSpec, Relief, SpecError

DEFAULTS_PATH = Path("configs/default.yml")

_JOB_KEYS = {"name", "backing", "tolerance", "mesh_deviation", "base_type", "plate_specs", "names"}
_BASE_KEYS = {"model", "geometry", "height", "top_d", "bottom_d"}
_PLATE_KEYS = {
    "text", "font", "thickness", "relief", "relief_depth", "width", "height", "font_size", "padding", "border",
}
_BORDER_KEYS = {"border_type", "width", "height"}
_BASE_GEOMETRIES = {"round", "square", "ellipse"}


def load_yaml(path: str | Path) -> dict:
    try:
        with open(path) as handle:
            data = yaml.safe_load(handle)
    except OSError as error:
        raise SpecError(f"cannot read {path}: {error.strerror}") from error
    except yaml.YAMLError as error:
        raise SpecError(f"{path} is not valid YAML: {error}") from error
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise SpecError(f"{path} must contain a mapping at the top level")
    return data


def base_catalog() -> dict:
    return yaml.safe_load(resources.files("nameplates").joinpath("data/bases.yml").read_text())


def merge(base: dict, overlay: dict) -> dict:
    """Layer `overlay` over `base`, merging nested mappings key by key.

    A layer that names a base model replaces the whole base_type, so dimensions
    left over from a lower layer cannot override the new model's lookup.
    """
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            if key == "base_type" and value.get("model") is not None:
                merged[key] = dict(value)
            else:
                merged[key] = merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _check_keys(data: dict, allowed: set[str], where: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise SpecError(f"unknown {where} setting(s): {', '.join(unknown)}")


def _mapping(value, where: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SpecError(f"{where} must be a mapping")
    return value


def _number(value, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SpecError(f"{where} must be a number, got {value!r}")
    return float(value)


def _size(value, where: str) -> float | None:
    """A size in mm, or None when it is left out or set to "fit"."""
    if value is None or value == "fit":
        return None
    return _number(value, where)


def _choice(enum, value, where: str):
    try:
        return enum(value)
    except ValueError:
        options = ", ".join(member.value for member in enum)
        raise SpecError(f"{where} must be one of {options}; got {value!r}") from None


def _present(data: dict) -> dict:
    """Drop keys left blank in the YAML so the spec's own defaults apply."""
    return {key: value for key, value in data.items() if value is not None}


def border_spec(data) -> BorderSpec:
    data = _present(_mapping(data, "border"))
    _check_keys(data, _BORDER_KEYS, "border")
    fields = {}
    if "border_type" in data:
        fields["border_type"] = _choice(BorderType, data["border_type"], "border_type")
    if "width" in data:
        fields["width"] = _number(data["width"], "border width")
    if "height" in data:
        fields["height"] = _number(data["height"], "border height")
    return BorderSpec(**fields)


def plate_spec(data: dict) -> PlateSpec:
    data = dict(data)
    _check_keys(data, _PLATE_KEYS, "plate_specs")
    border = border_spec(data.pop("border", None))
    sizes = {key: _size(data.pop(key, None), key) for key in ("width", "height", "font_size")}
    data = _present(data)
    if "text" not in data:
        raise SpecError("no text given: set plate_specs.text, list names, or pass --text")
    fields = {"text": str(data["text"])}
    if "font" in data:
        fields["font"] = str(data["font"])
    if "relief" in data:
        fields["relief"] = _choice(Relief, data["relief"], "relief")
    for key in ("thickness", "relief_depth", "padding"):
        if key in data:
            fields[key] = _number(data[key], key)
    return PlateSpec(border=border, **sizes, **fields)


def base_spec(data) -> BaseSpec:
    """Catalog dimensions for the model, with any explicit values taking precedence."""
    data = _present(_mapping(data, "base_type"))
    _check_keys(data, _BASE_KEYS, "base_type")
    model = data.get("model")
    fields = {**base_catalog().get(model, {}), **data}
    missing = [key for key in ("height", "top_d", "bottom_d") if key not in fields]
    if missing:
        if model is not None and model not in base_catalog():
            raise SpecError(f"base model {model!r} is not in the catalog; give {', '.join(missing)} explicitly")
        raise SpecError(f"base_type needs a model or {', '.join(missing)}")
    geometry = fields.get("geometry", "round")
    if geometry not in _BASE_GEOMETRIES:
        raise SpecError(f"base geometry must be one of {', '.join(sorted(_BASE_GEOMETRIES))}; got {geometry!r}")
    return BaseSpec(
        height=_number(fields["height"], "base height"),
        top_d=_number(fields["top_d"], "base top_d"),
        bottom_d=_number(fields["bottom_d"], "base bottom_d"),
        geometry=geometry,
        model=model,
    )


def _plates(shared: dict, names) -> tuple[PlateSpec, ...]:
    if names is None:
        return (plate_spec(shared),)
    if not isinstance(names, list) or not names:
        raise SpecError("names must be a non-empty list")
    plates = []
    for entry in names:
        # An entry is just the text, or a mapping of plate settings for that one plate.
        own = entry if isinstance(entry, dict) else {"text": entry}
        if own.get("text") is None:
            raise SpecError(f"names entry {entry!r} has no text")
        plates.append(plate_spec(merge(shared, own)))
    return tuple(plates)


def job_from_dict(data: dict) -> Job:
    _check_keys(data, _JOB_KEYS, "top-level")
    backing = _choice(Backing, data.get("backing") or Backing.BASE, "backing")
    fields = {}
    for key in ("tolerance", "mesh_deviation"):
        if data.get(key) is not None:
            fields[key] = _number(data[key], key)
    return Job(
        name=str(data.get("name") or "nameplates"),
        backing=backing,
        plates=_plates(_mapping(data.get("plate_specs"), "plate_specs"), data.get("names")),
        base=base_spec(data.get("base_type")) if backing is Backing.BASE else None,
        **fields,
    )


def load_job(
    path: str | Path | None = None,
    *,
    defaults: str | Path | None = DEFAULTS_PATH,
    overrides: dict | None = None,
) -> Job:
    """Build a Job from the defaults file, an optional job file and optional overrides.

    The default defaults file is skipped when it does not exist, so the tool also
    works outside the repo.
    """
    layers = []
    if defaults is not None and (Path(defaults).exists() or Path(defaults) != DEFAULTS_PATH):
        layers.append(load_yaml(defaults))
    if path is not None:
        layers.append(load_yaml(path))
    if overrides:
        layers.append(overrides)
    data: dict = {}
    for layer in layers:
        data = merge(data, layer)
    return job_from_dict(data)
