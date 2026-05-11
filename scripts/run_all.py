"""Run the full RetailPulse local pipeline."""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


LOGGER = logging.getLogger("retailpulse.run_all")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RetailPulse data generation and Spark ETL pipeline.")
    parser.add_argument("--scale", default="tiny", choices=["tiny", "small", "default"])
    parser.add_argument("--start-date", default="2025-01-01")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--skip-generate", action="store_true")
    parser.add_argument("--skip-quality", action="store_true")
    return parser.parse_args()


def end_date(start_date: str, days: int) -> str:
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    return (start + timedelta(days=days - 1)).isoformat()


def run_command(command: list[str]) -> None:
    LOGGER.info("Running: %s", " ".join(command))
    subprocess.run(command, check=True)


def ensure_windows_hadoop_home() -> None:
    if os.name != "nt":
        return
    configured = os.environ.get("HADOOP_HOME")
    candidate = Path(configured).resolve() if configured else Path(".runtime/hadoop").resolve()
    if (candidate / "bin" / "winutils.exe").exists():
        os.environ["HADOOP_HOME"] = str(candidate)
        os.environ["hadoop.home.dir"] = str(candidate)
        hadoop_bin = str(candidate / "bin")
        if hadoop_bin not in os.environ.get("PATH", ""):
            os.environ["PATH"] = hadoop_bin + os.pathsep + os.environ.get("PATH", "")
        LOGGER.info("Using local HADOOP_HOME=%s", candidate)
    else:
        LOGGER.warning(
            "HADOOP_HOME is not set. On Windows, run scripts/setup_windows_spark.ps1 before Spark jobs."
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    ensure_windows_hadoop_home()
    root = Path(args.data_root)
    raw = root / "raw"
    end = end_date(args.start_date, args.days)
    dt = end

    commands: list[list[str]] = []
    if not args.skip_generate:
        commands.append(
            [
                sys.executable,
                "scripts/generate_data.py",
                "--output",
                str(raw),
                "--scale",
                args.scale,
                "--start-date",
                args.start_date,
                "--days",
                str(args.days),
            ]
        )
    commands.extend(
        [
            [
                sys.executable,
                "jobs/ods_load.py",
                "--input",
                str(raw),
                "--output",
                str(root / "ods"),
                "--start-date",
                args.start_date,
                "--end-date",
                end,
            ],
            [
                sys.executable,
                "jobs/dwd_clean.py",
                "--input",
                str(root / "ods"),
                "--output",
                str(root / "dwd"),
                "--start-date",
                args.start_date,
                "--end-date",
                end,
            ],
            [
                sys.executable,
                "jobs/dim_build.py",
                "--input",
                str(root),
                "--output",
                str(root / "dim"),
                "--dt",
                dt,
                "--start-date",
                args.start_date,
                "--end-date",
                end,
            ],
            [
                sys.executable,
                "jobs/dws_aggregate.py",
                "--input",
                str(root),
                "--output",
                str(root / "dws"),
                "--dt",
                dt,
                "--start-date",
                args.start_date,
                "--end-date",
                end,
            ],
            [
                sys.executable,
                "jobs/ads_metrics.py",
                "--input",
                str(root),
                "--output",
                str(root / "ads"),
                "--dt",
                dt,
                "--start-date",
                args.start_date,
                "--end-date",
                end,
            ],
        ]
    )
    if not args.skip_quality:
        commands.append(
            [
                sys.executable,
                "scripts/run_quality_checks.py",
                "--input",
                str(root),
                "--output",
                "reports/data_quality_report.md",
                "--start-date",
                args.start_date,
                "--end-date",
                end,
            ]
        )

    for command in commands:
        run_command(command)
    LOGGER.info("RetailPulse pipeline finished. Data root: %s, date range: %s to %s", root, args.start_date, end)


if __name__ == "__main__":
    main()
