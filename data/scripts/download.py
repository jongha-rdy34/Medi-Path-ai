"""Download the Kaggle fallback datasets into data/raw/ (gitignored).

Usage (from the repository root):
    pip install -r data/requirements.txt
    python data/scripts/download.py

Public Kaggle datasets download without credentials. If Kaggle asks for
authentication, set KAGGLE_API_TOKEN (https://www.kaggle.com/settings/api).
kagglehub API: https://github.com/Kaggle/kagglehub/blob/main/README.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[1] / "raw"

# Kaggle handle (pinned version, for reproducibility) -> folder name under data/raw/
DATASETS: dict[str, str] = {
    "kaushil268/disease-prediction-using-machine-learning/versions/1": (
        "kaggle_disease_prediction"
    ),
    "itachi9604/disease-symptom-description-dataset/versions/2": ("kaggle_symptom_description"),
}

FetchFn = Callable[[str, Path], str]


class DownloadError(RuntimeError):
    pass


def _kaggle_fetch(handle: str, output_dir: Path) -> str:
    import kagglehub

    return kagglehub.dataset_download(handle, output_dir=str(output_dir), force_download=True)


def _is_hidden(relative: Path) -> bool:
    """kagglehub leaves bookkeeping files such as .complete/...; they are not data."""
    return any(part.startswith(".") for part in relative.parts)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_all(
    datasets: dict[str, str], raw_dir: Path, fetch_fn: FetchFn = _kaggle_fetch
) -> dict:
    """Fetch every dataset into raw_dir/<folder> and write raw_dir/MANIFEST.json."""
    manifest: dict = {}
    for handle, folder in datasets.items():
        target = raw_dir / folder
        target.mkdir(parents=True, exist_ok=True)
        try:
            fetch_fn(handle, target)
        except Exception as exc:  # network, auth, or Kaggle-side errors
            raise DownloadError(
                f"Failed to download kaggle:{handle}: {exc}\n"
                "Check network access to kaggle.com. If authentication is required, "
                "set KAGGLE_API_TOKEN (https://www.kaggle.com/settings/api)."
            ) from exc
        manifest[folder] = {
            "source": f"kaggle:{handle}",
            "files": {
                str(p.relative_to(target)): {"bytes": p.stat().st_size, "sha256": _sha256(p)}
                for p in sorted(target.rglob("*"))
                if p.is_file() and not _is_hidden(p.relative_to(target))
            },
        }
    (raw_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    args = parser.parse_args()
    try:
        manifest = download_all(DATASETS, args.raw_dir)
    except DownloadError as exc:
        print(exc, file=sys.stderr)
        return 1
    for folder, entry in manifest.items():
        print(f"{folder} ({entry['source']})")
        for name, meta in entry["files"].items():
            print(f"  {name}  {meta['bytes']} bytes")
    print(f"Manifest: {args.raw_dir / 'MANIFEST.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
