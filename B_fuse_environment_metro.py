# -*- coding: utf-8 -*-
"""
Q1 数据融合脚本：城市环境质量 × 地铁客流量（2017 年 5–8 月）

研究问题：城市环境质量（区月降尘量、区月 PM2.5 均值）是否与地铁客流量有关？

────────────────────────────────────────────────────────────────────
输入文件（相对本脚本所在目录的上一级，即 上海地铁客流量2017/）：
  1. metroData_InOutFlow.csv                    地铁进出站客流（站点 × 10 分钟，2017-05-01~08-31）
  2. B_数据清洗要求/站点_区映射.csv             站点 → 区 映射（302 站，13 区有站点 + 3 站市外）
  3. 2017年各区降尘量与PM2.5月均浓度.xlsx       环境质量（Sheet1 降尘量 / Sheet2 PM2.5，16 区 × 12 月）
  4. 天气&工作日/workday_calendar.csv           工作日历（date, isWorday）
  5. 天气&工作日/shanghai_weatherHourly.csv     逐小时气象（全市单点，作月级控制变量）

输出文件（写入本目录 output/）：
  A. air_2017_long.csv                   环境长表：区名 × 月份（5–8 月），降尘量 + PM2.5
  B. metro_district_month.csv            地铁客流聚合：区名 × 月份，进出总客流 / 站点数 / 有效天数
  C. metro_district_day.csv              地铁客流中间表：区名 × 日（117 天），进出总客流
  D. fused_environment_metro_2017.csv    融合宽表（最终交付）：13 区 × 4 月 = 52 行
  E. fusion_log.txt                      数据量 / 缺失 / 校验日志

字段变化（相对原始）：
  - 地铁：删除 6 个采集不完整日（20170504/0508/0509/0616/0627/0628）；
          剔除 3 个市外站点（11 号线昆山段）；站点级 10 分钟 → 区级月度聚合；
          新增 地铁总客流=Σ(inFlow+outFlow)、地铁日均客流=总客流/有效天数、
          客流强度=总客流/站点数。
  - 环境：xlsx 宽表（16 区 × 12 月）→ 长表（区名 × 月份），仅保留 5–8 月；
          降尘量单位按领域惯例定为 t/(km²·月)，PM2.5 单位 μg/m³。
  - 控制变量：工作日数（该月有效工作日数）、月均温（℃）、月总降雨（mm），均为月级。
  - 空间对齐：奉贤 / 金山 / 崇明 3 区无地铁站点，不进融合表（客流侧缺失，不补 0）。

口径规则（与 E_cleaning_standard.md 一致）：
  - 区名按 16 区标准名，str.strip() 去首尾空格，保留全称（如「浦东新区」）。
  - 主键：区名 + 月份。merge 为左/右内连接，不允许笛卡尔积，输出校验无重复、无未匹配。
  - 客流分析与交付一律用 inFlow/outFlow 总量，不用 C/HBO/NHB 分量。
  - 随机无关操作；数值列不留空，单位写在 README 与数据字典。

运行命令：
  python -I fuse_environment_metro.py
────────────────────────────────────────────────────────────────────
"""
import pandas as pd
from pathlib import Path

# ---------- 路径（参数化） ----------
BASE = Path(__file__).resolve().parents[1]          # 上海地铁客流量2017/
OUTDIR = Path(__file__).resolve().parent / "output"
OUTDIR.mkdir(exist_ok=True)

METRO = BASE / "metroData_InOutFlow.csv"
MAP_STATION = BASE / "B_数据清洗要求" / "站点_区映射.csv"
AIR_XLSX = BASE / "2017年各区降尘量与PM2.5月均浓度.xlsx"
WORKDAY = BASE / "天气&工作日" / "workday_calendar.csv"
WEATHER = BASE / "天气&工作日" / "shanghai_weatherHourly.csv"

# 采集不完整的 6 天（当日总客流 < 500 万，整日剔除）
DROP_DATES = {"20170504", "20170508", "20170509", "20170616", "20170627", "20170628"}

log_lines = []


def log(msg):
    print(msg)
    log_lines.append(msg)


# ---------- 1. 地铁客流：站点 × 10 分钟 → 区 × 月 ----------
log("== 1. 地铁客流清洗与聚合 ==")
metro = pd.read_csv(
    METRO,
    usecols=lambda c: c.strip() in {"date", "station", "inFlow", "outFlow"},
)
metro.columns = [c.strip() for c in metro.columns]
log(f"原始行数：{len(metro):,}")

metro["date"] = metro["date"].astype(str)
metro["station"] = metro["station"].astype("int32")
metro["inFlow"] = metro["inFlow"].astype("int64")
metro["outFlow"] = metro["outFlow"].astype("int64")
metro["月份"] = metro["date"].str[4:6].astype(int)

before = len(metro)
metro = metro[~metro["date"].isin(DROP_DATES)]
log(f"剔除 6 个不完整日：-{before - len(metro):,} 行 → {len(metro):,} 行")

# 站点 → 区 映射
mapping = pd.read_csv(MAP_STATION, encoding="utf-8-sig")
mapping.columns = [c.strip() for c in mapping.columns]
mapping["district"] = mapping["district"].str.strip()
mapping = mapping[["stationID", "district"]]
mapping["stationID"] = mapping["stationID"].astype("int32")

metro = metro.merge(mapping, left_on="station", right_on="stationID", how="left")
before = len(metro)
metro = metro[metro["district"] != "上海市外（昆山）"]
log(f"剔除市外(昆山)站点：-{before - len(metro):,} 行；剩余 {len(metro):,} 行")
log(f"归区后有效区数：{metro['district'].nunique()}")

# 区 × 日 中间表
metro["总客流"] = metro["inFlow"] + metro["outFlow"]
district_day = (
    metro.groupby(["district", "date"], as_index=False)
    .agg(进出总客流=("总客流", "sum"))
    .rename(columns={"district": "区名"})
)

# 区 × 月 聚合
district_month = (
    metro.groupby(["district", "月份"], as_index=False)
    .agg(
        地铁总客流=("总客流", "sum"),
        站点数=("station", "nunique"),
        有效天数=("date", "nunique"),
    )
    .rename(columns={"district": "区名"})
)
district_month["地铁日均客流"] = (district_month["地铁总客流"] / district_month["有效天数"]).round(1)
district_month["客流强度"] = (district_month["地铁总客流"] / district_month["站点数"]).round(1)
log(f"区 × 月客流表：{district_month.shape[0]} 行（{district_month['区名'].nunique()} 区 × {district_month['月份'].nunique()} 月）")

# ---------- 2. 环境质量：xlsx → 长表（仅 5–8 月） ----------
log("\n== 2. 环境数据长表化 ==")
xl = pd.ExcelFile(AIR_XLSX)
dust = xl.parse(xl.sheet_names[0], header=0)   # 降尘量
pm25 = xl.parse(xl.sheet_names[1], header=0)   # PM2.5

def to_long(df, value_name):
    df = df.copy()
    df.columns = ["区名"] + [f"{m}月" for m in range(1, 13)]
    df["区名"] = df["区名"].str.strip()
    long = df.melt(id_vars="区名", var_name="月份", value_name=value_name)
    long["月份"] = long["月份"].str.replace("月", "", regex=False).astype(int)
    return long

dust_long = to_long(dust, "降尘量")
pm25_long = to_long(pm25, "PM2.5")
air = dust_long.merge(pm25_long, on=["区名", "月份"], how="inner")
air = air[air["月份"].between(5, 8)].sort_values(["区名", "月份"]).reset_index(drop=True)
log(f"环境长表（5–8 月）：{air.shape[0]} 行（{air['区名'].nunique()} 区 × {air['月份'].nunique()} 月）")
log(f"降尘量取值区间：{air['降尘量'].min():.1f} ~ {air['降尘量'].max():.1f}")
log(f"PM2.5 取值区间：{air['PM2.5'].min():.1f} ~ {air['PM2.5'].max():.1f}")

# ---------- 3. 控制变量（月级，全市一致） ----------
log("\n== 3. 月级控制变量 ==")
wd = pd.read_csv(WORKDAY, encoding="utf-8-sig")
wd.columns = [c.strip() for c in wd.columns]
wd["date"] = wd["date"].astype(str)
wd = wd[~wd["date"].isin(DROP_DATES)].copy()
wd["月份"] = wd["date"].str[4:6].astype(int)
workday_month = (
    wd.groupby("月份", as_index=False)
    .agg(工作日数=("isWorday", "sum"), 有效天数_月=("date", "nunique"))
)

wea = pd.read_csv(WEATHER, encoding="utf-8-sig")
wea.columns = [c.strip() for c in wea.columns]
wea["date"] = wea["date"].str[:8].astype(str)
wea = wea[~wea["date"].isin(DROP_DATES)].copy()
wea["月份"] = wea["date"].str[4:6].astype(int)
wea_daily = wea.groupby(["date", "月份"], as_index=False).agg(
    日均温=("temperature_2m", "mean"), 日降雨=("rain", "sum")
)
weather_month = (
    wea_daily.groupby("月份", as_index=False)
    .agg(月均温=("日均温", "mean"), 月总降雨=("日降雨", "sum"))
)
control = workday_month.merge(weather_month, on="月份", how="inner")
log(f"控制变量表：{control.shape[0]} 个月；字段={list(control.columns)}")

# ---------- 4. 融合 ----------
log("\n== 4. 融合 ==")
fused = district_month.merge(air, on=["区名", "月份"], how="inner")
fused = fused.merge(control, on="月份", how="left")
fused = fused.drop(columns=["有效天数_月"])

# 排序与精度
order = [
    "区名", "月份", "降尘量", "PM2.5", "地铁总客流", "地铁日均客流",
    "客流强度", "站点数", "有效天数", "工作日数", "月均温", "月总降雨",
]
fused = fused[order].sort_values(["月份", "区名"]).reset_index(drop=True)
fused["降尘量"] = fused["降尘量"].round(1)
fused["PM2.5"] = fused["PM2.5"].round(1)
fused["月均温"] = fused["月均温"].round(1)
fused["月总降雨"] = fused["月总降雨"].round(1)

# 校验
assert fused["区名"].nunique() == 13, f"期望 13 区，实际 {fused['区名'].nunique()}"
assert fused.shape[0] == 52, f"期望 52 行，实际 {fused.shape[0]}"
assert fused.duplicated(subset=["区名", "月份"]).sum() == 0, "存在重复区月！"
assert fused.isna().sum().sum() == 0, "存在缺失值！"
log(f"融合宽表：{fused.shape[0]} 行 × {fused.shape[1]} 列（13 区 × 4 月）")
log("校验通过：13 区、52 行、无重复区月、无缺失")

# ---------- 5. 写出（UTF-8 with BOM，Excel 直接打开不乱码） ----------
def write_csv(df, name):
    path = OUTDIR / name
    df.to_csv(path, index=False, encoding="utf-8-sig")
    log(f"写出 {name}：{df.shape[0]} 行 × {df.shape[1]} 列 → {path.name}")

write_csv(air, "air_2017_long.csv")
write_csv(district_month, "metro_district_month.csv")
write_csv(district_day.sort_values(["区名", "date"]), "metro_district_day.csv")
write_csv(fused, "fused_environment_metro_2017.csv")

# 日志
(OUTDIR / "fusion_log.txt").write_text("\n".join(log_lines), encoding="utf-8")
log("\n完成。日志写入 output/fusion_log.txt")
