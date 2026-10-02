"""Command line entry point: `nameplates single` and `nameplates batch`."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .config import DEFAULTS_PATH, load_job
from .plate import BuildError, build_nameplate
from .specs import Backing, Job, Relief, SpecError
from .surfaces import surface_for


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "plate"


def _size(value: str):
    return value if value == "fit" else float(value)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nameplates", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--defaults", type=Path, default=DEFAULTS_PATH, help="defaults file layered under the config (default: %(default)s)"
    )

    single = commands.add_parser("single", parents=[common], help="build one plate")
    single.add_argument("config", nargs="?", type=Path, help="YAML config; flags below override it")
    single.add_argument("--text")
    single.add_argument("--font", help="font name or path to a .ttf/.otf file")
    single.add_argument("--relief", choices=[relief.value for relief in Relief])
    single.add_argument("--width", type=_size, help="plate width in mm, or 'fit'")
    single.add_argument("--height", type=_size, help="plate height in mm, or 'fit'")
    single.add_argument("--backing", choices=[backing.value for backing in Backing])
    single.add_argument("--base", help="base model from the catalog, e.g. gw-40mm")
    single.add_argument("-o", "--output", type=Path, help="STL file to write (default: out/<text>.stl)")

    batch = commands.add_parser("batch", parents=[common], help="build every plate listed in a job file")
    batch.add_argument("config", type=Path, help="YAML job file with a `names` list")
    batch.add_argument("-o", "--output", type=Path, help="directory to write into (default: out/<job name>)")
    return parser


def _single_overrides(args) -> dict:
    plate = {key: getattr(args, key) for key in ("text", "font", "relief", "width", "height")}
    overrides: dict = {"plate_specs": {key: value for key, value in plate.items() if value is not None}}
    if args.text is not None:
        overrides["names"] = None
    if args.backing is not None:
        overrides["backing"] = args.backing
    if args.base is not None:
        overrides["base_type"] = {"model": args.base}
    return overrides


def _build_all(job: Job, targets: list[Path]) -> int:
    """Build each plate to its target path. Returns how many failed."""
    surface = surface_for(job)
    failures = 0
    for spec, target in zip(job.plates, targets):
        try:
            plate = build_nameplate(spec, surface, mesh_deviation=job.mesh_deviation)
        except (SpecError, BuildError) as error:
            print(f"FAILED {spec.text!r}: {error}", file=sys.stderr)
            failures += 1
            continue
        plate.export_stl(target)
        print(f"{target}  {plate.summary()}")
        for warning in plate.warnings:
            print(f"warning: {spec.text!r}: {warning}", file=sys.stderr)
    return failures


def _unique_targets(job: Job, directory: Path) -> list[Path]:
    targets, seen = [], {}
    for spec in job.plates:
        slug = _slug(spec.text)
        seen[slug] = seen.get(slug, 0) + 1
        targets.append(directory / (f"{slug}.stl" if seen[slug] == 1 else f"{slug}-{seen[slug]}.stl"))
    return targets


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "single":
            job = load_job(args.config, defaults=args.defaults, overrides=_single_overrides(args))
            if len(job.plates) != 1:
                raise SpecError(f"config lists {len(job.plates)} names; use `nameplates batch`, or pass --text")
            targets = [args.output or Path("out") / f"{_slug(job.plates[0].text)}.stl"]
        else:
            job = load_job(args.config, defaults=args.defaults)
            targets = _unique_targets(job, args.output or Path("out") / _slug(job.name))
        failures = _build_all(job, targets)
    except SpecError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if failures:
        print(f"{failures} of {len(job.plates)} plates failed", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
