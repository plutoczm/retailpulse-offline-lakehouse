"""Download public enterprise-scale ecommerce datasets.

The default dataset is the RecSys Challenge 2025 / Synerise online retail
dataset. It is a real behavior dataset and is stored under the project root
in ``external_data/`` so it stays separate from generated RetailPulse raw CSVs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import tarfile
import time
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


LOGGER = logging.getLogger("retailpulse.download_public_data")


@dataclass(frozen=True)
class PublicDataset:
    name: str
    title: str
    url: str
    expected_bytes: int
    archive_name: str
    description: str
    source_page: str


DATASETS = {
    "synerise-recsys-2025": PublicDataset(
        name="synerise-recsys-2025",
        title="RecSys Challenge 2025 / Synerise Online Retail Dataset",
        url="https://data.recsys.synerise.com/dataset/synerise_dataset.tar.gz",
        expected_bytes=2_062_884_710,
        archive_name="synerise_dataset.tar.gz",
        description=(
            "Real online retail behavior dataset containing six months of user-item interactions, "
            "including purchases, add-to-cart, remove-from-cart, page visits, search and item properties."
        ),
        source_page="https://recsys.synerise.com/data-set",
    )
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download public datasets for RetailPulse.")
    parser.add_argument("--dataset", choices=sorted(DATASETS), default="synerise-recsys-2025")
    parser.add_argument("--root", default="external_data", help="Directory under project root.")
    parser.add_argument("--extract", action="store_true", help="Extract the downloaded tar.gz archive.")
    parser.add_argument("--force", action="store_true", help="Redownload even if the archive exists.")
    parser.add_argument("--chunk-mb", type=int, default=8)
    return parser.parse_args()


def format_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024 or unit == "TB":
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(dataset: PublicDataset, target: Path, force: bool, chunk_size: int) -> None:
    if target.exists() and not force:
        LOGGER.info("Archive already exists: %s (%s)", target, format_size(target.stat().st_size))
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()

    LOGGER.info("Downloading %s", dataset.url)
    LOGGER.info("Expected size: %s", format_size(dataset.expected_bytes))
    started = time.time()
    downloaded = 0

    try:
        import requests
    except ImportError:
        request = urllib.request.Request(dataset.url, headers={"User-Agent": "RetailPulseDownloader/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response, tmp.open("wb") as fh:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                fh.write(chunk)
                downloaded = log_progress(downloaded + len(chunk), started, chunk_size)
    else:
        with requests.get(
            dataset.url,
            stream=True,
            timeout=(30, 120),
            headers={"User-Agent": "RetailPulseDownloader/1.0"},
        ) as response:
            response.raise_for_status()
            with tmp.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    downloaded = log_progress(downloaded + len(chunk), started, chunk_size)

    tmp.replace(target)
    actual_size = target.stat().st_size
    if actual_size < dataset.expected_bytes * 0.95:
        raise RuntimeError(f"Downloaded file looks too small: {format_size(actual_size)}")
    LOGGER.info("Download complete: %s (%s)", target, format_size(actual_size))


def log_progress(downloaded: int, started: float, chunk_size: int) -> int:
    if downloaded <= chunk_size or downloaded % (256 * 1024 * 1024) < chunk_size:
        elapsed = max(time.time() - started, 1)
        speed = downloaded / elapsed
        LOGGER.info("Downloaded %s at %s/s", format_size(downloaded), format_size(int(speed)))
    return downloaded


def safe_extract_tar_gz(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    destination_resolved = destination.resolve()
    LOGGER.info("Extracting %s to %s", archive, destination)
    with tarfile.open(archive, mode="r:gz") as tf:
        for member in tf.getmembers():
            target = (destination / member.name).resolve()
            if not str(target).startswith(str(destination_resolved)):
                raise RuntimeError(f"Unsafe archive member path: {member.name}")
        tf.extractall(destination)
    LOGGER.info("Extraction complete.")


def write_manifest(dataset: PublicDataset, dataset_dir: Path, archive: Path, extracted: bool) -> None:
    manifest = {
        **asdict(dataset),
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "archive_path": str(archive),
        "archive_bytes": archive.stat().st_size if archive.exists() else None,
        "archive_sha256": sha256_file(archive) if archive.exists() else None,
        "extracted": extracted,
        "extract_dir": str(dataset_dir / "extracted"),
    }
    manifest_path = dataset_dir / "dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    LOGGER.info("Manifest written: %s", manifest_path)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    dataset = DATASETS[args.dataset]
    dataset_dir = Path(args.root) / dataset.name
    archive = dataset_dir / dataset.archive_name

    download(dataset, archive, force=args.force, chunk_size=max(args.chunk_mb, 1) * 1024 * 1024)
    extracted = False
    if args.extract:
        safe_extract_tar_gz(archive, dataset_dir / "extracted")
        extracted = True
    write_manifest(dataset, dataset_dir, archive, extracted)
    LOGGER.info("Public dataset ready under %s", dataset_dir)


if __name__ == "__main__":
    main()
