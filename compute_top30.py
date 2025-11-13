from pathlib import Path
import sys
import pandas as pd
import numpy as np


def read_csv_with_fallback(path: Path):
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return pd.read_csv(path, encoding=enc, dtype={"证券代码": str})
        except UnicodeDecodeError:
            continue
    # last try without encoding hint
    return pd.read_csv(path, dtype={"证券代码": str})


def compute_top30(input_csv: Path, output_csv: Path) -> None:
    df = read_csv_with_fallback(input_csv)

    # Parse dates and coerce numeric columns
    if "日期" in df.columns:
        df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
    numeric_cols = ["现金流量比例", "股息率", "回购比例"]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Drop rows with missing key fields
    df = df.dropna(subset=["日期", "证券代码", "证券名称"])  # 保留核心标识

    # Z-score within each date for the three factors
    for c in numeric_cols:
        if c in df.columns:
            grp = df.groupby("日期")[c]
            mean_c = grp.transform("mean")
            std_c = grp.transform("std")  # sample std; if 0 -> set z=0
            z = (df[c] - mean_c) / std_c
            z = z.mask((std_c == 0) | (~np.isfinite(z)), 0.0)
            if c == "现金流量比例":
                df["现金流量得分"] = z
            elif c == "股息率":
                df["股息率得分"] = z
            elif c == "回购比例":
                df["回购得分"] = z

    # Equal-weight composite of z-scores
    df["复合得分"] = df[["现金流量得分", "股息率得分", "回购得分"]].mean(axis=1)

    # Pick top 30 per date by composite score (avoid groupby.apply warnings)
    df_sorted = df.sort_values(["日期", "复合得分", "证券代码"], ascending=[True, False, True])
    topn = df_sorted.groupby("日期", as_index=False, group_keys=False).head(30).reset_index(drop=True)

    # Select and rename columns for output
    out_cols = [
        "日期",
        "证券代码",
        "证券名称",
        "复合得分",
        "现金流量得分",
        "股息率得分",
        "回购得分",
        "现金流量比例",
        "股息率",
        "回购比例",
    ]
    out_cols = [c for c in out_cols if c in topn.columns]

    # Format scores to 6 decimals for stability
    for c in ["复合得分", "现金流量得分", "股息率得分", "回购得分"]:
        if c in topn.columns:
            topn[c] = topn[c].astype(float)

    topn.to_csv(output_csv, index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    base = Path(__file__).parent
    in_path = base / "价值策略因子数据【CSV】.csv"
    out_path = base / "选股结果_top30.csv"
    if len(sys.argv) >= 2:
        in_path = Path(sys.argv[1])
    if len(sys.argv) >= 3:
        out_path = Path(sys.argv[2])
    compute_top30(in_path, out_path)
    print(f"Wrote: {out_path}")
