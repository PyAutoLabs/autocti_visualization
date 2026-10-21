"""Shared helpers for the visualization producers and simulators.

Copied from ``autolens_visualization/_viz_cli.py`` (a deliberately small subset of
``autolens_profiling/_profile_cli.py``): this repo
renders figures, it does not time anything, so only the pieces the simulators and
the ``scripts/<domain>/visualization.py`` producers need are kept:

- ``repo_root()`` — walk up from any file to the directory holding ``ruff.toml``
  (the depth-proof repo-root sentinel), so scripts work from any nesting level.
- ``bootstrap_sys_path()`` — put the repo root and ``scripts/misc/`` on
  ``sys.path`` so ``_viz_cli`` / ``simulators`` import by name.
- ``dataset_path(dataset_type, dataset_name)`` — ``<root>/dataset/<type>/<name>``.
- ``auto_simulate_if_missing(...)`` — shell out to
  ``scripts/misc/simulators/<type>.py --dataset <name>`` when a dataset is absent.
- ``mirror_to_scratch(domains)`` — copy ``scripts/<domain>/images/`` PNGs to the opt-in
  ``$PYAUTO_EYES_SCRATCH/<lib>/<domain>/`` for on-the-fly review (no-op when unset);
  also ``python _viz_cli.py scratch [domain ...]``. ``gallery/gallery_run.sh`` calls it.

Unlike the galaxy / lens siblings there is no ``instruments/`` package: the CCD
layouts (shape, injection regions, prescans / overscans) live in the simulators
themselves and are saved next to each dataset as ``layout.json``.

Typical use at the top of a producer::

    import sys
    from pathlib import Path

    for _p in Path(__file__).resolve().parents:
        if (_p / "ruff.toml").exists():
            sys.path.insert(0, str(_p))
            break
    from _viz_cli import auto_simulate_if_missing, dataset_path, repo_root
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def repo_root(start: Path | None = None) -> Path:
    """Return the autocti_visualization root (the directory containing ``ruff.toml``)."""
    here = Path(start if start is not None else __file__).resolve()
    for p in [here, *here.parents]:
        if (p / "ruff.toml").exists():
            return p
    raise RuntimeError("autocti_visualization root (ruff.toml) not found")


def bootstrap_sys_path() -> Path:
    """Put the repo root and ``scripts/misc`` on ``sys.path``; return the root."""
    root = repo_root()
    for p in (root, root / "scripts" / "misc"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    return root


def dataset_path(dataset_type: str, dataset_name: str) -> Path:
    """``<root>/dataset/<dataset_type>/<dataset_name>``."""
    return repo_root() / "dataset" / dataset_type / dataset_name


def auto_simulate_if_missing(
    dataset_dir: Path,
    *,
    dataset_type: str,
    dataset_name: str,
    workspace_root: Path | None = None,
) -> None:
    """If ``dataset_dir`` is missing, run the matching simulator script.

    ``dataset_type`` maps to ``scripts/misc/simulators/<dataset_type>.py``
    (``dataset_1d`` / ``imaging_ci``).

    The gate is a plain ``cti.json`` existence check (the simulators write it last,
    after every per-normalization FITS): the datasets are tracked in git so every
    figure is reproducible, and this hook never deletes or rewrites one.
    """
    if (Path(dataset_dir) / "cti.json").exists():
        return

    root = workspace_root if workspace_root is not None else repo_root()
    simulator_script = root / "scripts" / "misc" / "simulators" / f"{dataset_type}.py"
    if not simulator_script.exists():
        raise FileNotFoundError(
            f"Auto-simulate could not find simulator script at {simulator_script}."
        )

    print(
        f"  [auto-simulate] {dataset_dir} missing; invoking "
        f"scripts/misc/simulators/{dataset_type}.py --dataset {dataset_name}"
    )
    subprocess.run(
        [
            sys.executable,
            str(simulator_script),
            "--dataset",
            dataset_name,
            "--output-root",
            str(root),
        ],
        check=True,
    )


# The PyAutoEyes dashboard names this repo's section by its library import name, and the
# scratch mirror reuses that name: ``$PYAUTO_EYES_SCRATCH/<EYES_LIB>/<domain>/``.
EYES_LIB = "autocti"
EYES_SCRATCH_ENV = "PYAUTO_EYES_SCRATCH"


def mirror_to_scratch(domains: list[str] | None = None) -> Path | None:
    """Copy freshly rendered PNGs to the opt-in Eyes scratch folder; return its lib folder.

    For on-the-fly figure review before any PR or CI. When ``$PYAUTO_EYES_SCRATCH`` is
    unset this is a silent no-op returning ``None`` (so CI and other machines are
    untouched). Otherwise each domain's ``$PYAUTO_EYES_SCRATCH/<EYES_LIB>/<domain>/`` is
    deleted and refilled with every PNG under ``scripts/<domain>/images/`` (subpaths
    below ``images/`` kept), so no stale figure survives a re-render. ``domains=None``
    mirrors every domain that has an ``images/`` folder (``misc`` never does).
    """
    scratch = os.environ.get(EYES_SCRATCH_ENV)
    if not scratch:
        return None
    scripts = repo_root() / "scripts"
    if domains is None:
        domains = sorted(p.parent.name for p in scripts.glob("*/images") if p.parent.name != "misc")
    lib_dir = Path(scratch).expanduser() / EYES_LIB
    for domain in domains:
        images = scripts / domain / "images"
        if not images.is_dir():
            print(f"  [eyes-scratch] skip {domain}: no {images.relative_to(scripts.parent)}")
            continue
        dest = lib_dir / domain
        shutil.rmtree(dest, ignore_errors=True)
        pngs = sorted(images.rglob("*.png"))
        for png in pngs:
            target = dest / png.relative_to(images)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(png, target)
        print(f"  [eyes-scratch] {len(pngs)} PNGs -> {dest}")
    return lib_dir


if __name__ == "__main__":
    # ``python _viz_cli.py scratch [domain ...]`` — mirror rendered PNGs to the Eyes scratch.
    if len(sys.argv) < 2 or sys.argv[1] != "scratch":
        sys.exit("usage: python _viz_cli.py scratch [domain ...]")
    if mirror_to_scratch(sys.argv[2:] or None) is None:
        print(f"  [eyes-scratch] ${EYES_SCRATCH_ENV} is unset; nothing mirrored")
