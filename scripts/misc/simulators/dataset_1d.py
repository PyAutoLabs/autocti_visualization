"""
Simulator: 1D CTI Datasets
==========================

Simulates the tiny 1D CTI dataset the ``scripts/dataset_1d/visualization.py`` producer
renders, and writes it to ``dataset/dataset_1d/<name>/``:

- ``norm_<n>/{data,noise_map,pre_cti_data}.fits`` — one ``Dataset1D`` per injection
  normalization;
- ``layout.json`` / ``clocker.json`` / ``cti.json`` — the ``Layout1D``, ``Clocker1D``
  and TRUE ``CTI1D`` model, which the producer reloads with ``ac.from_json`` so every
  fit figure is the fit of the model that made the data;
- ``norm_list.json`` — the normalizations (the per-norm folder names).

Adapted from ``autocti_workspace/scripts/dataset_1d/simulators/start_here.py`` at a
tiny size (50 pixels, the layout of ``autocti_workspace_test/scripts/plot/subplots.py``)
so the FITS are a few KB and every figure renders in seconds. There is no
``instruments/`` package in this repo: the CCD layout lives here.

The tracked ``dataset/dataset_1d/simple/`` was produced by::

    python scripts/misc/simulators/dataset_1d.py --dataset simple

The true model:

- ``Layout1D``: 50 pixels, FPR (charge injection) over pixels 5-25, prescan 0-5,
  overscan 45-50 — the EPER trails into pixels 25-50;
- 3 normalizations: 100, 5000 and 25000 e-;
- 2 ``TrapInstantCapture`` species (density 5.0 / release 1.25, density 10.0 / release
  4.4) with a ``CCDPhase`` (well fill power 0.58, full well 200000 e-);
- read noise 1.0 e-, fixed noise seeds (reproducible).

Usage
-----

    python scripts/misc/simulators/dataset_1d.py                   # simple (default)
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

DATASETS = ("simple",)
NORM_LIST = [100, 5000, 25000]


def simulate(dataset_name: str = "simple", output_root: Path | None = None) -> Path:
    """Simulate the named 1D dataset. Returns the dataset dir."""
    import matplotlib

    matplotlib.use("Agg")
    import autocti as ac

    if dataset_name not in DATASETS:
        raise ValueError(f"Unknown dataset '{dataset_name}'. Choose from: {list(DATASETS)}")

    root = output_root if output_root is not None else _REPO_ROOT
    dataset_path = root / "dataset" / "dataset_1d" / dataset_name
    dataset_path.mkdir(parents=True, exist_ok=True)

    print(f"\n--- Dataset1D simulator [{dataset_name}] ---")
    print(f"  output: {dataset_path}")

    layout = ac.Layout1D(
        shape_1d=(50,),
        region_list=[(5, 25)],
        prescan=ac.Region1D((0, 5)),
        overscan=ac.Region1D((45, 50)),
    )

    clocker = ac.Clocker1D(express=5)

    cti = ac.CTI1D(
        trap_list=[
            ac.TrapInstantCapture(density=5.0, release_timescale=1.25),
            ac.TrapInstantCapture(density=10.0, release_timescale=4.4),
        ],
        ccd=ac.CCDPhase(well_fill_power=0.58, well_notch_depth=0.0, full_well_depth=200000.0),
    )

    for i, norm in enumerate(NORM_LIST):
        simulator = ac.SimulatorDataset1D(
            read_noise=1.0, pixel_scales=0.1, norm=norm, noise_seed=i + 1
        )
        dataset = simulator.via_layout_from(clocker=clocker, layout=layout, cti=cti)
        norm_path = dataset_path / f"norm_{int(norm)}"
        norm_path.mkdir(parents=True, exist_ok=True)
        dataset.output_to_fits(
            data_path=norm_path / "data.fits",
            noise_map_path=norm_path / "noise_map.fits",
            pre_cti_data_path=norm_path / "pre_cti_data.fits",
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
        default="simple",
        choices=list(DATASETS),
        help="Dataset to simulate (default: simple).",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Override the repo root that holds dataset/ (default: inferred from this file).",
    )
    args = parser.parse_args()
    simulate(dataset_name=args.dataset, output_root=args.output_root)
