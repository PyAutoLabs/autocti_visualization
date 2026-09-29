# autocti_visualization

**[Browse the gallery → GALLERY.md](GALLERY.md)**

The permanent, rendered gallery of every figure PyAutoCTI writes during a model-fit — the
**CTI visualization project repo** of the PyAutoLabs organism.

This repo owns the CTI figures: the producer scripts, the simulators and datasets, the all-on
[`plots.yaml`](config/visualize/plots.yaml), the tracked PNGs, [`GALLERY.md`](GALLERY.md) and
the render harness. The organ [PyAutoEyes](https://github.com/PyAutoLabs/PyAutoEyes) is the
cross-project visualization dashboard: it reads this repo's tracked figure manifest
([`gallery/viz_manifest.yaml`](gallery/viz_manifest.yaml)) and links to the PNGs here — it never
renders or copies them. It is the sibling of
[autolens_visualization](https://github.com/PyAutoLabs/autolens_visualization) and
[autogalaxy_visualization](https://github.com/PyAutoLabs/autogalaxy_visualization), in the same
shape.

## Vision

Until now, the only way to see what a PyAutoCTI figure looks like was to run a CTI calibration
script and open its `output/` folder. This repo keeps the most up-to-date rendering of every
visualizer output in git — for 1D CTI data and for charge injection imaging — so there is one
place to see every figure, judge it, and improve it (by hand or in an AI chat pointed at the
plotting source) without re-running anything.

Each figure is what `VisualizerDataset1D` / `VisualizerImagingCI` write to a fit's `image/`
folder — for one analysis and for the combined multi-dataset pass over three charge injection
normalizations — rendered with the simulator's true CTI model and every toggle in
[`config/visualize/plots.yaml`](config/visualize/plots.yaml) switched on. Charge injection
imaging is rendered for a parallel + serial CTI model with cosmic rays and for a parallel-only
model. A `direct/` folder per domain adds the `autocti.plot` figures the visualizers never write
(the remaining single-quantity fit figures, the pre-CTI residual map and the noise-scaling maps).
Each distinct figure is rendered once, so the gallery stays small (the PNGs are plain-git
tracked and re-rendered every release).

## Render locally

`import autocti` needs [arcticpy](https://github.com/jkeger/arctic), a C++ extension built from
source; CI installs it with PyAutoHeart's `install-arcticpy` action (the recipe and version pin
live in `PyAutoHeart/.github/actions/install-arcticpy/install_arcticpy.sh`).

```bash
source activate.sh                  # library checkouts on PYTHONPATH (see the file)
bash gallery/gallery_run.sh --all   # run every producer, rebuild GALLERY.md + manifest, --check
```

Or one domain: `python scripts/imaging_ci/visualization.py`, then
`python gallery/gallery_build.py`. Commit the regenerated PNGs under `scripts/<domain>/images/`
together with `GALLERY.md` and `gallery/viz_manifest.yaml` (every figure's producer, domain,
source folder, path, byte size and sha256, plus the stack versions it was rendered with). On
every PyAutoCTI release, [`render.yml`](.github/workflows/render.yml) re-renders with the
released stack, commits the result and pings PyAutoEyes (`repository_dispatch: eyes-refresh`)
to refresh its dashboard.

Runtime on an 8-core laptop (CPU): dataset_1d ~20 s, imaging_ci ~45 s.

## Add a domain

- Add a simulator under `scripts/misc/simulators/` and track its dataset under
  `dataset/<domain>/<name>/` (there is no `instruments/` package: the CCD layout lives in the
  simulator and is saved as `layout.json`).
- Add a flat producer `scripts/<domain>/visualization.py` modelled on
  [`scripts/imaging_ci/visualization.py`](scripts/imaging_ci/visualization.py).
- Run `bash gallery/gallery_run.sh --all` and commit the PNGs + `GALLERY.md` +
  `gallery/viz_manifest.yaml`.

## Improve a figure

Three edit surfaces, from cheapest to deepest:

- **Config** — [`config/visualize/plots.yaml`](config/visualize/plots.yaml): which figures are
  written at all.
- **Plot API** — the plotting code in the libraries: `PyAutoCTI/autocti/**/plot/`,
  `PyAutoCTI/autocti/util/plot_utils.py`, `PyAutoArray/autoarray/plot/`. Change it there (normal
  library workflow), then re-render here.
- **Script** — the producer in `scripts/<domain>/visualization.py` (dataset, model, sources).

The Brain Eyes agent runs the review loop on this repo:
`bin/pyauto-brain eyes survey cti/autocti_visualization` (or `/eyes review cti`). Accepted
critiques are filed with the `eyes-critique` label.

## Related repos

- [PyAutoEyes](https://github.com/PyAutoLabs/PyAutoEyes) — the organ: the cross-project
  visualization dashboard that aggregates this repo (reads `gallery/viz_manifest.yaml`, links to
  the PNGs here).
- [autocti_workspace](https://github.com/PyAutoLabs/autocti_workspace) — user-facing CTI
  calibration scripts and tutorials (the source of `config/` and of the simulators here).
- [autocti_workspace_test](https://github.com/PyAutoLabs/autocti_workspace_test) — plot-API
  integration tests the fit-without-search recipe here comes from.

## Community & support

Questions, figure bugs and visualization ideas go to the
[PyAutoLabs Discussions](https://github.com/orgs/PyAutoLabs/discussions).
