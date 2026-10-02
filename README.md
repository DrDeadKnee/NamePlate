# NamePlates

This repo exists to house code to create 3d images for miniature name plates. 
For any individual name plate, target surface geometry, name, direction, and font can be given.

The software needs to run in batch or individual modes.

The target geometry might be flat, in which case a height and width need to be specified. However, the
traditional target would be a games workshop miniature base. these bases are well described as slices of
a cone - giving something like a beveled cylinder with a broad face and a short height. For example, a typical
"40mm" base is 39mm in diameter at the bottom, 37mm in diameter at the top, and 4.5mm in height. A nameplate
that fits on that base would need to match the curvature almost exactly on the back 
(err on a configuratble tolerance defaulting to 1% "too straight").

Some default parameters are written in configs/default.yml

## Setup

```
uv sync
```

## Usage

Run from the repo root so `configs/default.yml` and `fonts/` are found.

```
# one plate; flags override the config
uv run nameplates single --text "99 WAYNE GRETZKY"
uv run nameplates single --text "FLAT PLATE" --backing flat --height 8 --width 40 -o out/flat.stl

# every name in a job file, one STL each, into out/<job name>/
uv run nameplates batch configs/batch-example.yml
```

Settings are layered: built-in defaults, then `configs/default.yml`, then the config or job
file, then command line flags. A batch job lists `names`; `plate_specs` apply to all of them, and
an entry can be a mapping to override settings for that one plate (see `configs/batch-example.yml`).

### Sizing

- `height: fit` uses the base wall's height; a flat plate needs an explicit height.
- `font_size: fit` makes capital letters fill the height between the paddings, so plates of the
  same height get the same lettering. Descenders may dip into the padding.
- `width: fit` follows the text. With an exact width, text that is too long is shrunk, with a warning.

### Fonts and bases

- `font` is a name matched against font file names (`DejaVu Sans Bold` finds `DejaVuSans-Bold.ttf`),
  looked up in `fonts/` first and then the system font directories, or a path to a `.ttf`/`.otf` file.
- `base_type.model` is looked up in `src/nameplates/data/bases.yml`; explicit `height`, `top_d` and
  `bottom_d` override the lookup. Only round bases are built so far.

## How it works

Every plate is built flat (body, text, border), meshed, and then mapped onto its target surface.
A surface is a small class in `src/nameplates/surfaces.py` that maps flat plate coordinates into 3D,
so new targets (other base shapes, scanned or irregular surfaces) only need a new surface class.

Curved plates come out standing as they would on a base centred on the origin, facing -Y.

```python
from nameplates import FrustumSurface, PlateSpec, build_nameplate

surface = FrustumSurface(bottom_d=39, top_d=37, height=4.5, tolerance=0.01)
plate = build_nameplate(PlateSpec("99 WAYNE GRETZKY"), surface)
plate.export_stl("gretzky.stl")
```

## Tests

```
uv run pytest
```

## Earmarked for later

- Custom borders (only `none` and a plain raised `rim` exist; builders register in `builder.BORDERS`)
- Beveled text
- Square and ellipse bases
- Less well-defined target surfaces
- CSV batch input

