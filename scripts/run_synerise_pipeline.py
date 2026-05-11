"""Run Synerise public dataset ODS and DWD jobs."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path


LOGGER = logging.getLogger("retailpulse.run_synerise_pipeline")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Synerise ODS/DWD pipeline.")
    parser.add_argument("--input", default="external_data/synerise-recsys-2025/extracted")
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--dt")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--tables", default="all")
    parser.add_argument("--sample-fraction", type=float, default=0.0)
    parser.add_argument("--limit-per-table", type=int, default=0)
    parser.add_argument("--shuffle-partitions", type=int, default=96)
    parser.add_argument("--output-partitions", type=int, default=96)
    parser.add_argument("--deduplicate", action="store_true")
    parser.add_argument("--broadcast-products", action="store_true")
    parser.add_argument("--skip-ods", action="store_true")
    parser.add_argument("--skip-dwd", action="store_true")
    parser.add_argument("--skip-dws", action="store_true")
    parser.add_argument("--skip-ads", action="store_true")
    return parser.parse_args()


def run_command(command: list[str]) -> None:
    LOGGER.info("Running: %s", " ".join(command))
    subprocess.run(command, check=True)


def append_optional(command: list[str], name: str, value: object | None) -> None:
    if value is not None and value != "":
        command.extend([name, str(value)])


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    data_root = Path(args.data_root)

    if not args.skip_ods:
        ods_cmd = [
            sys.executable,
            "jobs/synerise_ods_load.py",
            "--input",
            args.input,
            "--output",
            str(data_root / "ods"),
            "--tables",
            args.tables,
            "--shuffle-partitions",
            str(args.shuffle_partitions),
            "--output-partitions",
            str(args.output_partitions),
        ]
        append_optional(ods_cmd, "--dt", args.dt)
        append_optional(ods_cmd, "--start-date", args.start_date)
        append_optional(ods_cmd, "--end-date", args.end_date)
        if args.sample_fraction:
            ods_cmd.extend(["--sample-fraction", str(args.sample_fraction)])
        if args.limit_per_table:
            ods_cmd.extend(["--limit-per-table", str(args.limit_per_table)])
        run_command(ods_cmd)

    if not args.skip_dwd:
        dwd_cmd = [
            sys.executable,
            "jobs/synerise_dwd_behavior.py",
            "--input",
            str(data_root / "ods"),
            "--output",
            str(data_root / "dwd"),
            "--tables",
            args.tables,
            "--shuffle-partitions",
            str(args.shuffle_partitions),
            "--output-partitions",
            str(args.output_partitions),
        ]
        append_optional(dwd_cmd, "--dt", args.dt)
        append_optional(dwd_cmd, "--start-date", args.start_date)
        append_optional(dwd_cmd, "--end-date", args.end_date)
        if args.limit_per_table:
            dwd_cmd.extend(["--limit-per-table", str(args.limit_per_table)])
        if args.deduplicate:
            dwd_cmd.append("--deduplicate")
        if args.broadcast_products:
            dwd_cmd.append("--broadcast-products")
        run_command(dwd_cmd)

    if not args.skip_dws:
        dws_cmd = [
            sys.executable,
            "jobs/synerise_dws_aggregate.py",
            "--input",
            str(data_root),
            "--output",
            str(data_root / "dws"),
            "--shuffle-partitions",
            str(args.shuffle_partitions),
            "--output-partitions",
            str(args.output_partitions),
        ]
        append_optional(dws_cmd, "--dt", args.dt)
        append_optional(dws_cmd, "--start-date", args.start_date)
        append_optional(dws_cmd, "--end-date", args.end_date)
        run_command(dws_cmd)

    if not args.skip_ads:
        ads_cmd = [
            sys.executable,
            "jobs/synerise_ads_metrics.py",
            "--input",
            str(data_root),
            "--output",
            str(data_root / "ads"),
            "--shuffle-partitions",
            str(args.shuffle_partitions),
        ]
        append_optional(ads_cmd, "--dt", args.dt)
        append_optional(ads_cmd, "--start-date", args.start_date)
        append_optional(ads_cmd, "--end-date", args.end_date)
        run_command(ads_cmd)

    LOGGER.info("Synerise pipeline finished. Data root: %s", data_root)


if __name__ == "__main__":
    main()
