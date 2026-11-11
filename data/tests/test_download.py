import json

import pytest
from download import DATASETS, DownloadError, download_all


def fake_fetch(files):
    """Stand-in for kagglehub.dataset_download: writes files into output_dir."""

    def fetch(handle, output_dir):
        for name, content in files[handle].items():
            (output_dir / name).write_text(content)
        return str(output_dir)

    return fetch


def test_downloads_each_dataset_into_its_own_folder_and_writes_manifest(tmp_path):
    files = {"owner/a": {"train.csv": "x,y\n1,2\n"}, "owner/b": {"desc.csv": "d\n"}}
    datasets = {"owner/a": "dataset_a", "owner/b": "dataset_b"}

    manifest = download_all(datasets, tmp_path, fetch_fn=fake_fetch(files))

    assert (tmp_path / "dataset_a" / "train.csv").read_text() == "x,y\n1,2\n"
    assert (tmp_path / "dataset_b" / "desc.csv").exists()
    on_disk = json.loads((tmp_path / "MANIFEST.json").read_text())
    assert on_disk == manifest
    entry = manifest["dataset_a"]
    assert entry["source"] == "kaggle:owner/a"
    assert entry["files"]["train.csv"]["bytes"] == 8
    assert len(entry["files"]["train.csv"]["sha256"]) == 64


def test_failed_download_names_the_dataset_and_suggests_a_fix(tmp_path):
    def broken_fetch(handle, output_dir):
        raise OSError("network unreachable")

    with pytest.raises(DownloadError) as exc:
        download_all({"owner/a": "dataset_a"}, tmp_path, fetch_fn=broken_fetch)

    message = str(exc.value)
    assert "owner/a" in message
    assert "network unreachable" in message
    assert "KAGGLE_API_TOKEN" in message


def test_manifest_skips_hidden_bookkeeping_files(tmp_path):
    files = {"owner/a": {"train.csv": "x\n", ".complete": ""}}

    manifest = download_all({"owner/a": "dataset_a"}, tmp_path, fetch_fn=fake_fetch(files))

    assert list(manifest["dataset_a"]["files"]) == ["train.csv"]


def test_default_datasets_are_pinned_kaggle_versions():
    assert DATASETS == {
        "kaushil268/disease-prediction-using-machine-learning/versions/1": (
            "kaggle_disease_prediction"
        ),
        "itachi9604/disease-symptom-description-dataset/versions/2": ("kaggle_symptom_description"),
    }
