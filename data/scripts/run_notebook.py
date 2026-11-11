"""Execute a notebook top to bottom in place (T12 verification).

Usage (from the repository root):
    python data/scripts/run_notebook.py data/notebooks/eda.ipynb

Fails with a non-zero exit code if any cell raises.
nbclient API: https://github.com/jupyter/nbclient/blob/main/docs/client.rst
"""

import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient


def main(path: str) -> int:
    nb_path = Path(path).resolve()
    nb = nbformat.read(nb_path, as_version=4)
    NotebookClient(nb, timeout=600, resources={"metadata": {"path": str(nb_path.parent)}}).execute()
    nbformat.write(nb, nb_path)
    print(f"executed {len(nb.cells)} cells without error: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
