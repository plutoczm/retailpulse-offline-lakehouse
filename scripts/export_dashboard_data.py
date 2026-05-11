"""Export ADS Parquet tables to a compact JSON payload for the dashboard."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export RetailPulse ADS metrics for dashboard rendering.")
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--external-root", default="external_data/synerise-recsys-2025/extracted")
    parser.add_argument("--output", default="dashboard/data/dashboard.json")
    parser.add_argument("--topn", type=int, default=10)
    return parser.parse_args()


def read_parquet_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def normalize_dt(df: pd.DataFrame) -> pd.DataFrame:
    if not df.empty and "dt" in df.columns:
        df = df.copy()
        df["dt"] = df["dt"].astype(str)
    return df


def latest_dt(*frames: pd.DataFrame) -> str | None:
    values: list[str] = []
    for frame in frames:
        if not frame.empty and "dt" in frame.columns:
            values.extend(frame["dt"].dropna().astype(str).tolist())
    return max(values) if values else None


def latest_non_sparse_dt(df: pd.DataFrame, count_col: str = "event_count") -> str | None:
    if df.empty or "dt" not in df.columns:
        return None
    if count_col not in df.columns:
        return latest_dt(df)
    max_count = float(df[count_col].max() or 0)
    if max_count <= 0:
        return latest_dt(df)
    dense = df[df[count_col] >= max_count * 0.1]
    return latest_dt(dense if not dense.empty else df)


def clean_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 6)
    return value


def records(df: pd.DataFrame, limit: int | None = None) -> list[dict[str, Any]]:
    if limit is not None:
        df = df.head(limit)
    return [{key: clean_value(value) for key, value in row.items()} for row in df.to_dict("records")]


def sort_latest(df: pd.DataFrame, dt: str | None, sort_col: str, topn: int) -> pd.DataFrame:
    if df.empty:
        return df
    current = df[df["dt"].astype(str) == dt] if dt and "dt" in df.columns else df
    if sort_col in current.columns:
        current = current.sort_values(sort_col, ascending=False)
    elif "rank_no" in current.columns:
        current = current.sort_values("rank_no")
    return current.head(topn)


def build_payload(data_root: Path, topn: int) -> dict[str, Any]:
    ads = data_root / "ads"
    tables = {
        "daily": normalize_dt(read_parquet_table(ads / "ads_retail_dashboard_daily")),
        "product_topn": normalize_dt(read_parquet_table(ads / "ads_product_topn")),
        "category_topn": normalize_dt(read_parquet_table(ads / "ads_category_topn")),
        "shop_rank": normalize_dt(read_parquet_table(ads / "ads_shop_rank")),
        "retention": normalize_dt(read_parquet_table(ads / "ads_user_retention")),
        "rfm": normalize_dt(read_parquet_table(ads / "ads_rfm_user_segment")),
        "refund": normalize_dt(read_parquet_table(ads / "ads_refund_analysis")),
        "inventory": normalize_dt(read_parquet_table(ads / "ads_inventory_turnover")),
        "synerise_daily": normalize_dt(read_parquet_table(ads / "ads_synerise_behavior_dashboard_daily")),
        "synerise_event_type": normalize_dt(read_parquet_table(ads / "ads_synerise_event_type_trend")),
        "synerise_product_topn": normalize_dt(read_parquet_table(ads / "ads_synerise_product_topn")),
        "synerise_category_topn": normalize_dt(read_parquet_table(ads / "ads_synerise_category_topn")),
    }
    current_dt = latest_dt(
        tables["daily"],
        tables["product_topn"],
        tables["category_topn"],
        tables["shop_rank"],
        tables["retention"],
        tables["rfm"],
        tables["refund"],
        tables["inventory"],
    )
    synerise_dt = latest_non_sparse_dt(tables["synerise_daily"])

    daily = tables["daily"].sort_values("dt") if not tables["daily"].empty else pd.DataFrame()
    latest_daily = daily[daily["dt"] == current_dt].tail(1) if current_dt and not daily.empty else pd.DataFrame()
    kpis = latest_daily.iloc[0].to_dict() if not latest_daily.empty else {}
    synerise_daily = tables["synerise_daily"].sort_values("dt") if not tables["synerise_daily"].empty else pd.DataFrame()
    synerise_latest = (
        synerise_daily[synerise_daily["dt"] == synerise_dt].tail(1) if synerise_dt and not synerise_daily.empty else pd.DataFrame()
    )
    synerise_kpis = synerise_latest.iloc[0].to_dict() if not synerise_latest.empty else {}

    rfm = tables["rfm"]
    if not rfm.empty and "user_segment" in rfm.columns:
        rfm_segment = (
            rfm.groupby("user_segment", dropna=False)
            .agg(user_count=("user_id", "count"), monetary=("monetary", "sum"))
            .reset_index()
            .sort_values("user_count", ascending=False)
        )
    else:
        rfm_segment = pd.DataFrame()

    retention = tables["retention"]
    if not retention.empty:
        retention_latest = retention[retention["dt"] == current_dt] if current_dt and "dt" in retention.columns else retention
        retention_latest = retention_latest.sort_values(["cohort_dt", "day_diff"]) if "cohort_dt" in retention_latest.columns else retention_latest
    else:
        retention_latest = retention

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data_root": str(data_root),
        "latest_dt": current_dt,
        "kpis": {key: clean_value(value) for key, value in kpis.items()},
        "daily": records(daily),
        "product_topn": records(sort_latest(tables["product_topn"], current_dt, "sales_amount", topn)),
        "category_topn": records(sort_latest(tables["category_topn"], current_dt, "sales_amount", topn)),
        "shop_rank": records(sort_latest(tables["shop_rank"], current_dt, "sales_amount", topn)),
        "retention": records(retention_latest, limit=topn * 2),
        "rfm_segment": records(rfm_segment),
        "refund_analysis": records(sort_latest(tables["refund"], current_dt, "refund_amount", topn)),
        "inventory_turnover": records(sort_latest(tables["inventory"], current_dt, "inventory_turnover_rate", topn)),
        "synerise_latest_dt": synerise_dt,
        "synerise_kpis": {key: clean_value(value) for key, value in synerise_kpis.items()},
        "synerise_daily": records(synerise_daily),
        "synerise_event_type": records(tables["synerise_event_type"]),
        "synerise_product_topn": records(sort_latest(tables["synerise_product_topn"], synerise_dt, "pay_event_count", topn)),
        "synerise_category_topn": records(sort_latest(tables["synerise_category_topn"], synerise_dt, "pay_event_count", topn)),
        "synerise_product_topn_all": records(tables["synerise_product_topn"]),
        "synerise_category_topn_all": records(tables["synerise_category_topn"]),
    }
    return payload


def public_dataset_profile(external_root: Path) -> list[dict[str, Any]]:
    if not external_root.exists():
        return []
    profile: list[dict[str, Any]] = []
    for path in sorted(external_root.glob("*.parquet")):
        parquet_file = pq.ParquetFile(path)
        profile.append(
            {
                "table": path.name,
                "rows": parquet_file.metadata.num_rows,
                "row_groups": parquet_file.metadata.num_row_groups,
                "size_mb": round(path.stat().st_size / 1024 / 1024, 1),
                "columns": parquet_file.schema.names,
            }
        )
    return profile


def main() -> None:
    args = parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload(Path(args.data_root), args.topn)
    payload["public_dataset"] = public_dataset_profile(Path(args.external_root))
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Dashboard data exported to {output}")


if __name__ == "__main__":
    main()
