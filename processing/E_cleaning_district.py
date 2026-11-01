# -*- coding: utf-8 -*-
"""
================================================================================
E_cleaning_district.py —— 行政区划数据清洗（优先级 P0-3，C/D 共用）
================================================================================

【输入】
  <team-data>/上海市行政区划-乡镇级shp文件/区级数据.shp    （优先，含 .prj）
  <team-data>/上海市行政区划-乡镇级shp文件/区级数据.geojson（shp 缺失时回退）
  乡镇级数据.geojson —— 本期仅登记，不下钻

【输出】
  data/cleaned/cleaned_district.geojson     区级边界（WGS84，含 area_km2）
  data/cleaned/cleaned_district.csv         区级属性表（区名/adcode/面积/质心）
  data/cleaned/cleaned_district.gpkg        （可选，仅在 geopandas 可用时导出）

【清洗规则】
  1. 区名按标准 2.3 标准化；剔除汇总行/表头行；必须 16 区；
  2. 坐标系统一 WGS84（EPSG:4326）；源为 geojson 时默认 CRS84；
  3. **面积重算**：原始 `Shape_Area` 为「平方度」，量纲错误不可用；
     统一投影到 UTM 51N（EPSG:32651，上海标准分带）重算面积，
     输出 `面积_平方公里`（2 位小数）；
  4. 几何有效性：`is_valid` 校验，无效几何 `buffer(0)` 修复并记录；
  5. 质心（用于标注/空间连接兜底）：同样在 UTM 下计算后转回 WGS84。

【运行】
  python processing/E_cleaning_district.py
  python processing/E_cleaning_district.py --district-file "D:\\...\\区级数据.shp"
================================================================================
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from pyproj import Transformer
from shapely.geometry import mapping, shape
from shapely.ops import transform as shp_transform

sys.path.insert(0, str(Path(__file__).resolve().parent))
from E_common import (  # noqa: E402
    DISTRICTS_16,
    check_district_triple,
    ensure_dir,
    find_district_file,
    is_header_row,
    is_total,
    log,
    missing_report,
    normalize_district,
    project_root,
    section,
    write_csv,
)
from E_common import default_team_data  # noqa: E402

WGS84 = "EPSG:4326"
UTM51N = "EPSG:32651"          # 上海标准分带（中央经线 123°E）


def load_districts(path: Path):
    """读取区界，返回 [(区名, geometry, 原始属性dict)]。"""
    path = Path(path)
    if path.suffix.lower() == ".shp":
        import shapefile  # pyshp
        with shapefile.Reader(str(path)) as r:
            fields = [f[0] for f in r.fields[1:]]
            out = []
            for sr in r.shapeRecords():
                props = dict(zip(fields, sr.record))
                name = props.get("district") or props.get("name") or props.get("NAME")
                out.append((normalize_district(name),
                            shape(sr.shape.__geo_interface__), props))
        return out

    with open(path, encoding="utf-8") as f:
        gj = json.load(f)
    return [(normalize_district(ft["properties"].get("district")
                                or ft["properties"].get("name")),
             shape(ft["geometry"]), ft["properties"]) for ft in gj["features"]]


def main() -> int:
    ap = argparse.ArgumentParser(description="行政区划数据清洗（P0-3）")
    ap.add_argument("--team-data", default=None)
    ap.add_argument("--district-file", default=None)
    ap.add_argument("--cleaned", default=None)
    args = ap.parse_args()

    root = project_root()
    team = Path(args.team_data) if args.team_data else default_team_data()
    cleaned = Path(args.cleaned) if args.cleaned else root / "data" / "cleaned"
    ensure_dir(cleaned)

    section("P0-3 行政区划 · 读取与校验")
    dfile = Path(args.district_file) if args.district_file else find_district_file(team)
    if dfile is None or not Path(dfile).exists():
        log("[错误] 未找到区界文件（区级数据.shp / .geojson）")
        return 1

    districts = load_districts(Path(dfile))
    log(f"  区界文件：{Path(dfile).name}（{len(districts)} 个要素）")

    # 剔除汇总/表头行
    before = len(districts)
    districts = [(n, g, p) for n, g, p in districts
                 if n and not is_total(n) and not is_header_row(n)]
    if before != len(districts):
        log(f"  [清洗] 剔除汇总/表头行 {before - len(districts)} 条")
    assert len(districts) == 16, f"期望 16 区，实际 {len(districts)}"

    # 几何有效性
    bad = [n for n, g, _ in districts if not g.is_valid]
    if bad:
        log(f"  [几何修复] 无效几何 {len(bad)} 个，buffer(0)：{bad}")
        districts = [(n, g.buffer(0) if not g.is_valid else g, p)
                     for n, g, p in districts]
    else:
        log("  [几何校验] 16 区几何全部有效")

    # 面积重算（UTM 51N）
    to_utm = Transformer.from_crs(WGS84, UTM51N, always_xy=True)
    to_wgs = Transformer.from_crs(UTM51N, WGS84, always_xy=True)

    rows, feats = [], []
    for name, geom, props in districts:
        g_utm = shp_transform(lambda x, y: to_utm.transform(x, y), geom)
        area_km2 = round(g_utm.area / 1_000_000.0, 2)
        cx, cy = to_wgs.transform(g_utm.centroid.x, g_utm.centroid.y)
        rows.append({
            "区名": name,
            "adcode": props.get("adcode"),
            "面积_平方公里": area_km2,
            "质心经度": round(cx, 6),
            "质心纬度": round(cy, 6),
        })
        feats.append({
            "type": "Feature",
            "properties": {"区名": name, "adcode": props.get("adcode"),
                           "面积_平方公里": area_km2},
            "geometry": mapping(geom),
        })

    df = pd.DataFrame(rows)
    df["_o"] = df["区名"].map({d: i for i, d in enumerate(DISTRICTS_16)})
    df = df.sort_values("_o").drop(columns="_o").reset_index(drop=True)

    # 原始 Shape_Area 对照（平方度，不可用，仅作说明）
    log(f"  面积已按 UTM 51N 重算；原始 Shape_Area 为平方度，已弃用")
    log("  [缺失值]\n" + missing_report(df).to_string(index=False))
    check_district_triple({"区划": set(df["区名"])})

    out_gj = cleaned / "cleaned_district.geojson"
    out_gj.write_text(json.dumps(
        {"type": "FeatureCollection",
         "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
         "features": feats},
        ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"  写出 {out_gj.relative_to(root)}")

    write_csv(df, cleaned / "cleaned_district.csv")

    # 可选：gpkg（标准 2.1 首选交付格式，需 geopandas）
    try:
        import geopandas as gpd
        gdf = gpd.GeoDataFrame(df, geometry=[g for _, g, _ in districts],
                               crs=WGS84)
        gp = cleaned / "cleaned_district.gpkg"
        gdf.to_file(gp, driver="GPKG")
        log(f"  写出 {gp.relative_to(root)}（GeoPackage）")
    except Exception as e:  # geopandas 未安装或驱动不可用 -> 降级为 geojson
        log(f"  [提示] 未导出 .gpkg（{type(e).__name__}）；"
            f"已用 .geojson + .csv 交付，安装 geopandas 后可自动补出")

    section("P0-3 行政区划清洗完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
