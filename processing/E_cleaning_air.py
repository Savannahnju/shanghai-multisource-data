# -*- coding: utf-8 -*-
"""
================================================================================
E_cleaning_air.py —— 空气质量数据清洗（优先级 P0-1，D/C/B 三方共用）
================================================================================

【输入】
  <team-data>/空气质量、环境指数/2017年各区降尘量与PM2.5月均浓度.xlsx
      Sheet1  2017年降尘量月度对比   16 区 × 12 月   -> 供 B 的 Q1
      Sheet2  2017年PM2.5月度对比    16 区 × 12 月   -> 供 B 的 Q1
      Sheet3  2024-2025年上海市空气质量 384 行 × 7 列 -> 供 C 的 Q2 / D 的 Q3
  <team-data>/空气质量、环境指数/zenedo-上海空气质量数据集.zip
      air_quality_historical.csv（全市日尺度，仅趋势参照，不进区级融合）

【输出】
  data/cleaned/cleaned_air_monthly.csv       Sheet3 清洗后全量 384 行
  data/processed/air_annual_2024.csv         16 行，2024 区年均值   -> D 的 Q3
  data/processed/air_annual_2024_2025.csv    16 行，两年区均值      -> C 的 Q2
  data/processed/air_2017_long.csv           192 行，2017 区×月长表 -> B 的 Q1
  data/processed/air_2017_q1_may_aug.csv      64 行，Q1 窗口 5–8 月
  data/processed/air_city_monthly.csv        Zenodo 全市月度（参照）

【口径规则】
  1. 区名按标准 2.3 标准化，并与区划图层、年鉴三方 16/16 校验；
  2. 年度聚合 = 12 个月简单平均（非日加权，与描述性分析口径一致）；
  3. 2017 两 sheet 与 2024-25 数据年份、指标均不同，严禁混用；
  4. 奉贤 11/12 月降尘量（12.5、9.3）标注可疑，不删除（不影响 Q1 窗口）；
  5. 降尘量单位源表未标注，按 **t/km²·月（吨/平方公里·月）** 处理——该口径经 D 的数据源说明确认。

【口径提示：道路PM10 不是环境空气 PM10】
  Sheet3 的「道路PM10」按上海市生态环境局月报表注，是**移动监测车沿地面道路
  （不含高架和快速路，每条路每月途经 ≥5 次）测得的区级月均浓度**，
  与 AQI 优良率 / PM2.5 / O3 所用的国控固定点位**不是同一监测体系**；
  它代表"道路扬尘暴露"，数值天然高于环境空气 PM10（本数据 道路PM10/PM2.5
  比值中位 3.18），且移动监测覆盖道路条数逐月不同，跨期比较宜看趋势。

【运行】
  python processing/E_cleaning_air.py
  python processing/E_cleaning_air.py --team-data "D:\\团队数据\\data"
================================================================================
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from E_common import (  # noqa: E402
    DISTRICTS_16,
    check_district_triple,
    clean_ws,
    ensure_dir,
    find_district_file,
    is_header_row,
    is_total,
    log,
    missing_report,
    normalize_district,
    project_root,
    range_check,
    read_zip_csv,
    section,
    standardize_columns,
    write_csv,
)

SHEET_DUST = "2017年降尘量月度对比"
SHEET_PM25 = "2017年PM2.5月度对比"
SHEET_2425 = "2024-2025年上海市空气质量"

# Sheet3 指标列名 -> 输出列名（统一"区年均/两年均值"语义）
COLS_2425 = {
    "AQI优良率(%)": "AQI优良率",
    "PM2.5(μg/m³)": "PM2.5",
    "O3(μg/m³)": "O3",
    "道路PM10(μg/m³)": "道路PM10",
}
# 精度：占比 2 位、浓度 1 位（标准 2.9）
ROUND = {"AQI优良率": 2, "PM2.5": 1, "O3": 1, "道路PM10": 1}


# ---------------------------------------------------------------- 解析

def parse_2017_sheet(path: Path, sheet: str, value_name: str) -> pd.DataFrame:
    """
    2017 年宽表（16 区 × 12 月）转长表。
    表头在第 0 行（区名 / 1月 ... 12月），数据 1–16 行。
    """
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    header = [clean_ws(c) for c in raw.iloc[0].tolist()]
    body = raw.iloc[1:].copy()
    body.columns = header

    df = body.rename(columns={header[0]: "区名"})
    df = df.loc[:, ~df.columns.duplicated()]

    # 去掉汇总/空行
    df["区名"] = df["区名"].map(normalize_district)
    df = df[~df["区名"].map(is_total)]
    df = df[df["区名"] != ""]

    month_cols = [c for c in df.columns if re.fullmatch(r"\d{1,2}月", str(c))]
    long = df.melt(id_vars="区名", value_vars=month_cols,
                   var_name="月份", value_name=value_name)
    long["月份"] = long["月份"].str.replace("月", "", regex=False).astype(int)
    long["年份"] = 2017
    return long[["年份", "月份", "区名", value_name]]


def parse_2425_sheet(path: Path) -> pd.DataFrame:
    """2024-2025 年区×月空气质量表（384 行）。"""
    df = pd.read_excel(path, sheet_name=SHEET_2425)
    df = standardize_columns(df)
    df["区名"] = df["区名"].map(normalize_district)
    for c in COLS_2425:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


# ---------------------------------------------------------------- 校验

def validate_2425(df: pd.DataFrame) -> pd.DataFrame:
    """值域校验并生成 is_outlier 标记（仅标记，不删除）。"""
    log("  [值域校验]")
    flags = pd.DataFrame(index=df.index)
    # 硬规则：占比 0–100，浓度 ≥ 0
    for src, out in COLS_2425.items():
        lo, hi = 0.0, (100.0 if out == "AQI优良率" else None)
        bad = range_check(df, src, lo, hi)
        flags[f"越界_{out}"] = bad
        log(f"    {out}: 越界 {int(bad.sum())} 条  "
            f"(min={df[src].min():.1f}, max={df[src].max():.1f})")
    # 统计规则：IQR 仅标记
    for src, out in COLS_2425.items():
        q1, q3 = df[src].quantile(0.25), df[src].quantile(0.75)
        iqr = q3 - q1
        f = (df[src] < q1 - 1.5 * iqr) | (df[src] > q3 + 1.5 * iqr)
        flags[f"IQR异常_{out}"] = f
        log(f"    {out}: IQR 异常标记 {int(f.sum())} 条（不删除）")
    return flags


# ---------------------------------------------------------------- 主流程

def main() -> int:
    ap = argparse.ArgumentParser(description="空气质量数据清洗（P0-1）")
    ap.add_argument("--team-data", default=None,
                    help="团队原始数据目录（默认：环境变量 SH_TEAM_DATA 或相对推导）")
    ap.add_argument("--cleaned", default=None, help="清洗后全量输出目录")
    ap.add_argument("--processed", default=None, help="中间产物输出目录")
    args = ap.parse_args()

    root = project_root()
    from E_common import default_team_data
    team = Path(args.team_data) if args.team_data else default_team_data()
    air_dir = team / "空气质量、环境指数"
    cleaned = Path(args.cleaned) if args.cleaned else root / "data" / "cleaned"
    processed = Path(args.processed) if args.processed else root / "data" / "processed"
    ensure_dir(cleaned)
    ensure_dir(processed)

    xlsx = air_dir / "2017年各区降尘量与PM2.5月均浓度.xlsx"
    zipf = air_dir / "zenedo-上海空气质量数据集.zip"
    if not xlsx.exists():
        log(f"[错误] 找不到空气 xlsx：{xlsx}\n请用 --team-data 指定团队数据目录")
        return 1

    # ---------- Sheet3：2024-2025（主表） ----------
    section("P0-1 空气质量 · Sheet3（2024-2025，C 的 Q2 / D 的 Q3）")
    d3 = parse_2425_sheet(xlsx)
    log(f"  原始：{d3.shape[0]} 行 × {d3.shape[1]} 列")
    log(f"  区名唯一数：{d3['区名'].nunique()}；年份：{sorted(d3['年份'].unique())}")

    # 结构校验 = 16 区 × 24 月
    expect = 16 * 24
    log(f"  结构校验：{len(d3)} 行 {'==' if len(d3) == expect else '!='} 期望 {expect}")

    # 重复值（主键 区名+年份+月份）
    key = ["区名", "年份", "月份"]
    dup = d3.duplicated(subset=key, keep="first")
    if dup.sum():
        d3 = d3[~dup].copy()
        log(f"  [重复值] 主键 {key} 重复 {int(dup.sum())} 条，已保留首条")
    else:
        log(f"  [重复值] 主键 {key} 无重复")

    # 缺失
    mr = missing_report(d3)
    log("  [缺失值]\n" + mr.to_string(index=False))

    # 值域
    flags = validate_2425(d3)
    d3 = pd.concat([d3, flags], axis=1)

    # 补年月列
    d3["年月"] = d3["年份"].astype(str) + "-" + d3["月份"].astype(str).str.zfill(2)

    # 精度
    for src, out in COLS_2425.items():
        d3[src] = d3[src].round(ROUND[out])

    out_cols = ["年份", "月份", "年月", "区名"] + list(COLS_2425) + list(flags.columns)
    monthly = d3[out_cols].sort_values(["年份", "月份", "区名"]).reset_index(drop=True)
    write_csv(monthly, cleaned / "cleaned_air_monthly.csv")

    # ---------- 年度聚合 ----------
    log("\n  [年度聚合] 口径：12 个月简单平均")

    def annual(sub: pd.DataFrame, year_label: str) -> pd.DataFrame:
        g = sub.groupby("区名", as_index=False)[list(COLS_2425)].mean()
        for src, out in COLS_2425.items():
            g[src] = g[src].round(ROUND[out])
        g = g.rename(columns=COLS_2425)
        g.insert(0, "年份", year_label)
        # 固定 16 区顺序
        g["_o"] = g["区名"].map({d: i for i, d in enumerate(DISTRICTS_16)})
        g = g.sort_values("_o").drop(columns="_o").reset_index(drop=True)
        return g

    a2024 = annual(d3[d3["年份"] == 2024], "2024")
    a2425 = annual(d3, "2024-2025")
    write_csv(a2024, processed / "air_annual_2024.csv")
    write_csv(a2425, processed / "air_annual_2024_2025.csv")

    # ---------- Sheet1/2：2017（B 的 Q1） ----------
    section("P0-1 空气质量 · Sheet1/2（2017，B 的 Q1）")
    dust = parse_2017_sheet(xlsx, SHEET_DUST, "降尘量")
    pm = parse_2017_sheet(xlsx, SHEET_PM25, "PM2.5")
    y2017 = dust.merge(pm, on=["年份", "月份", "区名"], how="outer")
    log(f"  降尘量 {len(dust)} 行；PM2.5 {len(pm)} 行；合并后 {len(y2017)} 行")
    log("  [缺失值]\n" + missing_report(y2017).to_string(index=False))

    # 可疑值标注（奉贤 11/12 月降尘量约为其他月 2–3 倍）
    y2017["降尘量_可疑"] = iqr_mask(y2017["降尘量"])
    n_susp = int(y2017["降尘量_可疑"].sum())
    if n_susp:
        ex = y2017.loc[y2017["降尘量_可疑"], ["区名", "月份", "降尘量"]]
        log(f"  [可疑值] 降尘量 IQR 异常 {n_susp} 条（标注不删除）：")
        log(ex.head(10).to_string(index=False))

    y2017 = y2017.sort_values(["月份", "区名"]).reset_index(drop=True)
    write_csv(y2017[["年份", "月份", "区名", "降尘量", "PM2.5", "降尘量_可疑"]],
              processed / "air_2017_long.csv")

    q1 = y2017[y2017["月份"].between(5, 8)].reset_index(drop=True)
    write_csv(q1[["年份", "月份", "区名", "降尘量", "PM2.5", "降尘量_可疑"]],
              processed / "air_2017_q1_may_aug.csv")
    log(f"  Q1 窗口（2017-05~08）：{len(q1)} 行 = 16 区 × 4 月")

    # ---------- Zenodo 补充 ----------
    section("P0-1 空气质量 · Zenodo 全市历史（趋势参照，不进区级融合）")
    if zipf.exists():
        z = read_zip_csv(zipf, "air_quality_historical.csv")
        z["date"] = pd.to_datetime(z["date"], errors="coerce")
        zc = z[(z["date"] >= "2024-01-01") & (z["date"] <= "2025-12-31")].copy()
        zc["年月"] = zc["date"].dt.strftime("%Y-%m")
        out = zc.groupby("年月", as_index=False).agg(
            PM2_5=("pm2_5", "mean"), PM10=("pm10", "mean"),
            O3=("ozone", "mean"), AQI_US=("us_aqi", "mean"))
        for c in ["PM2_5", "PM10", "O3", "AQI_US"]:
            out[c] = out[c].round(1)
        write_csv(out, processed / "air_city_monthly.csv")
        log(f"  全量 {len(z)} 日 → 截取 2024-2025 {len(zc)} 日 → 月度 {len(out)} 行")
    else:
        log(f"  [跳过] 未找到 {zipf.name}")

    # ---------- 三方区名校验 ----------
    section("区名三方校验（区划 / 年鉴 / 空气）")
    sets = {"空气": set(d3["区名"].unique())}
    # 年鉴
    yb_dir = team / "统计年鉴气象、绿化数据（2024年）"
    yb = yb_dir / "各区绿地面积.xls"
    if yb.exists():
        raw = pd.read_excel(yb, header=None)
        names = [normalize_district(v) for v in raw.iloc[:, 0].tolist()]
        # 剔除汇总行（总计/全市）与表头行（地 区）、表标题行（表10.17 ...）
        names = [n for n in names if n and not is_total(n) and not is_header_row(n)]
        sets["年鉴"] = set(names)
    # 区划
    dj = find_district_file(team)
    if dj is not None:
        if Path(dj).suffix.lower() == ".shp":
            import shapefile
            with shapefile.Reader(str(dj)) as r:
                fl = [f[0] for f in r.fields[1:]]
                names = {normalize_district(dict(zip(fl, sr.record)).get("district"))
                         for sr in r.shapeRecords()}
        else:
            import json
            feat = json.load(open(dj, encoding="utf-8"))["features"]
            names = {normalize_district(f["properties"].get("district")) for f in feat}
        sets["区划"] = names
    check_district_triple(sets, label="")

    section("P0-1 空气质量清洗完成")
    return 0


def iqr_mask(s: pd.Series, k: float = 1.5) -> pd.Series:
    """IQR 异常标记（局部实现，避免额外依赖）。"""
    v = pd.to_numeric(s, errors="coerce")
    q1, q3 = v.quantile(0.25), v.quantile(0.75)
    iqr = q3 - q1
    if pd.isna(iqr) or iqr == 0:
        return pd.Series(False, index=s.index)
    return ((v < q1 - k * iqr) | (v > q3 + k * iqr)).fillna(False)


if __name__ == "__main__":
    raise SystemExit(main())
