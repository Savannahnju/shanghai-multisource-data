# -*- coding: utf-8 -*-
"""
================================================================================
E_cleaning_metro.py —— 地铁客流 + 站点清洗（优先级 P1-4，B 的研究问题 1）
================================================================================

【输入】
  <team-data>/上海地铁客流量/metroData_InOutFlow.csv  3,788,892 行 × 13 列（217 MB）
  <team-data>/上海地铁客流量/stationInfo.csv          302 行 × 6 列
  <team-data>/上海地铁客流量/workday_calendar.csv     123 行 × 2 列
  <team-data>/../B_数据清洗要求/站点_区映射.csv        302 行（B 已完成，直接复用）

【输出】
  data/cleaned/cleaned_metro.csv                全量（本地留存，约 300 MB）
  data/cleaned/cleaned_metro_sample.csv         2 个完整日样本（上 GitHub，约 3 MB）
  data/cleaned/cleaned_metro_daily_district.csv 区 × 日 聚合（B 的分析主表）
  data/processed/metro_station_clean.csv        站点表（含区名）

【清洗规则】
  1. 列名去首尾空格（原始为 ' date' / ' timeslot' ...）；
  2. date：20170501 -> 2017-05-01，并派生 年份/月/日；
  3. startTime/endTime：HMMSS 整数（60000 -> 06:00:00）转标准时间；
     **timeslot 是跨天全局递增编号 0–12545**（每天 102 段 × 123 天），
     日内时段 = timeslot % 102（0–101，对应 6:00–23:00）；
  4. 关联 stationInfo（302/302 全匹配），补站点名称/经纬度；删 Unnamed: 0；
  5. **剔除 6 个采集不完整日**（B 已识别）：
     20170504、20170508、20170509、20170616、20170627、20170628；
  6. 站点归区：复用 B 的映射；3 站（11 号线昆山段）剔除；
     奉贤/金山/崇明无地铁，客流记缺失**不填 0**；
  7. 完整性校验：原始 302 站每日进站总量 == 出站总量（严格配平）；
     剔除昆山 3 站后 299 站不再配平，差额须等于这 3 站自身的进出站差；
  8. 缺失/重复/负值按标准 2.6–2.8 处理。

【运行】
  python processing/E_cleaning_metro.py
  python processing/E_cleaning_metro.py --no-full   # 跳过全量写出（快）
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
    DISTRICTS_16,
    ensure_dir,
    log,
    missing_report,
    normalize_district,
    project_root,
    section,
    write_csv,
)
from E_common import default_team_data  # noqa: E402

# B 已识别的采集不完整日（当日总客流 < 500 万，完整日为 727–1538 万）
BAD_DATES = [20170504, 20170508, 20170509, 20170616, 20170627, 20170628]

FLOW_COLS = ["inFlow", "outFlow", "CinFlow", "HBOinFlow", "NHBinFlow",
             "CoutFlow", "HBOoutFlow", "NHBoutFlow"]


def hmmss_to_time(v) -> str:
    """60000 -> '06:00:00'；61000 -> '06:10:00'。"""
    if pd.isna(v):
        return ""
    v = int(v)
    return f"{v // 10000:02d}:{(v // 100) % 100:02d}:{v % 100:02d}"


def main() -> int:
    ap = argparse.ArgumentParser(description="地铁客流+站点清洗（P1-4）")
    ap.add_argument("--team-data", default=None)
    ap.add_argument("--cleaned", default=None)
    ap.add_argument("--processed", default=None)
    ap.add_argument("--no-full", action="store_true", help="跳过全量 cleaned_metro.csv 写出")
    ap.add_argument("--chunksize", type=int, default=500_000)
    args = ap.parse_args()

    root = project_root()
    team = Path(args.team_data) if args.team_data else default_team_data()
    metro_dir = team / "上海地铁客流量"
    cleaned = Path(args.cleaned) if args.cleaned else root / "data" / "cleaned"
    processed = Path(args.processed) if args.processed else root / "data" / "processed"
    ensure_dir(cleaned)
    ensure_dir(processed)

    # ---------- 站点表 ----------
    section("P1-4 地铁 · 站点信息")
    st = pd.read_csv(metro_dir / "stationInfo.csv")
    st = st.rename(columns=lambda c: str(c).strip())
    st = st.drop(columns=[c for c in st.columns if c.startswith("Unnamed")], errors="ignore")
    st = st.rename(columns={"stationID": "station", "name": "站点名称",
                            "lon": "经度", "lat": "纬度"})
    log(f"  站点 {len(st)} 行；列：{list(st.columns)}")

    # 站点 → 区（复用 B 的映射）
    mapping = team.parent / "B_数据清洗要求" / "站点_区映射.csv"
    if mapping.exists():
        mp = pd.read_csv(mapping, encoding="utf-8-sig")
        mp = mp.rename(columns=lambda c: str(c).strip())
        mp["区名"] = mp["district"].map(normalize_district)
        st = st.merge(mp[["stationID", "区名"]].rename(columns={"stationID": "station"}),
                      on="station", how="left")
        log(f"  已复用 B 的站点→区映射（{len(mp)} 行）")
    else:
        st["区名"] = None
        log("  [警告] 未找到 B 的站点→区映射，区名为空")

    outside = st[st["区名"] == "上海市外（昆山）"]
    if len(outside):
        log(f"  上海市外站点 {len(outside)} 个（11 号线昆山段）："
            f"{outside['站点名称'].tolist()}，将剔除")
    covered = sorted(set(st["区名"].dropna()) - {"上海市外（昆山）"})
    log(f"  覆盖 {len(covered)} 个区；无地铁的区："
        f"{[d for d in DISTRICTS_16 if d not in covered]}（客流记缺失，不填 0）")
    write_csv(st, processed / "metro_station_clean.csv")

    # ---------- 工作日历 ----------
    section("P1-4 地铁 · 工作日历")
    cal = pd.read_csv(metro_dir / "workday_calendar.csv")
    cal = cal.rename(columns=lambda c: str(c).strip())
    cal = cal.rename(columns={"isWorday": "isWorkday"})   # 修正原始拼写错误
    cal["date"] = pd.to_datetime(cal["date"].astype(str), format="%Y%m%d")
    cal["是否工作日"] = np.where(cal["isWorkday"] == 1, "工作日", "非工作日")
    cal["日期"] = cal["date"].dt.strftime("%Y-%m-%d")
    log(f"  日历 {len(cal)} 天；工作日 {int((cal['isWorkday'] == 1).sum())} 天")
    log("  已修正字段拼写：isWorday -> isWorkday")

    # ---------- 客流分块清洗 ----------
    section("P1-4 地铁 · 客流分块清洗")
    src = metro_dir / "metroData_InOutFlow.csv"
    chunksize = args.chunksize

    out_full = cleaned / "cleaned_metro.csv"
    if out_full.exists() and not args.no_full:
        out_full.unlink()

    st_small = st[["station", "站点名称", "经度", "纬度", "区名"]]
    cal_small = cal[["日期", "是否工作日"]]

    tot_in = tot_out = 0
    removed_bad = 0
    removed_dup = 0
    neg_cnt = 0
    unmatched_station = 0
    first_write = True
    daily_rows = []
    ks_rows = []

    for i, ch in enumerate(pd.read_csv(src, chunksize=chunksize)):
        ch = ch.rename(columns=lambda c: str(c).strip())
        n0 = len(ch)
        tot_in += n0

        # 剔除不完整日
        bad = ch["date"].isin(BAD_DATES)
        removed_bad += int(bad.sum())
        ch = ch[~bad].copy()
        if ch.empty:
            continue

        # date -> 标准日期
        ch["日期"] = pd.to_datetime(ch["date"].astype(str), format="%Y%m%d").dt.strftime("%Y-%m-%d")
        ch["年份"] = ch["date"] // 10000
        ch["月"] = (ch["date"] // 100) % 100
        ch["日"] = ch["date"] % 100

        # HMMSS -> 时间
        ch["起始时刻"] = ch["startTime"].map(hmmss_to_time)
        ch["结束时刻"] = ch["endTime"].map(hmmss_to_time)
        # timeslot 为**跨天全局编号**（0–12545），派生日内时段 0–101
        ch["时段"] = ch["timeslot"] % 102

        # 重复值（主键 date+timeslot+station）
        dup = ch.duplicated(subset=["date", "timeslot", "station"], keep="first")
        removed_dup += int(dup.sum())
        ch = ch[~dup].copy()

        # 关联站点
        before = len(ch)
        ch = ch.merge(st_small, on="station", how="left")
        unmatched_station += int(ch["站点名称"].isna().sum())
        # 昆山 3 站（上海市外）在剔除前先单独结算：剔除后 299 站将不再配平，
        # 差额应恰等于这 3 站自身的进站-出站差，用于证明差额是口径变化、不是数据缺陷
        ks = ch[ch["区名"] == "上海市外（昆山）"]
        if len(ks):
            ks_rows.append(ks.groupby("日期", as_index=False).agg(
                昆山进站=("inFlow", "sum"), 昆山出站=("outFlow", "sum")))
        # 剔除上海市外（昆山）站点
        ch = ch[ch["区名"] != "上海市外（昆山）"].copy()
        # 关联工作日历（B 的 Q1 需要区分工作日/非工作日）
        ch = ch.merge(cal_small, on="日期", how="left")

        # 负值校验
        for c in FLOW_COLS:
            neg_cnt += int((pd.to_numeric(ch[c], errors="coerce") < 0).sum())

        # 日进出站合计（用于闭合校验）
        g = ch.groupby("日期", as_index=False).agg(
            日进站总量=("inFlow", "sum"), 日出站总量=("outFlow", "sum"))
        daily_rows.append(g)

        if not args.no_full:
            ch.to_csv(out_full, mode="a", index=False,
                      header=first_write, encoding="utf-8-sig", lineterminator="\n")
            first_write = False

        log(f"  块 {i + 1}: 读入 {n0:,} 行 -> 保留 {len(ch):,} 行")

    tot_out = tot_in - removed_bad - removed_dup
    log(f"\n  合计读入 {tot_in:,} 行；剔除不完整日 {removed_bad:,} 行；"
        f"剔除重复 {removed_dup:,} 行；剩余 {tot_out:,} 行")
    if not args.no_full:
        log(f"  全量已写出：{out_full.relative_to(root)} "
            f"({out_full.stat().st_size / 1024 / 1024:.1f} MB)")
    log(f"  站点未匹配 {unmatched_station} 条；客流负值 {neg_cnt} 条")

    # ---------- 每日闭合校验 ----------
    section("P1-4 地铁 · 完整性校验（进/出站总量配平）")
    daily = pd.concat(daily_rows, ignore_index=True)
    daily = daily.groupby("日期", as_index=False).sum()
    daily["差值"] = daily["日进站总量"] - daily["日出站总量"]

    # 加回昆山 3 站，还原原始 302 站口径做严格配平校验
    if ks_rows:
        ks = pd.concat(ks_rows, ignore_index=True).groupby("日期", as_index=False).sum()
        daily = daily.merge(ks, on="日期", how="left")
        daily[["昆山进站", "昆山出站"]] = daily[["昆山进站", "昆山出站"]].fillna(0)
    else:
        daily["昆山进站"] = 0
        daily["昆山出站"] = 0
    daily["全站进站总量"] = daily["日进站总量"] + daily["昆山进站"]
    daily["全站出站总量"] = daily["日出站总量"] + daily["昆山出站"]
    daily["全站差值"] = daily["全站进站总量"] - daily["全站出站总量"]

    log(f"  原始 302 站：严格配平 {int((daily['全站差值'] == 0).sum())}/{len(daily)} 天"
        f"（全站进站 = 出站 = {int(daily['全站进站总量'].sum()):,}）")
    log(f"  剔除昆山 3 站后（299 站）：严格相等 {int((daily['差值'] == 0).sum())} 天，"
        f"差值 {daily['差值'].min()} ~ {daily['差值'].max()}")
    resid = int((daily["差值"] + (daily["昆山进站"] - daily["昆山出站"])).abs().max())
    log(f"  差额溯源：299 站差值 + 昆山站进出差 的最大残差 = {resid}"
        f"（0 = 差额完全由剔站造成，非数据缺陷）")
    daily["相对误差_%"] = (daily["差值"].abs() / daily["日进站总量"] * 100).round(4)

    # 500 万阈值只对**工作日**成立：周末/节假日正常低客流为 360–500 万
    daily = daily.merge(cal_small, on="日期", how="left")
    daily["采集不完整"] = (daily["日进站总量"] < 5_000_000) & (daily["是否工作日"] == "工作日")
    n_bad = int(daily["采集不完整"].sum())
    n_low_nwd = int(((daily["日进站总量"] < 5_000_000)
                     & (daily["是否工作日"] == "非工作日")).sum())
    log(f"  工作日且 < 500 万（采集不完整，已在清洗时剔除）：{n_bad} 天")
    log(f"  非工作日且 < 500 万：{n_low_nwd} 天 -> 周末正常低客流，不剔除")
    write_csv(daily, processed / "metro_daily_totals.csv")

    # ---------- 区 × 日 聚合（B 分析主表） ----------
    section("P1-4 地铁 · 区 × 日 聚合")
    parts = []
    for ch in pd.read_csv(out_full if not args.no_full else src,
                          chunksize=chunksize):
        ch = ch.rename(columns=lambda c: str(c).strip())
        if "日期" not in ch.columns:
            ch["日期"] = pd.to_datetime(ch["date"].astype(str),
                                        format="%Y%m%d").dt.strftime("%Y-%m-%d")
        if "区名" in ch.columns:
            g = ch.groupby(["日期", "区名"], as_index=False).agg(
                日进站量=("inFlow", "sum"), 日出站量=("outFlow", "sum"))
            parts.append(g)
    dd = pd.concat(parts, ignore_index=True)
    dd = dd.groupby(["日期", "区名"], as_index=False).sum()
    dd = dd.merge(cal_small, on="日期", how="left")
    dd = dd[["日期", "区名", "是否工作日", "日进站量", "日出站量"]]
    dd = dd.sort_values(["日期", "区名"]).reset_index(drop=True)
    log(f"  区 × 日 聚合：{len(dd)} 行（{dd['日期'].nunique()} 天 × "
        f"{dd['区名'].nunique()} 区）")
    write_csv(dd, cleaned / "cleaned_metro_daily_district.csv")

    # ---------- 2 个完整日样本 ----------
    section("P1-4 地铁 · 上传 GitHub 样本（2 个完整日）")
    wd = cal_small.loc[cal_small["是否工作日"] == "工作日", "日期"].tolist()
    nwd = cal_small.loc[cal_small["是否工作日"] == "非工作日", "日期"].tolist()
    pick = []
    if wd:
        pick.append(wd[len(wd) // 2])      # 取中间的工作日，避开月初采集问题
    if nwd:
        pick.append(nwd[len(nwd) // 2])
    log(f"  抽样日期：{pick}")

    sparts = []
    for ch in pd.read_csv(out_full if not args.no_full else src,
                          chunksize=chunksize):
        ch = ch.rename(columns=lambda c: str(c).strip())
        col = "日期" if "日期" in ch.columns else "date"
        if col == "date":
            ch["日期"] = pd.to_datetime(ch["date"].astype(str),
                                        format="%Y%m%d").dt.strftime("%Y-%m-%d")
            ch["时段"] = ch["timeslot"] % 102
        sparts.append(ch[ch["日期"].isin(pick)])
    samp = pd.concat(sparts, ignore_index=True)

    # 只保留语义列：去掉与"日期/起始时刻"等价的冗余列（date/年份/月/日/startTime/endTime）
    sample_cols = ["日期", "是否工作日", "时段", "起始时刻", "结束时刻",
                   "station", "站点名称", "经度", "纬度", "区名"] + FLOW_COLS
    samp = samp[[c for c in sample_cols if c in samp.columns]]

    out_samp = cleaned / "cleaned_metro_sample.csv"
    write_csv(samp, out_samp)
    size = out_samp.stat().st_size / 1024 / 1024
    if size > 5.0 and len(pick) > 1:
        # 超过 5 MB 上限 -> 降为 1 个完整工作日（保住结构完整性）
        keep = [pick[0]]
        samp = samp[samp["日期"].isin(keep)]
        write_csv(samp, out_samp)
        size = out_samp.stat().st_size / 1024 / 1024
        log(f"  超过 5 MB 上限，降为 1 个完整日：{keep}")
    log(f"  样本 {len(samp):,} 行，{size:.2f} MB（上限 5 MB）")

    section("P1-4 地铁清洗完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
