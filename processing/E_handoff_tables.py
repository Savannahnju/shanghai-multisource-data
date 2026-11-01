# -*- coding: utf-8 -*-
"""
================================================================================
E_handoff_tables.py —— 生成 B / D 清洗要求中点名的「分析用宽表」
================================================================================

【输入】
  data/cleaned/cleaned_metro_daily_district.csv   区×日 客流（1,521 行）
  data/processed/metro_station_clean.csv          站点表（302 行，含区名）
  data/processed/air_2017_q1_may_aug.csv          2017 区×月 降尘量/PM2.5
  data/processed/air_annual_2024.csv              2024 区年均空气
  data/processed/air_annual_2024_2025.csv         2024–25 两年区均值
  data/cleaned/cleaned_green.csv                  区级绿地/植被/年鉴

【输出】
  data/cleaned/cleaned_metro_month_district.csv   B 的 Q1 宽表（区×月，52 行）
  data/cleaned/cleaned_green_analysis_wide.csv    D 的 Q3 宽表（16 区）

【口径】
  B：月份只取 5–8 月；总客流 = 进站 + 出站；日均 = 总 / 有效天数；
     客流强度 = 总客流 / 站点数；仅 13 个有站点区。
  D：植被为静态快照（2001–2022 汇总），故区级宽表为 16 行；
     空气取 2024 单年（对齐年鉴与植被），另附两年均值列备选。
================================================================================
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from E_common import DISTRICTS_16, log, project_root, section, write_csv


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def build_b(root: Path) -> None:
    section("B（Q1）· 区 × 月 客流宽表")
    c = root / "data" / "cleaned"
    p = root / "data" / "processed"

    daily = read_csv(c / "cleaned_metro_daily_district.csv")
    st = read_csv(p / "metro_station_clean.csv")
    st = st[st["区名"].isin(DISTRICTS_16)]
    n_station = st.groupby("区名").size().rename("站点数")

    daily["日期"] = pd.to_datetime(daily["日期"])
    daily["月份"] = daily["日期"].dt.month
    daily["日客流"] = daily["日进站量"] + daily["日出站量"]

    g = daily.groupby(["区名", "月份"], as_index=False).agg(
        地铁总客流=("日客流", "sum"),
        有效天数=("日客流", "size"),
    )
    g["地铁总客流"] = g["地铁总客流"].astype(int)
    g["地铁日均客流"] = (g["地铁总客流"] / g["有效天数"]).round(0)
    g["站点数"] = g["区名"].map(n_station).astype(int)
    g["客流强度"] = (g["地铁总客流"] / g["站点数"]).round(0)

    # 只保留 5–8 月（B 的分析窗口）
    g = g[g["月份"].between(5, 8)].copy()

    out = g[["区名", "月份", "地铁总客流", "地铁日均客流", "客流强度", "站点数", "有效天数"]]
    out = out.sort_values(["区名", "月份"]).reset_index(drop=True)
    write_csv(out, c / "cleaned_metro_month_district.csv")
    log(f"  共 {out['区名'].nunique()} 区 × 4 月 = {len(out)} 行"
        f"（应为 52）；列：{list(out.columns)}")
    log(f"  合计客流 {out['地铁总客流'].sum():,} 人次")


def build_b_station_month(root: Path) -> None:
    """B 的第七节还要求「站点 × 月」中间表备查，这里一并生成。"""
    section("B（Q1）· 站点 × 月 客流中间表")
    src = root / "data" / "cleaned" / "cleaned_metro.csv"
    cols = ["station", "日期", "站点名称", "区名", "inFlow", "outFlow"]
    parts = []
    for ch in pd.read_csv(src, encoding="utf-8-sig", usecols=cols, chunksize=500_000):
        ch["月份"] = pd.to_datetime(ch["日期"]).dt.month
        parts.append(ch)
    d = pd.concat(parts, ignore_index=True)
    d = d[d["月份"].between(5, 8)]
    g = d.groupby(["区名", "station", "站点名称", "月份"], as_index=False).agg(
        进站量=("inFlow", "sum"), 出站量=("outFlow", "sum"), 有效天数=("日期", "size"))
    g["进站量"] = g["进站量"].astype(int)
    g["出站量"] = g["出站量"].astype(int)
    g = g[["区名", "station", "站点名称", "月份", "进站量", "出站量", "有效天数"]]
    g = g.sort_values(["区名", "station", "月份"]).reset_index(drop=True)
    write_csv(g, root / "data" / "cleaned" / "cleaned_metro_station_month.csv")
    log(f"  {g['station'].nunique()} 站 × 4 月 = {len(g)} 行；列：{list(g.columns)}")


def build_d(root: Path) -> None:
    section("D（Q3）· 区级分析宽表（空气 + 植被 + 年鉴）")
    c = root / "data" / "cleaned"
    p = root / "data" / "processed"

    green = read_csv(c / "cleaned_green.csv")
    a24 = read_csv(p / "air_annual_2024.csv")
    a2425 = read_csv(p / "air_annual_2024_2025.csv")

    a2425 = a2425.rename(columns={
        "AQI优良率": "AQI优良率_两年均值",
        "PM2.5": "PM2.5_两年均值",
        "O3": "O3_两年均值",
        "道路PM10": "道路PM10_两年均值",
    }).drop(columns=["年份"])

    g = green.rename(columns={
        "遥感绿地占比均值_%": "绿地占比",
        "STL_AR1均值_剔除负值": "韧性_STL_AR1",
        "V2_AR1均值": "韧性_V2_AR1",
        "V2_VAR均值": "韧性_V2_VAR",
        "绿地面积(公顷)": "绿地面积",
        "人口密度(人/平方公里)": "人口密度",
    })[["区名", "绿地占比", "韧性_STL_AR1", "韧性_V2_AR1", "韧性_V2_VAR",
        "绿地面积", "人口密度", "有效绿地像元数"]]

    wide = (a24.merge(g, on="区名", how="outer")
              .merge(a2425, on="区名", how="outer"))
    wide = wide[["区名", "年份", "AQI优良率", "PM2.5", "O3", "道路PM10",
                 "绿地占比", "韧性_STL_AR1", "韧性_V2_AR1", "韧性_V2_VAR",
                 "绿地面积", "人口密度", "有效绿地像元数",
                 "AQI优良率_两年均值", "PM2.5_两年均值", "O3_两年均值",
                 "道路PM10_两年均值"]]
    wide["_o"] = wide["区名"].map({d: i for i, d in enumerate(DISTRICTS_16)})
    wide = wide.sort_values("_o").drop(columns="_o").reset_index(drop=True)

    write_csv(wide, c / "cleaned_green_analysis_wide.csv")
    n_ok = int(wide["绿地占比"].notna().sum())
    log(f"  {len(wide)} 区；有植被数据的 {n_ok} 区"
        f"（徐汇/静安/普陀 无有效像元，留空不补 0）")
    log(f"  列：{list(wide.columns)}")


def main() -> int:
    root = project_root()
    log(f"项目根目录：{root}")
    build_b(root)
    build_b_station_month(root)
    build_d(root)
    section("完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
