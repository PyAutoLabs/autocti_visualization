# autocti_visualization — Agent Instructions

This repo is the single home for **what PyAutoCTI figures look like**: it stores, in git, the
most up-to-date rendering of every figure the PyAutoCTI visualizers write during a model-fit —
of 1D CTI data (`Dataset1D`) and of charge injection imaging (`ImagingCI`) — so visualization
can be judged and improved (by humans or AI chats against the source) without re-running a
workspace fit. It is a collection of standalone producer scripts, **not** an installable
package — there is no `pyproject.toml`. These are the canonical, agent-agnostic instructions
for this repo; the `README.md` is the human-facing overview and `GALLERY.md` is the browsable
gallery. It is the CTI sibling of `lens/autolens_visualization` and
`galaxy/autogalaxy_visualization` and mirrors their layout.

## Layering: project repo vs organ

This is a **project repo** (category `project`): it makes, stores and tracks the CTI figures —
producers, simulators, datasets, `plots.yaml`, tracked PNGs, `GALLERY.md`, the render harness.
The organ **PyAutoEyes** is the cross-project visualization dashboard over the
`<lib>_visualization` project repos: it reads this repo's tracked `gallery/viz_manifest.yaml`
and links to the PNGs here; it renders nothing and copies no figures. Judging figures is the
Brain's Eyes conductor; figure changes land here (producer / config) or in the libraries (plot
API), never in the organ.

## Repository Structure

Producers are laid out **flat, one per domain** (`scripts/<domain>/visualization*.py`), because
the Brain Eyes agent scans `scripts/<domain>/*.py` non-recursively for stems containing
`visualization`:

```
scripts/
  dataset_1d/visualization.py        VisualizerDataset1D on dataset/dataset_1d/simple
  dataset_1d/images/visualization/   dataset/ + fit_dataset_combined/ (combined pass),
                                     norm_5000/{dataset,fit_dataset}/ (one analysis), direct/
  imaging_ci/visualization.py        VisualizerImagingCI on dataset/imaging_ci/{parallel_serial,parallel}
  imaging_ci/images/visualization/   parallel_serial/{dataset_combined,fit_dataset_combined}/,
                                     parallel_serial/norm_5000/..., parallel/norm_5000/..., direct/
  misc/simulators/                   dataset_1d.py + imaging_ci.py (regenerate datasets)
  misc/test/                         hermetic pytest for the gallery builder
gallery/gallery_build.py             GALLERY.md + gallery/viz_manifest.yaml + output/gallery/
gallery/viz_manifest.yaml            TRACKED, generated figure manifest (PyAutoEyes read contract)
gallery/gallery_run.sh               run producers -> build -> --check
config/                              the autocti_workspace config (general, logging, notation,
                                     non_linear/, priors/, visualize/) with version check off
config/visualize/plots.yaml          EVERY toggle on, incl. dataset.fpr_non_uniformity
dataset/dataset_1d/simple/           TRACKED, simulated here (50 px, 3 norms, 2 traps)
dataset/imaging_ci/parallel_serial/  TRACKED, simulated here (30x30, parallel+serial, cosmic rays)
dataset/imaging_ci/parallel/         TRACKED, simulated here (30x30, parallel only)
_viz_cli.py                          repo-root finder, dataset paths, auto-simulate hook
GALLERY.md                           TRACKED, generated — never edit by hand
```

**No `instruments/` package** (a deliberate deviation from the lens / galaxy siblings): a CTI
dataset's "instrument" is its CCD layout (shape, charge injection regions, prescans /
overscans), which lives in the simulators and is saved next to each dataset as `layout.json`,
together with `clocker.json` and the true-model `cti.json`. The producers reload all three with
`ac.from_json`.

**What is tracked.** PNG figures under `scripts/<domain>/images/**`, `GALLERY.md`,
`gallery/viz_manifest.yaml` and the datasets (per-normalization FITS + the JSONs). The FITS
(`fit.fits`) / CSV / JSON data products the visualizers also write are gitignored (bulky, not
viewable on GitHub), as is `output/`. `gallery_build.py` lists on-disk FITS in its scan (so
`--check` never flags them) but the tracked manifest carries PNG figures only.

**Import model.** Producers find the repo root by walking up to the directory containing
`ruff.toml` (a depth-proof sentinel) and put it on `sys.path`, so `_viz_cli` imports by name.

## Rendering

From the repo root, with the library checkouts on `PYTHONPATH` (`source activate.sh`) and
**arcticpy** installed (`import autocti` hard-requires it; CI installs it with
`PyAutoLabs/PyAutoHeart/.github/actions/install-arcticpy@main`, locally
`organs/PyAutoHeart/.github/actions/install-arcticpy/install_arcticpy.sh` holds the recipe and
the version pin):

```bash
bash gallery/gallery_run.sh --all          # every producer, then build + --check (~70 s)
python scripts/imaging_ci/visualization.py # one producer (~45 s)
python gallery/gallery_build.py            # rebuild GALLERY.md + gallery/viz_manifest.yaml + output/gallery/
python gallery/gallery_build.py --check    # fail if GALLERY.md or the manifest is stale vs the PNGs on disk
```

Each producer wipes its own `scripts/<domain>/images/visualization/` tree first, so the committed
PNG set is exactly what the last run produced. Commit the PNGs, `GALLERY.md` and
`gallery/viz_manifest.yaml` together.

**The tracked manifest** (`gallery/viz_manifest.yaml`, schema 1) lists every committed PNG as
`{file, producer, domain, source, bytes, sha256}` (`source` = the sub-folder path within the
producer's image dir, e.g. `parallel_serial/norm_5000/fit_dataset`, `dataset` or `direct`),
plus `rendered_with:` (the autocti / autoarray / autofit versions) and `generated:` (the date
the figures or stack last changed — carried over on an unchanged rebuild, so re-running is a
git no-op). There are no mtimes: it is reproducible from a checkout. `--check` ignores only
`generated:` and `rendered_with:`; any added, removed or byte-changed PNG fails it. It is the
read contract of the PyAutoEyes dashboard — change its shape only together with the organ.

**What each producer renders.** Each pushes `config/` via `conf.instance.push` (the all-true
`plots.yaml`), loads its tracked datasets (one per injection normalization: 100, 5000, 25000
e-), rebuilds the simulator's **true model** (`af.Collection(cti=af.Model(ac.CTI1D|CTI2D,
...))` with every parameter fixed, whose prior-median instance carries `.cti`), and runs the
Visualizer with a `SimpleNamespace(image_path=..., output_path=...)` paths stub:

- **One analysis** (`norm_5000/`): `visualize_before_fit` + `visualize` → `dataset/` and
  `fit_dataset/`. Every analysis of a multi-dataset fit writes the same kinds of figure, so one
  stands in for all three.
- **The combined pass** (top level for `dataset_1d`, `parallel_serial/` for `imaging_ci`):
  `visualize_before_fit_combined` + `visualize_combined` over all three analyses (one instance
  per analysis, as the factor graph passes them) → the `*_list` subplots.
- **`imaging_ci/parallel/`** renders only the one-analysis lifecycle (no combined pass): it is
  there to show the parallel-only region set `region_list_from` picks for a model without
  serial CTI.
- **`direct/`**: only the `aplt.*` figures the Visualizer never writes —
  `figure_fit_dataset_1d` / `figure_fit_ci_region` for the six quantities the Visualizer does
  not plot singly (noise map, S/N, pre-/post-CTI data, normalized residuals, chi-squared),
  `figure_pre_cti_data_residual_map`, and `subplot_noise_scaling_map_dict` (on a dataset whose
  `noise_scaling_map_dict` is the four region chi-squared maps of the true fit, as
  `ResultImagingCI.noise_scaling_map_dict` builds them).

**Figure budget.** The gallery renders each *distinct* figure once, not the full quantity ×
region × logy × normalization product the plot functions accept: the PNGs are plain-git tracked
(no LFS) and re-rendered on every release. Keep additions to new kinds of figure; check for
byte-identical duplicates (`sha256sum`) before committing.

**Rendering notes.**

- The `parallel_serial` fit masks its cosmic rays (`Mask2D.from_cosmic_ray_map_buffed`, 1-pixel
  buffers); its `subplot_dataset` is the 5-panel form with the cosmic ray map. No
  `dataset_full` is passed to the analyses (it would duplicate every figure into `*_full/`).
- `dataset.fpr_non_uniformity` is on, so the `imaging_ci` before-fit figures include the
  `fpr_non_uniformity` region; it renders (no skip needed).
- `Dataset1D`'s `visualize` with a `dataset_full` writes the full fit into the same
  `fit_dataset/` folder as the masked fit (no `_full` suffix, unlike `ImagingCI`), so it would
  overwrite; another reason no `dataset_full` is used here.
- No non-linear search runs, so there are no corner / search figures (`plots_search.yaml` is
  on for when one is added).

**Datasets.** All three were produced by this repo's simulators:

```bash
python scripts/misc/simulators/dataset_1d.py --dataset simple
python scripts/misc/simulators/imaging_ci.py --dataset parallel_serial
python scripts/misc/simulators/imaging_ci.py --dataset parallel
```

See each simulator's docstring for the layout and the true CTI model. The auto-simulate hook in
`_viz_cli.py` only fires when `cti.json` is absent — it never deletes a tracked dataset.

## Adding a domain

1. Add a simulator under `scripts/misc/simulators/` and track its dataset under
   `dataset/<domain>/<name>/`.
2. Add a flat producer `scripts/<domain>/visualization.py` modelled on the existing ones,
   writing to `scripts/<domain>/images/visualization/`.
3. Run `bash gallery/gallery_run.sh --all` and commit the PNGs + `GALLERY.md` +
   `gallery/viz_manifest.yaml`.

## Improving a figure (edit surfaces)

- **config** — `config/visualize/plots.yaml` here: which figures are written at all.
- **plot API** — the plotting code in the libraries: `PyAutoCTI/autocti/**/plot/`,
  `PyAutoCTI/autocti/util/plot_utils.py`, `PyAutoArray/autoarray/plot/` (library changes go
  through the normal library workflow, then this repo is re-rendered).
- **script** — the producer in `scripts/<domain>/visualization.py` (dataset, model, sources).

## Eyes contracts

Two readers depend on this repo's layout:

- **The Brain Eyes conductor** (`organs/PyAutoBrain/agents/conductors/eyes/`) reviews it:
  `bin/pyauto-brain eyes survey cti/autocti_visualization` (or `/eyes review cti`). It expects
  flat `scripts/<domain>/visualization*.py` producers writing `scripts/<domain>/images/<stem>/**`,
  a `gallery/gallery_run.sh` harness, and `output/gallery/{gallery.html,viz_manifest.yaml}` (the
  latter a gitignored copy of the tracked manifest). Accepted critiques are labelled
  `eyes-critique` and route through intake / start_dev like any other change.
- **The PyAutoEyes dashboard** reads the tracked `gallery/viz_manifest.yaml` and links to the
  PNGs; `render.yml` fires `repository_dispatch: eyes-refresh` at PyAutoLabs/PyAutoEyes after
  each release re-render.

Keep that layout when adding domains.

## Testing

The PR gate is `lint.yml` on Python 3.12 against the library mains (PyAutoNerves, PyAutoFit,
PyAutoArray, PyAutoCTI), after installing arcticpy via the PyAutoHeart composite action:

```bash
ruff check .
ruff format --check .
python gallery/gallery_build.py --check
pytest scripts/misc/test -q
```

plus `lychee` on every `*.md`, then every producer runs for real followed by
`gallery_build.py --check` (a PR that changes the figure set without regenerating `GALLERY.md`
fails). `render.yml` (manual + `repository_dispatch: pyautocti-release`) installs arcticpy and
the released PyPI stack, re-renders, commits PNGs + `GALLERY.md` + `gallery/viz_manifest.yaml`
back as `github-actions[bot]` `[skip ci]`, then dispatches `eyes-refresh` to PyAutoEyes (token:
`secrets.PAT_PYAUTOLABS`; the step warns and skips when the secret is unavailable).

## Sandboxed / restricted runs

```bash
NUMBA_CACHE_DIR=/tmp/numba_cache MPLCONFIGDIR=/tmp/matplotlib python scripts/imaging_ci/visualization.py
```

## Bulk-edit safety

When editing the same region across many scripts in one pass, only rewrite the targeted region.
**Never produce a whole-file write unless you have read the entire current file.**

## Related Repos

- `../PyAutoCTI` — the visualizers being rendered (plus `../../array/PyAutoArray`,
  `../../fit/PyAutoFit`, `../../organs/PyAutoNerves` on `PYTHONPATH`).
- `../autocti_workspace` — user-facing science scripts and tutorials; source of `config/` and
  of the simulators these were adapted from.
- `../autocti_workspace_test` — plot-API integration tests (`scripts/plot/subplots.py`, the
  fit-without-search recipe the producers use).
- `../../galaxy/autogalaxy_visualization`, `../../lens/autolens_visualization` — the siblings
  this repo mirrors; source of the gallery harness and the builder.
- `../../organs/PyAutoEyes` — the organ: cross-project visualization dashboard that aggregates
  this repo via `gallery/viz_manifest.yaml` (links to the PNGs, never copies them).

## Task Workflows

When changing a producer, the config or a dataset, re-render (`gallery/gallery_run.sh --all`),
keep `ruff check .` / `ruff format --check .` clean, and commit the PNGs + `GALLERY.md` +
`gallery/viz_manifest.yaml` in the same PR. Do not commit machine-specific absolute paths.

<!-- repos_sync:history:begin -->
## Never rewrite history

Never rewrite pushed history on any repo with a remote — no `git init` over a
tracked repo, no force-push to `main`, no fresh-start "Initial commit", no
`filter-repo` / `filter-branch` / `rebase -i` on pushed branches. To get a
clean tree: `git fetch origin && git reset --hard origin/main && git clean -fd`.
<!-- repos_sync:history:end -->

<!-- repos_sync:deliverable:begin -->
## Sessions end at their deliverable

A session ends when it reports its deliverable — never arm anything that
outlives the turn to wait for CI, a review or a merge: no `send_later`, no
`subscribe_pr_activity`, no `CronCreate`, no `ScheduleWakeup`, no `/loop`, no
`RemoteTrigger` create/update/run. Judge once, report, stop; the human re-runs
`/prm` (or the batch review) when it is green. Measured: five batch members
armed hourly check-ins on 2026-08-31, and a mobile `/prm` re-armed a 60-minute
`send_later` hourly all night on 2026-09-03 with no task active, draining usage.
<!-- repos_sync:deliverable:end -->

<!-- repos_sync:filing:begin -->
## Where to file

Questions, help with code or an analysis, ideas, bug reports and results from a
user or collaborator — or an agent acting for one — go to
<https://github.com/orgs/PyAutoLabs/discussions> in the matching category
(Help & Questions, Ideas & Proposals, Bugs & Errors, Show and tell;
Announcements is maintainers-only), never to this repo's Issues. An agent never
runs `gh issue create` for such a report: it drafts the title, category and
body and hands them to the human (sessions cannot create Discussions). Only the
development flow — Mind prompt → `/start_dev` → `/create_issue` → one issue per
task → PR — opens issues here. Why: `PyAutoMind/policy/community_surface.md`.
<!-- repos_sync:filing:end -->

<!-- repos_sync:standards:begin -->
## Shared standards

Before changing a shared interface, consult the applicable
[organism standard](https://github.com/PyAutoLabs/PyAutoBrain/blob/main/docs/standards.md)
on demand, identify affected consumers, and validate their adoption. Change
generated guidance at its canonical source and regenerate.
<!-- repos_sync:standards:end -->
