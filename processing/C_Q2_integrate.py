# -*- coding: utf-8 -*-
"""
[C] Q2 融合数据生成脚本（Integrated Data）

作用：把"区 × 产业结构 × 环境质量 × 机制代理"四类信息，按统一键 `adcode`（等价 `区名`）
      融合为一张可供统一分析的宽表，输出 data/integrated/integrated_C_Q2_sample.csv。

上游依赖：先执行 analysis/C_Q2_analysis.py，产出 analysis/output/ 的阶段结果表；
          区界与 adcode 取自 data/raw/raw_C_district_sample.geojson。

输入（analysis/output/）：
    01_产业结构指标.csv   面积、POI 数、密度、12 类产业占比、Shannon/HHI、PC1/PC2
    02_环境质量刻画.csv   PM2.5、道路 PM10、O3 年均与 AQI 优良率（2024-01—2025-12 两年均值）
    04_机制变量表.csv     距市中心距离、扬尘/物流/汽修/商务住宅源数
    06_Kmeans聚类.csv     CLR 空间 K-means 簇号、主导产业

运行：
    python processing/C_Q2_integrate.py
"""

import io
import json
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "analysis", "output")
GEO_PATH = os.path.join(ROOT, "data", "raw", "raw_C_district_sample.geojson")
DST = os.path.join(ROOT, "data", "integrated", "integrated_C_Q2_sample.csv")

# 输出列的中文别名：带单位、去歧义
RENAME = {
    "距市中心km": "距市中心_km",
    "原始POI总数": "原始POI总数_条",
    "修正后产业POI数": "产业POI数_条",
    "PM2.5年均": "PM2.5_ug_m3",
    "道路PM10年均": "道路PM10_ug_m3",
    "O3年均": "O3_ug_m3",
    "AQI优良率": "AQI优良率_pct",
    "簇": "Kmeans簇",
}


def load_output(name):
    """读取 Q2 流水线的阶段结果表（UTF-8-SIG，中文表头）。"""
    return pd.read_csv(os.path.join(OUT_DIR, name), encoding="utf-8-sig")


def load_adcode():
    """从区界 geojson 提取 区名 → adcode，作为跨源统一键。"""
    geo = json.load(io.open(GEO_PATH, encoding="utf-8"))
    return pd.DataFrame(
        [{"区名": f["properties"]["district"], "adcode": str(f["properties"]["adcode"])}
         for f in geo["features"]]
    )


def build_fused():
    """按区名一对一合并四张阶段表，并补上时间对齐标记。"""
    fused = load_output("01_产业结构指标.csv").merge(
        load_adcode(), on="区名", how="inner", validate="1:1")

    fused = fused.merge(
        load_output("02_环境质量刻画.csv")[["区名", "PM2.5年均", "道路PM10年均", "O3年均", "AQI优良率"]],
        on="区名", how="inner", validate="1:1")

    fused = fused.merge(
        load_output("04_机制变量表.csv")[["区名", "距市中心km", "扬尘源数", "物流源数", "汽修源数", "商务住宅数"]],
        on="区名", how="inner", validate="1:1")

    fused = fused.merge(
        load_output("06_Kmeans聚类.csv")[["区名", "簇", "主导产业", "主导产业占比"]],
        on="区名", how="inner", validate="1:1")

    fused["POI年份"] = 2025
    fused["空气质量窗口"] = "2024-01~2025-12"
    return fused


def order_columns(df):
    """按 键 → 规模 → 结构 → 模型结果 → 机制 → 环境 → 对齐标记 排列。"""
    share_cols = [c for c in df.columns if c.startswith("占比_")]
    cols = (
        ["adcode", "区名", "面积_km2", "距市中心km", "原始POI总数", "修正后产业POI数", "POI密度_个每km2"]
        + share_cols
        + ["Shannon多样性", "HHI集中度", "PC1", "PC2", "簇", "主导产业", "主导产业占比",
           "扬尘源数", "物流源数", "汽修源数", "商务住宅数",
           "PM2.5年均", "道路PM10年均", "O3年均", "AQI优良率", "POI年份", "空气质量窗口"]
    )
    return df[[c for c in cols if c in df.columns]].sort_values("adcode").reset_index(drop=True)


def validate(df):
    """融合完整性检查：16 区齐全、无缺失、键唯一。"""
    assert len(df) == 16, f"区数应为 16，实际 {len(df)}"
    assert df["adcode"].is_unique, "adcode 不唯一"
    na = df.isna().sum()
    assert na.sum() == 0, "存在缺失值：\n" + na[na > 0].to_string()
    # 结构占比每行应近似等于 100%
    share = df[[c for c in df.columns if c.startswith("占比_")]].sum(axis=1)
    assert (share - 100).abs().max() < 0.1, f"占比行和偏离 100：{share.round(2).tolist()}"


def main():
    fused = build_fused()
    validate(fused)
    out = order_columns(fused).rename(columns=RENAME)
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    out.to_csv(DST, index=False, encoding="utf-8-sig")
    print(f"已生成 {DST}")
    print(f"行数 {len(out)} / 列数 {len(out.columns)} / 体积 {os.path.getsize(DST)} bytes")


if __name__ == "__main__":
    main()
