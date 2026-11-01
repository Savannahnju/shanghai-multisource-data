# -*- coding: utf-8 -*-
"""
================================================================================
E_cleaning_poi.py —— POI 数据清洗（优先级 P1-6，C 的研究问题 2）
================================================================================

【输入】
  <team-data>/上海市百度地图POI数据/上海市.csv   1,422,977 行 × 15 列（277 MB）
  <team-data>/上海市行政区划-乡镇级shp文件/区级数据.geojson   16 区区界

【输出】
  data/cleaned/cleaned_poi.csv                     全量（本地留存）
  data/cleaned/cleaned_poi_sample.csv              1% 随机样本（上 GitHub）
  data/cleaned/cleaned_poi_district_industry.csv   区 × 产业大类 聚合（C 分析主表）

【清洗规则（按 C 的 C_POI_data_cleaning.md 执行，标准层面补充）】
  1. 删除无区分度字段：省份（全"上海市"）、城市（全 21）、区县（全"上海市"）；
  2. **电话脱敏删除**：缺失约 68%，且含个人手机号，涉个人信息，不进交付
     （对应待确认 Q7，按"删除"执行）；
  3. 坐标校验：WGS84 经度 120.8–122.0、纬度 30.6–31.9，超界单独列出不静默删；
  4. 剔除异常大类：虚拟数据 / 室内设施 / 事件活动（非实体产业，约 64 条）；
  5. 去重：按 ID；辅以 名称+坐标+大类；
  6. **空间连接生成 `区名`**：必须用 **WGS84** 坐标配 WGS84 区界
     （GCJ02 是加密坐标，与区界有 300–600 m 偏移，用它会错划到邻区）；
     未匹配点单独统计、不丢弃，匹配率写入报告；
  7. 产业映射：21 个 POI 大类 → 12 个产业大类（C 的映射表）；
  8. GCJ02 两列保留但仅用于高德底图叠加，**分析一律用 WGS84**。

【运行】
  python processing/E_cleaning_poi.py
  python processing/E_cleaning_poi.py --no-full   # 只出样本与聚合（快）
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
    find_district_file,
    log,
    missing_report,
    normalize_district,
    project_root,
    section,
    write_csv,
)
from E_common import default_team_data  # noqa: E402

# C 的产业映射表：21 个 POI 大类 -> 产业大类
INDUSTRY_MAP = {
    "公司企业": "生产性服务业",
    "金融保险服务": "金融业",
    "购物服务": "批发零售",
    "餐饮服务": "住宿餐饮",
    "住宿服务": "住宿餐饮",
    "生活服务": "居民生活服务",
    "交通设施服务": "交通运输仓储",
    "通行设施": "交通运输仓储",
    "汽车服务": "居民生活服务",
    "汽车销售": "批发零售",
    "汽车维修": "居民生活服务",
    "摩托车服务": "居民生活服务",
    "道路附属设施": "公共设施",
    "政府机构及社会团体": "公共管理社会组织",
    "科教文化服务": "教育文化",
    "医疗保健服务": "卫生福利",
    "体育休闲服务": "文化休闲",
    "风景名胜": "文化休闲",
    "公共设施": "公共设施",
    "商务住宅": "房地产居住",
    "地名地址信息": "居住地址标识",
}
EXCLUDE_CATEGORIES = ["虚拟数据", "室内设施", "事件活动"]
DROP_COLS = ["省份", "城市", "区县", "电话"]
LON_MIN, LON_MAX = 120.8, 122.0
LAT_MIN, LAT_MAX = 30.6, 31.9


def main() -> int:
    ap = argparse.ArgumentParser(description="POI 数据清洗（P1-6）")
    ap.add_argument("--team-data", default=None)
    ap.add_argument("--district-file", default=None)
    ap.add_argument("--cleaned", default=None)
    ap.add_argument("--no-full", action="store_true")
    ap.add_argument("--sample-frac", type=float, default=0.01)
    args = ap.parse_args()

    root = project_root()
    team = Path(args.team_data) if args.team_data else default_team_data()
    cleaned = Path(args.cleaned) if args.cleaned else root / "data" / "cleaned"
    ensure_dir(cleaned)

    poi_path = team / "上海市百度地图POI数据" / "上海市.csv"
    if not poi_path.exists():
        log(f"[错误] 找不到 POI 文件：{poi_path}")
        return 1

    # ---------- 读取 ----------
    section("P1-6 POI · 读取")
    df = pd.read_csv(poi_path, dtype={"类型码": "str"})
    n_raw = len(df)
    log(f"  原始 {n_raw:,} 行 × {df.shape[1]} 列")
    log(f"  大类 {df['大类'].nunique()} 个；中类 {df['中类'].nunique()} 个；"
        f"小类 {df['小类'].nunique()} 个")

    # ---------- 删无效列 + 电话脱敏 ----------
    section("P1-6 POI · 字段处理")
    drop = [c for c in DROP_COLS if c in df.columns]
    df = df.drop(columns=drop)
    log(f"  删除无区分度/敏感字段：{drop}")
    log(f"    省份唯一值 {1}（全'上海市'）、城市唯一值 1（全'21'）、"
        f"区县唯一值 1（全'上海市'）-> 无信息量")
    log("    电话缺失约 68% 且含个人手机号 -> 按脱敏要求删除（待确认 Q7 按删除执行）")

    # ---------- 坐标校验 ----------
    section("P1-6 POI · 坐标校验（WGS84）")
    bad_lon = ~df["经度_WGS84"].between(LON_MIN, LON_MAX)
    bad_lat = ~df["纬度_WGS84"].between(LAT_MIN, LAT_MAX)
    bad = bad_lon | bad_lat
    log(f"  经度越界 {int(bad_lon.sum()):,} 条；纬度越界 {int(bad_lat.sum()):,} 条；"
        f"合计 {int(bad.sum()):,} 条")
    if bad.any():
        log(f"  示例：\n{df.loc[bad, ['ID', '名称', '经度_WGS84', '纬度_WGS84']].head(5).to_string(index=False)}")
        df = df[~bad].copy()
        log(f"  已剔除越界点，剩余 {len(df):,} 行")

    # GCJ02 与 WGS84 偏移量（说明为何不能混用）
    dx = (df["经度_GCJ02"] - df["经度_WGS84"]).abs()
    dy = (df["纬度_GCJ02"] - df["纬度_WGS84"]).abs()
    log(f"  GCJ02 - WGS84 偏移：经度均值 {dx.mean():.6f}°，纬度均值 {dy.mean():.6f}°"
        f"（约 {dy.mean() * 111000:.0f} m 量级）-> 两套坐标不可混用")

    # ---------- 剔除异常大类 ----------
    section("P1-6 POI · 异常大类过滤")
    cnt_ex = df["大类"].isin(EXCLUDE_CATEGORIES).sum()
    log(f"  剔除 {EXCLUDE_CATEGORIES}：{int(cnt_ex)} 条")
    df = df[~df["大类"].isin(EXCLUDE_CATEGORIES)].copy()
    unknown = sorted(set(df["大类"]) - set(INDUSTRY_MAP))
    if unknown:
        log(f"  [提示] 映射表未覆盖的大类：{unknown}（产业大类将留空，需 C 补充）")

    # ---------- 去重 ----------
    section("P1-6 POI · 去重")
    dup_id = df.duplicated(subset=["ID"], keep="first")
    log(f"  按 ID 重复：{int(dup_id.sum()):,} 条")
    df = df[~dup_id].copy()
    dup_tri = df.duplicated(subset=["名称", "经度_WGS84", "纬度_WGS84", "大类"], keep="first")
    log(f"  按 名称+坐标+大类 重复：{int(dup_tri.sum()):,} 条（保留首条）")
    df = df[~dup_tri].copy()
    log(f"  去重后 {len(df):,} 行")

    # ---------- 空间连接 ----------
    section("P1-6 POI · 空间连接（WGS84 点 × WGS84 区界）")
    import geopandas as gpd
    from shapely.geometry import Point

    dfile = Path(args.district_file) if args.district_file else find_district_file(team)
    if dfile is None:
        log("[错误] 未找到区界文件（shp / geojson）")
        return 1
    dist = gpd.read_file(str(dfile))
    name_col = "district" if "district" in dist.columns else dist.columns[0]
    dist["区名"] = dist[name_col].map(normalize_district)
    dist = dist[dist["区名"].isin(DISTRICTS_16)][["区名", "geometry"]]
    log(f"  区界 {len(dist)} 区（{Path(dfile).name}）")

    poi = gpd.GeoDataFrame(
        df,
        geometry=[Point(x, y) for x, y in zip(df["经度_WGS84"], df["纬度_WGS84"])],
        crs="EPSG:4326")
    joined = gpd.sjoin(poi, dist, how="left", predicate="within")
    joined = joined.drop(columns=["index_right"], errors="ignore")

    # sjoin 可能因区界要素重叠/边界点产生"一点多区"的多重匹配 -> 按 ID 去重
    dup_sp = joined.duplicated(subset=["ID"], keep="first")
    if dup_sp.any():
        log(f"  [去重] 空间连接产生多重匹配 {int(dup_sp.sum()):,} 条"
            f"（区界重叠或边界点），保留首条")
        joined = joined[~dup_sp].copy()

    n_unmatch = int(joined["区名"].isna().sum())
    rate = (1 - n_unmatch / len(joined)) * 100
    log(f"  匹配成功 {len(joined) - n_unmatch:,} 条；未匹配 {n_unmatch:,} 条；"
        f"匹配率 {rate:.3f}%")
    if n_unmatch:
        log("  未匹配点单独保留（不丢弃），`区名` 留空；报告中单列说明")

    # ---------- 产业映射 ----------
    section("P1-6 POI · 产业映射")
    joined["产业大类"] = joined["大类"].map(INDUSTRY_MAP)
    log(f"  映射后产业大类 {joined['产业大类'].nunique()} 个："
        f"{sorted(joined['产业大类'].dropna().unique())}")
    log("  [局限] 高德无制造业大类，第二产业系统性缺失，须在报告中说明")

    out = pd.DataFrame(joined.drop(columns="geometry"))
    out = out[["ID", "名称", "类型码", "大类", "中类", "小类", "产业大类", "区名",
               "经度_WGS84", "纬度_WGS84", "经度_GCJ02", "纬度_GCJ02", "地址"]]
    for c in ["经度_WGS84", "纬度_WGS84", "经度_GCJ02", "纬度_GCJ02"]:
        out[c] = out[c].round(6)

    log("  [字段缺失]\n" + missing_report(out).to_string(index=False))

    # ---------- 输出 ----------
    section("P1-6 POI · 写出")
    if not args.no_full:
        write_csv(out, cleaned / "cleaned_poi.csv")

    # 1% 样本
    samp = out.sample(frac=args.sample_frac, random_state=42)
    write_csv(samp, cleaned / "cleaned_poi_sample.csv")
    log(f"  样本比例 {args.sample_frac:.0%}（random_state=42）")

    # 区 × 产业聚合（C 的分析主表）
    g = (out.dropna(subset=["区名"])
            .groupby(["区名", "产业大类"], as_index=False)
            .agg(POI数量=("ID", "count")))
    tot = g.groupby("区名")["POI数量"].transform("sum")
    g["占本区比例_%"] = (g["POI数量"] / tot * 100).round(2)
    # 区位熵 = (区内该产业占比) / (全市该产业占比)
    city_ind = out.dropna(subset=["区名"]).groupby("产业大类").size()
    city_ratio = city_ind / city_ind.sum()
    g["区位熵"] = (g["占本区比例_%"] / 100 / g["产业大类"].map(city_ratio)).round(3)
    g["_o"] = g["区名"].map({d: i for i, d in enumerate(DISTRICTS_16)})
    g = g.sort_values(["_o", "产业大类"]).drop(columns="_o")
    write_csv(g, cleaned / "cleaned_poi_district_industry.csv")

    # 区级汇总（供 C 与空气关联）
    dz = (out.dropna(subset=["区名"]).groupby("区名", as_index=False)
          .agg(POI总数=("ID", "count")))
    dz["_o"] = dz["区名"].map({d: i for i, d in enumerate(DISTRICTS_16)})
    dz = dz.sort_values("_o").drop(columns="_o")
    write_csv(dz, cleaned / "cleaned_poi_by_district.csv")

    section("P1-6 POI 清洗完成")
    log(f"  {n_raw:,} -> {len(out):,} 行（剔除 "
        f"{n_raw - len(out):,} 条，占 {(n_raw - len(out)) / n_raw * 100:.3f}%）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
