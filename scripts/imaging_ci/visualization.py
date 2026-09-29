"""
Visualization: Charge Injection Imaging
=======================================

Renders every figure ``VisualizerImagingCI`` writes during a real PyAutoCTI model-fit of
charge injection imaging, plus the rest of the ``autocti.plot`` charge injection
function surface, on this repo's tiny 30x30 ``dataset/imaging_ci/*`` datasets, so the
most up-to-date version of each figure lives in git and can be browsed on GitHub
(``GALLERY.md``) without re-running a fit.

This script RENDERS, it does not test: there are no assertions on file names or FITS
HDUs (that is ``autocti_workspace_test``'s job). Which Visualizer figures appear is
governed by ``config/visualize/plots.yaml`` (every toggle on, including
``dataset.fpr_non_uniformity``).

Output tree (wiped at the start of every run so stale PNGs never linger)::

    scripts/imaging_ci/images/visualization/
        parallel_serial/   <- parallel + serial CTI with cosmic rays (all 4 FPR / EPER
                              regions + fpr_non_uniformity)
            dataset_combined/, fit_dataset_combined/
                              <- the combined (multi-dataset) lifecycle over all 3
                                 normalizations: visualize_before_fit_combined +
                                 visualize_combined
            norm_5000/dataset/, norm_5000/fit_dataset/
                              <- one analysis: visualize_before_fit + visualize
        parallel/          <- parallel CTI only (the parallel regions only)
            norm_5000/dataset/, norm_5000/fit_dataset/
                              <- one analysis: visualize_before_fit + visualize
        direct/            <- the aplt.* charge injection figures the Visualizer never
                              writes, on the parallel_serial norm-5000 dataset / fit:
                              figure_pre_cti_data_residual_map,
                              subplot_noise_scaling_map_dict, and figure_fit_ci_region
                              for the six quantities it does not plot (parallel EPER)

Every analysis writes the same KIND of figures, so one analysis (the norm-5000 dataset)
stands in for the three a multi-dataset fit writes; the combined pass still fits all
three. The gallery renders each distinct figure once rather than the full quantity x
region x logy product the plot functions accept, because the PNGs are plain-git
tracked and re-rendered on every release. The ``parallel_serial`` fit masks its cosmic
rays (1-pixel buffer); its ``subplot_dataset`` is the 5-panel one with the cosmic ray
map. No ``dataset_full`` is passed (it would duplicate every figure into ``*_full/``
folders). The FITS products (``fit.fits``) are gitignored; only PNGs are tracked.

The model is each simulator's TRUE model (``dataset/imaging_ci/<name>/cti.json``), so
every figure shows what a user sees in ``output/`` after a fit that found the right
answer. No non-linear search runs: no corner / search figures here.

Run from the repo root::

    python scripts/imaging_ci/visualization.py
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
    output_path=str(REPO_ROOT / "scripts" / "imaging_ci" / "images"),
)

import autocti as ac
import autocti.plot as aplt
import autofit as af
from autocti.charge_injection.model.visualizer import VisualizerImagingCI

from _viz_cli import auto_simulate_if_missing

SOURCES = ("parallel_serial", "parallel")
PIXEL_SCALES = 0.1

"""
__Paths__

``VisualizerImagingCI`` only needs ``image_path`` and ``output_path``. The image tree is
wiped first so the committed PNG set is exactly what this run produced.
"""
image_path = REPO_ROOT / "scripts" / "imaging_ci" / "images" / "visualization"
if image_path.exists():
    shutil.rmtree(image_path)
image_path.mkdir(parents=True)

scratch_root = REPO_ROOT / "output" / "visualization" / "imaging_ci"
if scratch_root.exists():
    shutil.rmtree(scratch_root)


def _paths(sub: str) -> SimpleNamespace:
    img = image_path / sub
    img.mkdir(parents=True, exist_ok=True)
    out = scratch_root / sub  # scratch output -> gitignored output/
    out.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(image_path=img, output_path=out)


def load_source(name: str):
    """Datasets (unmasked + cosmic-ray masked), clocker, true model and analyses of one source."""
    dataset_path = REPO_ROOT / "dataset" / "imaging_ci" / name
    auto_simulate_if_missing(
        dataset_path, dataset_type="imaging_ci", dataset_name=name, workspace_root=REPO_ROOT
    )

    norm_list = json.loads((dataset_path / "norm_list.json").read_text())
    layout = ac.from_json(file_path=dataset_path / "layout.json")
    clocker = ac.from_json(file_path=dataset_path / "clocker.json")
    cti = ac.from_json(file_path=dataset_path / "cti.json")

    full_list, masked_list = [], []
    for norm in norm_list:
        norm_path = dataset_path / f"norm_{norm}"
        cosmic_ray_map_path = norm_path / "cosmic_ray_map.fits"
        dataset = ac.ImagingCI.from_fits(
            data_path=norm_path / "data.fits",
            noise_map_path=norm_path / "noise_map.fits",
            pre_cti_data_path=norm_path / "pre_cti_data.fits",
            cosmic_ray_map_path=cosmic_ray_map_path if cosmic_ray_map_path.exists() else None,
            layout=layout,
            pixel_scales=PIXEL_SCALES,
        )
        mask = ac.Mask2D.all_false(
            shape_native=dataset.shape_native, pixel_scales=dataset.pixel_scales
        )
        full_list.append(dataset.apply_mask(mask=mask))
        if dataset.cosmic_ray_map is not None:
            mask = mask + ac.Mask2D.from_cosmic_ray_map_buffed(
                cosmic_ray_map=dataset.cosmic_ray_map,
                settings=ac.SettingsMask2D(
                    cosmic_ray_parallel_buffer=1,
                    cosmic_ray_serial_buffer=1,
                    cosmic_ray_diagonal_buffer=0,
                ),
            )
        masked_list.append(dataset.apply_mask(mask=mask))

    # Every parameter fixed to the simulator's value: the prior-median instance IS the
    # true model. ``region_list_from`` reads ``model.cti.parallel_ccd`` / ``serial_ccd``.
    cti_kwargs = dict(parallel_trap_list=cti.parallel_trap_list, parallel_ccd=cti.parallel_ccd)
    if cti.serial_ccd is not None:
        cti_kwargs.update(serial_trap_list=cti.serial_trap_list, serial_ccd=cti.serial_ccd)
    model = af.Collection(cti=af.Model(ac.CTI2D, **cti_kwargs))
    instance = model.instance_from_prior_medians()

    analysis_list = [
        ac.AnalysisImagingCI(dataset=masked, clocker=clocker) for masked in masked_list
    ]
    return SimpleNamespace(
        norm_list=norm_list,
        clocker=clocker,
        cti=cti,
        full_list=full_list,
        model=model,
        instance=instance,
        analysis_list=analysis_list,
    )


"""
__Visualizer Lifecycle__

One analysis — dataset/: subplot_dataset, subplot_1d_ci_<region>, data_<region>,
data_logy_<region>, subplot_data_binned; fit_dataset/: subplot_fit,
subplot_1d_fit_ci_<region>, data / residual_map (+ logy) per region, fit.fits.
Combined (parallel_serial only) — dataset_combined/ and fit_dataset_combined/: the
*_list subplots. The factor graph passes one instance per analysis.
"""
REPRESENTATIVE = 1  # the norm-5000 analysis
COMBINED = ("parallel_serial",)

sources = {}
for name in SOURCES:
    src = load_source(name)
    sources[name] = src

    norm = src.norm_list[REPRESENTATIVE]
    analysis = src.analysis_list[REPRESENTATIVE]
    t0 = time.perf_counter()
    paths = _paths(f"{name}/norm_{norm}")
    VisualizerImagingCI.visualize_before_fit(analysis=analysis, paths=paths, model=src.model)
    VisualizerImagingCI.visualize(
        analysis=analysis, paths=paths, instance=src.instance, during_analysis=False
    )
    print(f"lifecycle [{name}/norm_{norm}]: {time.perf_counter() - t0:.1f}s")

    if name not in COMBINED:
        continue

    t0 = time.perf_counter()
    paths = _paths(name)
    VisualizerImagingCI.visualize_before_fit_combined(
        analyses=src.analysis_list, paths=paths, model=src.model
    )
    VisualizerImagingCI.visualize_combined(
        analyses=src.analysis_list,
        paths=paths,
        instance=[src.instance] * len(src.analysis_list),
        during_analysis=False,
    )
    print(f"lifecycle [{name}/combined]: {time.perf_counter() - t0:.1f}s")

"""
__Direct plot functions__

The ``aplt.*`` charge injection figures the Visualizer never writes, on the
parallel_serial norm-5000 unmasked dataset and its true-model fit. Every other function
(``figure_imaging_ci_data_region``, ``subplot_imaging_ci`` incl. its 5-panel cosmic-ray
form, ``subplot_imaging_ci_region``, ``subplot_imaging_ci_data_binned``,
``subplot_fit_ci``, ``subplot_fit_ci_region`` and the ``*_list`` variants) already
appears above.
"""
t0 = time.perf_counter()
direct_path = image_path / "direct"
direct_path.mkdir(parents=True)

src = sources["parallel_serial"]
dataset = src.full_list[REPRESENTATIVE]
fit = src.analysis_list[REPRESENTATIVE].fit_via_instance_and_dataset_from(
    instance=src.instance, dataset=dataset
)

aplt.figure_pre_cti_data_residual_map(dataset=dataset, output_path=direct_path, output_format="png")

for quantity in (
    "noise_map",
    "signal_to_noise_map",
    "pre_cti_data",
    "post_cti_data",
    "normalized_residual_map",
    "chi_squared_map",
):
    aplt.figure_fit_ci_region(
        fit=fit,
        quantity=quantity,
        region="parallel_eper",
        output_path=direct_path,
        output_format="png",
    )

"""
The noise scaling maps a hyper fit scales the noise with are the chi-squared maps of a
previous fit restricted to each region (``ResultImagingCI.noise_scaling_map_dict``);
here they come from the true-model fit of the unmasked dataset.
"""
noise_scaling_map_dict = {
    "regions_ci": fit.chi_squared_map_of_regions_ci,
    "parallel_eper": fit.chi_squared_map_of_parallel_eper,
    "serial_eper": fit.chi_squared_map_of_serial_eper,
    "serial_overscan_no_eper": fit.chi_squared_map_of_serial_overscan_no_eper,
}
dataset_scaled = ac.ImagingCI(
    data=dataset.data,
    noise_map=dataset.noise_map,
    pre_cti_data=dataset.pre_cti_data,
    layout=dataset.layout,
    cosmic_ray_map=dataset.cosmic_ray_map,
    noise_scaling_map_dict=noise_scaling_map_dict,
)
fit_scaled = ac.FitImagingCI(
    dataset=dataset_scaled,
    post_cti_data=src.clocker.add_cti(data=dataset.pre_cti_data, cti=src.cti),
)
aplt.subplot_noise_scaling_map_dict(fit=fit_scaled, output_path=direct_path, output_format="png")
print(f"direct: {time.perf_counter() - t0:.1f}s")

n_png = len(list(image_path.rglob("*.png")))
print(f"Wrote {n_png} PNGs under {image_path.relative_to(REPO_ROOT)}")
