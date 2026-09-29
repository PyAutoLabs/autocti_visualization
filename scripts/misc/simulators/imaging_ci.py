"""
Simulator: Charge Injection Imaging Datasets
============================================

Simulates the tiny charge injection (``ImagingCI``) datasets the
``scripts/imaging_ci/visualization.py`` producer renders, and writes each to
``dataset/imaging_ci/<name>/``:

- ``norm_<n>/{data,noise_map,pre_cti_data}.fits`` (+ ``cosmic_ray_map.fits`` for
  ``parallel_serial``) — one ``ImagingCI`` per injection normalization;
- ``layout.json`` / ``clocker.json`` / ``cti.json`` — the ``Layout2DCI``, ``Clocker2D``
  and TRUE ``CTI2D`` model, which the producer reloads with ``ac.from_json``;
- ``norm_list.json`` — the normalizations (the per-norm folder names).

Adapted from ``autocti_workspace/scripts/imaging_ci/simulators/overview/
non_uniform_cosmic_rays.py`` and ``examples/parallel_and_serial.py`` at a tiny 30x30
size, so the FITS are a few KB and every figure renders in seconds. There is no
``instruments/`` package in this repo: the CCD layout lives here.

The tracked datasets were produced by::

    python scripts/misc/simulators/imaging_ci.py --dataset parallel_serial
    python scripts/misc/simulators/imaging_ci.py --dataset parallel

The layout (both datasets): 30x30 pixels, two charge injection regions (rows 2-8 and
14-20, columns 3-26), serial prescan columns 0-3, serial overscan columns 26-30,
parallel overscan rows 26-30. Normalizations 100, 5000 and 25000 e-, each injected
non-uniformly across columns (``column_sigma`` = 5% of the normalization), read noise
1.0 e-, fixed seeds (reproducible).

- ``parallel_serial``: 2 parallel ``TrapInstantCapture`` species (density 5.0 /
  release 1.25, density 10.0 / release 4.4, ``CCDPhase`` well fill power 0.58) plus 1
  serial species (density 5.0 / release 3.0, well fill power 0.75), and a cosmic ray
  map per normalization (``SimulatorCosmicRayMap.defaults``, capped at the full well).
- ``parallel``: the same parallel traps and CCD, no serial CTI, no cosmic rays.

Usage
-----

    python scripts/misc/simulators/imaging_ci.py                      # parallel_serial
    python scripts/misc/simulators/imaging_ci.py --dataset parallel
"""

import json
import sys as _sys
from pathlib import Path as _Path


def _repo_root() -> _Path:
    for _p in _Path(__file__).resolve().parents:
        if (_p / "ruff.toml").exists():
            return _p
    raise RuntimeError("autocti_visualization root (ruff.toml) not found")


if str(_repo_root()) not in _sys.path:
    _sys.path.insert(0, str(_repo_root()))

from pathlib import Path

_REPO_ROOT = _repo_root()

DATASETS = ("parallel_serial", "parallel")
NORM_LIST = [100, 5000, 25000]


def simulate(dataset_name: str = "parallel_serial", output_root: Path | None = None) -> Path:
    """Simulate the named charge injection dataset. Returns the dataset dir."""
    import matplotlib

    matplotlib.use("Agg")
    import autocti as ac

    if dataset_name not in DATASETS:
        raise ValueError(f"Unknown dataset '{dataset_name}'. Choose from: {list(DATASETS)}")

    with_serial = dataset_name == "parallel_serial"

    root = output_root if output_root is not None else _REPO_ROOT
    dataset_path = root / "dataset" / "imaging_ci" / dataset_name
    dataset_path.mkdir(parents=True, exist_ok=True)

    print(f"\n--- ImagingCI simulator [{dataset_name}] ---")
    print(f"  output: {dataset_path}")

    shape_native = (30, 30)
    serial_prescan = ac.Region2D((0, 30, 0, 3))
    serial_overscan = ac.Region2D((0, 30, 26, 30))
    parallel_overscan = ac.Region2D((26, 30, 3, 26))

    layout = ac.Layout2DCI(
        shape_2d=shape_native,
        region_list=[(2, 8, 3, 26), (14, 20, 3, 26)],
        parallel_overscan=parallel_overscan,
        serial_prescan=serial_prescan,
        serial_overscan=serial_overscan,
    )

    parallel_ccd = ac.CCDPhase(well_fill_power=0.58, well_notch_depth=0.0, full_well_depth=200000.0)
    parallel_trap_list = [
        ac.TrapInstantCapture(density=5.0, release_timescale=1.25),
        ac.TrapInstantCapture(density=10.0, release_timescale=4.4),
    ]

    if with_serial:
        clocker = ac.Clocker2D(
            parallel_express=5,
            parallel_roe=ac.ROEChargeInjection(),
            parallel_fast_mode=True,
            serial_express=5,
            serial_roe=ac.ROE(),
        )
        serial_ccd = ac.CCDPhase(
            well_fill_power=0.75, well_notch_depth=0.0, full_well_depth=200000.0
        )
        cti = ac.CTI2D(
            parallel_trap_list=parallel_trap_list,
            parallel_ccd=parallel_ccd,
            serial_trap_list=[ac.TrapInstantCapture(density=5.0, release_timescale=3.0)],
            serial_ccd=serial_ccd,
        )
    else:
        clocker = ac.Clocker2D(
            parallel_express=5, parallel_roe=ac.ROEChargeInjection(), parallel_fast_mode=True
        )
        cti = ac.CTI2D(parallel_trap_list=parallel_trap_list, parallel_ccd=parallel_ccd)

    for i, norm in enumerate(NORM_LIST):
        simulator = ac.SimulatorImagingCI(
            read_noise=1.0,
            pixel_scales=0.1,
            norm=norm,
            column_sigma=0.05 * norm,
            row_slope=0.0,
            max_norm=200000.0,
            noise_seed=i + 1,
            ci_seed=i + 101,
        )

        cosmic_ray_map = None
        if with_serial:
            cosmic_ray_map = ac.SimulatorCosmicRayMap.defaults(
                shape_native=shape_native,
                flux_scaling=1.0,
                pixel_scale=simulator.pixel_scales,
                seed=i + 201,
            ).cosmic_ray_map_from(limit=parallel_ccd.full_well_depth)

        dataset = simulator.via_layout_from(
            clocker=clocker, layout=layout, cti=cti, cosmic_ray_map=cosmic_ray_map
        )

        norm_path = dataset_path / f"norm_{int(norm)}"
        norm_path.mkdir(parents=True, exist_ok=True)
        dataset.output_to_fits(
            data_path=norm_path / "data.fits",
            noise_map_path=norm_path / "noise_map.fits",
            pre_cti_data_path=norm_path / "pre_cti_data.fits",
            cosmic_ray_map_path=(norm_path / "cosmic_ray_map.fits") if with_serial else None,
            overwrite=True,
        )

    (dataset_path / "norm_list.json").write_text(json.dumps(NORM_LIST) + "\n")
    ac.output_to_json(obj=layout, file_path=dataset_path / "layout.json")
    ac.output_to_json(obj=clocker, file_path=dataset_path / "clocker.json")
    # Written last: its presence is the auto-simulate "dataset complete" gate.
    ac.output_to_json(obj=cti, file_path=dataset_path / "cti.json")

    print(f"  wrote {dataset_path}")
    return dataset_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--dataset",
        type=str,
        default="parallel_serial",
        choices=list(DATASETS),
        help="Dataset to simulate (default: parallel_serial).",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Override the repo root that holds dataset/ (default: inferred from this file).",
    )
    args = parser.parse_args()
    simulate(dataset_name=args.dataset, output_root=args.output_root)
