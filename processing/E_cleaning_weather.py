# -*- coding: utf-8 -*-
"""
================================================================================
E_cleaning_weather.py —— 小时气象 + 工作日历清洗（优先级 P1-5，B 的研究问题 1）
================================================================================

【输入】
  <team-data>/上海地铁客流量/shanghai_weatherHourly.csv  2,952 行 × 5 列
  <team-data>/上海地铁客流量/workday_calendar.csv        123 行 × 2 列

【输出】
  data/cleaned/cleaned_weather_hourly.csv   小时表（剔除 6 个不完整日后 2,808 行）
  data/cleaned/cleaned_weather_daily.csv   日尺度聚合（117 行，B 的分析主表）
  data/processed/workday_calendar_clean.csv

【清洗规则】
  1. date 形如 '20170501 00:00:00' -> 拆 `日期`（YYYY-MM-DD）+ `小时`（0–23）；
  2. **rain 口径判定**：实测 0–16.6、53 个唯一值，为连续量而**非 0/1 降雨标记**；
     按降水量处理，单位 mm（依 B 的数据源文档：rain = 小时降雨量 mm）；
  3. 字段拼写修正：isWorday -> isWorkday，值 0/1 映射为"工作日/非工作日"；
  4. 时间窗校验：必须与地铁一致（2017-05-01 ~ 08-31，123 × 24 = 2,952 行）；
  5. **与地铁同步剔除 6 个采集不完整日**，保证两侧时间窗一致（123 → 117 天）；
  6. 日聚合：日降水合计、日均温、日最高/最低温、日最大风速（**km/h**，
     依 B 的数据源文档：wind_speed_10m = 10 米风速 km/h，实测 0.72–33.99 亦吻合）；
  7. 单位：气温 ℃、体感温度 ℃、降水 mm、风速 km/h（与 Open-Meteo 默认一致）；
  8. 温度值域 -50~60 ℃、风速 ≥ 0、降水 ≥ 0。

【运行】
  python processing/E_cleaning_weather.py
================================================================================
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from E_common import (  # noqa: E402
    ensure_dir,
    log,
    missing_report,
    project_root,
    range_check,
    section,
    standardize_columns,
    write_csv,
)
from E_common import default_team_data  # noqa: E402

BAD_DATES = ["2017-05-04", "2017-05-08", "2017-05-09",
             "2017-06-16", "2017-06-27", "2017-06-28"]


def main() -> int:
    ap = argparse.ArgumentParser(description="小时气象+工作日历清洗（P1-5）")
    ap.add_argument("--team-data", default=None)
    ap.add_argument("--cleaned", default=None)
    ap.add_argument("--processed", default=None)
    args = ap.parse_args()

    root = project_root()
    team = Path(args.team_data) if args.team_data else default_team_data()
    metro_dir = team / "上海地铁客流量"
    cleaned = Path(args.cleaned) if args.cleaned else root / "data" / "cleaned"
    processed = Path(args.processed) if args.processed else root / "data" / "processed"
    ensure_dir(cleaned)
    ensure_dir(processed)

    # ---------- 工作日历 ----------
    section("P1-5 气象 · 工作日历")
    cal = standardize_columns(pd.read_csv(metro_dir / "workday_calendar.csv"))
    cal = cal.rename(columns={"isWorday": "isWorkday"})
    cal["日期"] = pd.to_datetime(cal["date"].astype(str), format="%Y%m%d").dt.strftime("%Y-%m-%d")
    cal["是否工作日"] = np.where(cal["isWorkday"] == 1, "工作日", "非工作日")
    cal_out = cal[["日期", "isWorkday", "是否工作日"]]
    log(f"  日历 {len(cal_out)} 天；工作日 {int((cal['isWorkday'] == 1).sum())} 天")
    log("  字段拼写修正：isWorday -> isWorkday")
    write_csv(cal_out, processed / "workday_calendar_clean.csv")

    # ---------- 小时气象 ----------
    section("P1-5 气象 · 小时数据")
    w = standardize_columns(pd.read_csv(metro_dir / "shanghai_weatherHourly.csv"))
    log(f"  原始 {w.shape[0]:,} 行 × {w.shape[1]} 列")
    log("  [缺失值]\n" + missing_report(w).to_string(index=False))

    dt = pd.to_datetime(w["date"], errors="coerce")
    w["日期"] = dt.dt.strftime("%Y-%m-%d")
    w["小时"] = dt.dt.hour
    w["年份"] = dt.dt.year
    w["月"] = dt.dt.month

    log(f"  日期范围：{w['日期'].min()} ~ {w['日期'].max()}；"
        f"唯一天数 {w['日期'].nunique()}")

    # 重复值（主键 日期+小时）
    dup = w.duplicated(subset=["日期", "小时"], keep="first")
    if dup.sum():
        w = w[~dup].copy()
        log(f"  [重复值] 剔除 {int(dup.sum())} 条")
    else:
        log("  [重复值] 主键 日期+小时 无重复")

    # 值域校验
    n_temp = int(range_check(w, "temperature_2m", -50, 60).sum())
    n_wind = int(range_check(w, "wind_speed_10m", 0, None).sum())
    n_rain = int(range_check(w, "rain", 0, None).sum())
    log(f"  [值域校验] 温度越界 {n_temp}；风速越界 {n_wind}；降水越界 {n_rain}")
    log(f"  [rain 口径] 唯一值 {w['rain'].nunique()} 个，"
        f"范围 {w['rain'].min()}~{w['rain'].max()} -> 判定为降水量(mm)，非 0/1 标记")

    # 与时间窗对齐：剔除 6 个不完整日
    bad = w["日期"].isin(BAD_DATES)
    log(f"  [同步剔除] 与地铁一致，剔除 6 个不完整日：{int(bad.sum())} 行")
    w = w[~bad].copy()

    # 关联工作日历
    w = w.merge(cal_out[["日期", "是否工作日"]], on="日期", how="left")

    # 精度
    for c in ["temperature_2m", "apparent_temperature", "rain", "wind_speed_10m"]:
        w[c] = w[c].round(1)

    cols = ["日期", "年份", "月", "小时", "是否工作日",
            "temperature_2m", "apparent_temperature", "rain", "wind_speed_10m"]
    hourly = w[cols].sort_values(["日期", "小时"]).reset_index(drop=True)
    log(f"  清洗后 {len(hourly):,} 行 = {hourly['日期'].nunique()} 天 × 24 小时")
    write_csv(hourly, cleaned / "cleaned_weather_hourly.csv")

    # ---------- 日聚合 ----------
    section("P1-5 气象 · 日尺度聚合")
    g = w.groupby("日期", as_index=False).agg(
        日降水合计_mm=("rain", "sum"),
        日均温_摄氏度=("temperature_2m", "mean"),
        日最高温_摄氏度=("temperature_2m", "max"),
        日最低温_摄氏度=("temperature_2m", "min"),
        日最大风速_公里每小时=("wind_speed_10m", "max"))
    for c in g.columns[1:]:
        g[c] = g[c].round(1)
    # 降雨日标记（日降水 > 0 视为有降雨）
    g["是否降雨日"] = np.where(g["日降水合计_mm"] > 0, "是", "否")
    g = g.merge(cal_out[["日期", "是否工作日"]], on="日期", how="left")
    g = g.sort_values("日期").reset_index(drop=True)
    log(f"  日聚合 {len(g)} 行；降雨日 {int((g['是否降雨日'] == '是').sum())} 天")
    write_csv(g, cleaned / "cleaned_weather_daily.csv")

    section("P1-5 气象清洗完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
