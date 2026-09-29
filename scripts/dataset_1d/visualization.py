"""
Visualization: Dataset1D
========================

Renders every figure ``VisualizerDataset1D`` writes during a real PyAutoCTI model-fit of
1D CTI data, plus the rest of the ``autocti.plot`` 1D function surface, on this repo's
tiny ``dataset/dataset_1d/simple`` dataset, so the most up-to-date version of each figure
lives in git and can be browsed on GitHub (``GALLERY.md``) without re-running a fit.

This script RENDERS, it does not test: there are no assertions on file names or FITS
HDUs (that is ``autocti_workspace_test``'s job). Which Visualizer figures appear is
governed by ``config/visualize/plots.yaml`` (every toggle on).

Output tree (wiped at the start of every run so stale PNGs never linger)::

    scripts/dataset_1d/images/visualization/
        dataset/, fit_dataset_combined/   <- the combined (multi-dataset) lifecycle:
                                             visualize_before_fit_combined +
                                             visualize_combined over all 3 analyses
        norm_5000/
            dataset/, fit_dataset/        <- one analysis: visualize_before_fit +
                                             visualize with the TRUE CTI model
        direct/                           <- the aplt.* 1D figures the Visualizer never
                                             writes: figure_fit_dataset_1d for the six
                                             quantities it does not plot (full dataset,
                                             linear y)

A model-fit of several datasets hands each analysis its own output folder and writes
the combined figures once. Every analysis writes the same KIND of figures, so one
analysis (the norm-5000 dataset) stands in for all three; the combined pass still
fits all three. The gallery renders each distinct figure once rather than the full
quantity x region x logy product the plot functions accept, because the PNGs are
plain-git tracked and re-rendered on every release. The FITS products (``fit.fits``)
are gitignored; only PNGs are tracked.

The model is the simulator's TRUE model (``dataset/dataset_1d/simple/cti.json``), so
every figure shows what a user sees in ``output/`` after a fit that found the right
answer. No non-linear search runs: no corner / search figures here.

Run from the repo root::

    python scripts/dataset_1d/visualization.py
"""

import json
import shutil
import sys
import time
from pathlib import Path
from types import SimpleNamespace


def _repo_root() -> Path:
    for _p in Path(__file__).resolve().parents:
        if (_p / "ruff.toml").exists():
            return _p
    raise RuntimeError("autocti_visualization root (ruff.toml) not found")


REPO_ROOT = _repo_root()
sys.path.insert(0, str(REPO_ROOT))

# Push the all-true plots.yaml before any visualization code path reads config.
from autonerves import conf

conf.instance.push(
    new_path=str(REPO_ROOT / "config"),
    output_path=str(REPO_ROOT / "scripts" / "dataset_1d" / "images"),
)

import autocti as ac
import autocti.plot as aplt
import autofit as af
from autocti.dataset_1d.model.visualizer import VisualizerDataset1D

from _viz_cli import auto_simulate_if_missing

DATASET_NAME = "simple"

"""
__Dataset__

One ``Dataset1D`` per injection normalization, unmasked (``Mask1D.all_false``), with the
layout, clocker and true CTI model the simulator saved next to the FITS.
"""
dataset_path = REPO_ROOT / "dataset" / "dataset_1d" / DATASET_NAME

auto_simulate_if_missing(
    dataset_path, dataset_type="dataset_1d", dataset_name=DATASET_NAME, workspace_root=REPO_ROOT
)

norm_list = json.loads((dataset_path / "norm_list.json").read_text())
layout = ac.from_json(file_path=dataset_path / "layout.json")
clocker = ac.from_json(file_path=dataset_path / "clocker.json")
cti = ac.from_json(file_path=dataset_path / "cti.json")

dataset_list = []
for norm in norm_list:
    dataset = ac.Dataset1D.from_fits(
        data_path=dataset_path / f"norm_{norm}" / "data.fits",
        noise_map_path=dataset_path / f"norm_{norm}" / "noise_map.fits",
        pre_cti_data_path=dataset_path / f"norm_{norm}" / "pre_cti_data.fits",
        layout=layout,
        pixel_scales=0.1,
    )
    mask = ac.Mask1D.all_false(
        shape_slim=dataset.data.shape_slim, pixel_scales=dataset.data.pixel_scales
    )
    dataset_list.append(dataset.apply_mask(mask=mask))

"""
__True Model__

Every parameter fixed to the simulator's value, so the model has no free parameters and
its prior-median instance IS the true model.
"""
model = af.Collection(cti=af.Model(ac.CTI1D, trap_list=cti.trap_list, ccd=cti.ccd))
instance = model.instance_from_prior_medians()

analysis_list = [ac.AnalysisDataset1D(dataset=dataset, clocker=clocker) for dataset in dataset_list]

"""
__Paths__

``VisualizerDataset1D`` only needs ``image_path`` and ``output_path``. The image tree is
wiped first so the committed PNG set is exactly what this run produced.
"""
image_path = REPO_ROOT / "scripts" / "dataset_1d" / "images" / "visualization"
if image_path.exists():
    shutil.rmtree(image_path)
image_path.mkdir(parents=True)

scratch_root = REPO_ROOT / "output" / "visualization" / "dataset_1d"
if scratch_root.exists():
    shutil.rmtree(scratch_root)


def _paths(sub: str | None) -> SimpleNamespace:
    img = image_path / sub if sub else image_path
    img.mkdir(parents=True, exist_ok=True)
    out = scratch_root / (sub or "combined")  # scratch output -> gitignored output/
    out.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(image_path=img, output_path=out)


"""
__Visualizer Lifecycle (one analysis)__

dataset/: subplot_dataset, data, data_logy (+ per-region fpr / eper variants).
fit_dataset/: subplot_fit, data, data_logy, residual_map, residual_map_logy (+ regions),
fit.fits.
"""
REPRESENTATIVE = 1  # the norm-5000 analysis

t0 = time.perf_counter()
paths = _paths(f"norm_{norm_list[REPRESENTATIVE]}")
analysis = analysis_list[REPRESENTATIVE]
VisualizerDataset1D.visualize_before_fit(analysis=analysis, paths=paths, model=model)
VisualizerDataset1D.visualize(
    analysis=analysis, paths=paths, instance=instance, during_analysis=False
)
print(f"lifecycle [norm_{norm_list[REPRESENTATIVE]}]: {time.perf_counter() - t0:.1f}s")

"""
__Visualizer Lifecycle (combined)__

dataset/: subplot_data_list (+ regions, logy). fit_dataset_combined/: subplot_<quantity>_list
(+ regions, logy). The factor graph passes one instance per analysis.
"""
t0 = time.perf_counter()
paths = _paths(None)
VisualizerDataset1D.visualize_before_fit_combined(analyses=analysis_list, paths=paths, model=model)
VisualizerDataset1D.visualize_combined(
    analyses=analysis_list,
    paths=paths,
    instance=[instance] * len(analysis_list),
    during_analysis=False,
)
print(f"lifecycle [combined]: {time.perf_counter() - t0:.1f}s")

"""
__Direct plot functions__

``figure_fit_dataset_1d`` for the quantities the Visualizer never writes as single
figures (it writes ``data`` and ``residual_map``, in every region and with log10 y).
Every other ``aplt.*`` 1D function (``figure_dataset_1d_data``, ``subplot_dataset_1d``,
``subplot_fit_dataset_1d`` and the ``*_list`` variants) already appears above.
"""
t0 = time.perf_counter()
direct_path = image_path / "direct"
direct_path.mkdir(parents=True)

fit = analysis.fit_via_instance_from(instance=instance)
for quantity in (
    "noise_map",
    "signal_to_noise_map",
    "pre_cti_data",
    "post_cti_data",
    "normalized_residual_map",
    "chi_squared_map",
):
    aplt.figure_fit_dataset_1d(
        fit=fit, quantity=quantity, output_path=direct_path, output_format="png"
    )
print(f"direct: {time.perf_counter() - t0:.1f}s")

n_png = len(list(image_path.rglob("*.png")))
print(f"Wrote {n_png} PNGs under {image_path.relative_to(REPO_ROOT)}")
