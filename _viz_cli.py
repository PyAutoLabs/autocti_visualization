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
