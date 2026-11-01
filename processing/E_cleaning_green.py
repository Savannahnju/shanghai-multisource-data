# -*- coding: utf-8 -*-
"""
================================================================================
E_cleaning_green.py —— 绿地 / 植被韧性数据清洗（优先级 P0-2，D 的研究问题 3）
================================================================================

【输入】
  1) 植被韧性栅格（E 自有数据源二）
     data/raw/SH_Green_Resilience_1.0/
       2_Green_R/GREEN_R.TIF + .tfw    绿地占比 %
       3_STL_AR1/STL_AR1.TIF + .tfw    韧性（STL 分解）
       4_V2_AR1/V2_AR1.TIF   + .tfw    韧性（二阶 AR1）
       5_V2_VAR/V2_VAR.TIF   + .tfw    韧性（二阶方差）
  2) 区界（A 提供，权威）
     <team-data>/上海市行政区划-乡镇级shp文件/区级数据.shp 或 .geojson
  3) 统计年鉴（E 自有数据源一，2024）
     <team-data>/统计年鉴气象、绿化数据（2024年）/各区绿地面积.xls   （表10.17）
     <team-data>/统计年鉴气象、绿化数据（2024年）/各区人口密度.xls  （表2.2）

【输出】
  data/cleaned/cleaned_green.csv              区级宽表 16 行（Q3 分析主表）
  data/processed/green_resilience_zonal.csv   栅格分区统计结果（备查）
  data/processed/green_yearbook_green.csv     年鉴绿地清洗后
  data/processed/green_yearbook_pop.csv       年鉴人口清洗后

【关键口径（易错，务必遵守）】
  1. **两套绿地面积不可混用**
     - 遥感口径：Σ(区内有效像元 GREEN_R% × 6.25 公顷)，反映实际植被覆盖；
     - 年鉴口径：表10.17 规划统计绿地面积（公顷）。
     二者含义不同、量级相差约 6 倍，仅可互相印证，**严禁当作同一变量**。
  2. STL_AR1 负值 = 模型不适用（约 14.4%），统计时**剔除**，不得当作"低韧性"；
  3. V2_AR1 / V2_VAR 全为负，**越负韧性越强**（与直觉相反）；
  4. 像元归属按中心点 point-in-polygon，跨区边界像元存在少量归属误差；
  5. 四幅栅格用同一掩膜，像元数一致（16,745）。

【运行】
  python processing/E_cleaning_green.py
  python processing/E_cleaning_green.py --district-file "D:\\...\\区级数据.geojson"
================================================================================
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile
from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.prepared import prep

warnings.filterwarnings("ignore")

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
    range_check,
    section,
    standardize_columns,
    write_csv,
)
from E_common import default_team_data  # noqa: E402

# 栅格层：目录 -> 输出字段语义
LAYERS = {
    "GREEN_R": ("2_Green_R/GREEN_R", "绿地占比_%"),
    "STL_AR1": ("3_STL_AR1/STL_AR1", "STL_AR1均值"),
    "V2_AR1": ("4_V2_AR1/V2_AR1", "V2_AR1均值"),
    "V2_VAR": ("5_V2_VAR/V2_VAR", "V2_VAR均值"),
}
PIXEL_AREA_HA = 250 * 250 / 10000.0  # 6.25 公顷/像元

# 年鉴两个表的固定列名（行2 指标名 + 行3 单位，已人工核对）
YB_GREEN_COLS = ["区名", "绿地面积(公顷)", "公园绿地面积(公顷)",
                 "公园数(个)", "公园面积(公顷)", "公园游园人数(万人次)"]
YB_POP_COLS = ["区名", "行政区域面积(平方公里)", "年末常住人口(万人)",
               "外来人口(万人)", "人口密度(人/平方公里)"]


# ---------------------------------------------------------------- 区界

def load_districts(path: Path):
    """返回 [(区名, geometry)]，区名已标准化。"""
    path = Path(path)
    if path.suffix.lower() == ".shp":
        import shapefile  # pyshp
        with shapefile.Reader(str(path)) as r:
            fields = [f[0] for f in r.fields[1:]]
            out = []
            for rec in r.shapeRecords():
                props = dict(zip(fields, rec.record))
                name = props.get("district") or props.get("name") or props.get("NAME")
                geom = shape(rec.shape.__geo_interface__)
                out.append((normalize_district(name), geom))
        return out

    with open(path, encoding="utf-8") as f:
        gj = json.load(f)
    out = []
    for ft in gj["features"]:
        p = ft["properties"]
        name = p.get("district") or p.get("name") or p.get("NAME")
        out.append((normalize_district(name), shape(ft["geometry"])))
    return out


# ---------------------------------------------------------------- 栅格

def load_rasters(raster_dir: Path):
    """读取四幅栅格 + 生成统一有效掩膜。"""
    layers, valid = {}, None
    for key, (sub, _) in LAYERS.items():
        tif = raster_dir / f"{sub}.TIF"
        if not tif.exists():
            log(f"  [警告] 缺少栅格 {tif}")
            continue
        a = tifffile.imread(str(tif))
        layers[key] = a
        m = np.isfinite(a) & (np.abs(a) < 1e30)
        valid = m if valid is None else (valid & m)
    return layers, valid


def raster_centroids_lonlat(raster_dir: Path, shape_hw):
    """由 .tfw 世界文件解算像元中心点经纬度（UTM 49N -> WGS84）。"""
    tfw = raster_dir / f"{LAYERS['GREEN_R'][0]}.tfw"
    A, B, C, D, E, F = [float(x) for x in tfw.read_text().split()]
    rows, cols = shape_hw
    rr, cc = np.mgrid[0:rows, 0:cols]
    utm_x = E + (cc + 0.5) * A      # 东向
    utm_y = F + (rr + 0.5) * D      # 北向（D 为负）
    tr = Transformer.from_crs("EPSG:32649", "EPSG:4326", always_xy=True)
    lon, lat = tr.transform(utm_x, utm_y)
    return lon, lat


def pixel_counts(lon, lat, districts) -> pd.DataFrame:
    """
    统计落入各区的**全部**像元数（含非绿地像元）。
    用于计算「绿地覆盖率 = 遥感绿地面积 / (区内像元数 × 6.25 公顷)」，
    与 GREEN_R 的「有效像元占比」是两个不同口径，需区分。

    返回带 `区名` 的 DataFrame，供 merge 使用
    ——切勿按位置赋值给已排序的表，会导致区号错位。
    """
    rows = []
    for name, geom in districts:
        minx, miny, maxx, maxy = geom.bounds
        m = (lon >= minx) & (lon <= maxx) & (lat >= miny) & (lat <= maxy)
        rr, cc = np.nonzero(m)
        pg = prep(geom)
        n = sum(1 for r, c in zip(rr, cc)
                if pg.contains(Point(lon[r, c], lat[r, c])))
        rows.append({"区名": name, "区内像元总数": n})
    return pd.DataFrame(rows)


def zonal_stats(layers, valid, lon, lat, districts):
    """
    分区统计：按像元中心点归属（point-in-polygon）。
    prepared geometry 加速；边界像元归属歧义在报告中说明。
    """
    vidx = np.argwhere(valid)
    n = len(vidx)
    assign = np.full(n, -1, dtype=int)

    prepped = [prep(g) for _, g in districts]
    for di, pg in enumerate(prepped):
        todo = np.where(assign == -1)[0]
        if len(todo) == 0:
            break
        pts = vidx[todo]
        # prepared geometry 与精确 contains 语义一致，仅用于加速；
        # 已归属的像元不再参与后续区的判定，保证"先命中先归属"。
        hit = np.array([pg.contains(Point(lon[r, c], lat[r, c])) for r, c in pts])
        assign[todo[hit]] = di

    unassigned = int((assign == -1).sum())
    log(f"  有效像元 {n:,}；未落入 16 区界 {unassigned:,}")

    rows = []
    for di, (dname, _) in enumerate(districts):
        sel = assign == di
        cnt = int(sel.sum())
        rec = {"区名": dname, "有效绿地像元数": cnt}
        if cnt == 0:
            rows.append(rec)
            continue
        r, c = vidx[sel][:, 0], vidx[sel][:, 1]
        gr = layers["GREEN_R"][r, c]
        stl = layers["STL_AR1"][r, c]
        v2a = layers["V2_AR1"][r, c]
        v2v = layers["V2_VAR"][r, c]
        stl_pos = stl[stl >= 0]                       # 剔除"模型不适用"
        rec.update({
            "遥感绿地占比均值_%": round(float(gr.mean()), 2),
            "遥感绿地占比中位数_%": round(float(np.median(gr)), 2),
            "遥感绿地面积_公顷": round(float((gr / 100.0 * PIXEL_AREA_HA).sum()), 1),
            "STL_AR1均值_剔除负值": round(float(stl_pos.mean()), 4) if stl_pos.size else None,
            "STL_AR1负值占比_%": round(float((stl < 0).mean() * 100), 1),
            "V2_AR1均值": round(float(v2a.mean()), 4),
            "V2_VAR均值": round(float(v2v.mean()), 4),
        })
        rows.append(rec)

    df = pd.DataFrame(rows)
    df["_o"] = df["区名"].map({d: i for i, d in enumerate(DISTRICTS_16)})
    df = df.sort_values("_o").drop(columns="_o").reset_index(drop=True)
    return df


# ---------------------------------------------------------------- 年鉴

def parse_yearbook(path: Path, cols: list[str]) -> pd.DataFrame:
    """
    解析年鉴宽表：标题(行0) / 空行(行1) / 指标名(行2) / 单位(行3) / 数据(行4起)。
    行4 为汇总行（总计/全市），剔除后应恰为 16 区。
    """
    raw = pd.read_excel(path, header=None)
    body = raw.iloc[4:, : len(cols)].copy()
    body.columns = cols
    body["区名"] = body["区名"].map(normalize_district)
    body = body[~body["区名"].map(is_total)]
    body = body[~body["区名"].map(is_header_row)]
    body = body[body["区名"] != ""]
    for c in cols[1:]:
        body[c] = pd.to_numeric(body[c], errors="coerce")
    body["_o"] = body["区名"].map({d: i for i, d in enumerate(DISTRICTS_16)})
    body = body.sort_values("_o").drop(columns="_o").reset_index(drop=True)
    return body


# ---------------------------------------------------------------- 主流程

def main() -> int:
    ap = argparse.ArgumentParser(description="绿地/植被韧性数据清洗（P0-2）")
    ap.add_argument("--team-data", default=None, help="团队原始数据目录")
    ap.add_argument("--raster-dir", default=None, help="植被韧性栅格目录")
    ap.add_argument("--district-file", default=None, help="区界文件（shp/geojson）")
    ap.add_argument("--cleaned", default=None)
    ap.add_argument("--processed", default=None)
    args = ap.parse_args()

    root = project_root()
    team = Path(args.team_data) if args.team_data else default_team_data()
    raster_dir = (Path(args.raster_dir) if args.raster_dir
                  else root / "data" / "raw" / "SH_Green_Resilience_1.0")
    cleaned = Path(args.cleaned) if args.cleaned else root / "data" / "cleaned"
    processed = Path(args.processed) if args.processed else root / "data" / "processed"
    ensure_dir(cleaned)
    ensure_dir(processed)

    # ---------- 区界 ----------
    section("P0-2 绿地 · 区界读取")
    dfile = Path(args.district_file) if args.district_file else find_district_file(team)
    if dfile is None or not Path(dfile).exists():
        log("[错误] 未找到 A 提供的区界文件（区级数据.shp / .geojson）")
        return 1
    districts = load_districts(Path(dfile))
    log(f"  区界文件：{Path(dfile).name}（{len(districts)} 个区）")
    assert len(districts) == 16, f"期望 16 区，实际 {len(districts)}"

    # 几何有效性
    from shapely.geometry import Polygon, MultiPolygon
    bad = [n for n, g in districts if not g.is_valid]
    if bad:
        log(f"  [几何修复] 无效几何 {len(bad)} 个，已 buffer(0)：{bad}")
        districts = [(n, g.buffer(0) if not g.is_valid else g) for n, g in districts]
    else:
        log("  [几何校验] 16 区几何全部有效")

    # ---------- 栅格分区统计 ----------
    section("P0-2 绿地 · 栅格分区统计")
    layers, valid = load_rasters(raster_dir)
    log(f"  读入 {len(layers)} 幅栅格；统一掩膜有效像元 {int(valid.sum()):,}")
    lon, lat = raster_centroids_lonlat(raster_dir, layers["GREEN_R"].shape)
    log(f"  经纬度范围：{lon.min():.3f}~{lon.max():.3f}°E，{lat.min():.3f}~{lat.max():.3f}°N")
    zonal = zonal_stats(layers, valid, lon, lat, districts)

    # 区内像元总数（含非绿地）-> 绿地覆盖率
    log("  统计各区像元总数（含非绿地）…")
    totals = pixel_counts(lon, lat, districts)
    zonal = zonal.merge(totals, on="区名", how="left")
    zonal["绿地覆盖率_%"] = (
        zonal["遥感绿地面积_公顷"] / (zonal["区内像元总数"] * PIXEL_AREA_HA) * 100
    ).round(2)
    # 合理性断言：覆盖率不可能超过 100%
    over = zonal["绿地覆盖率_%"] > 100
    if over.any():
        log(f"  [异常] 覆盖率 >100%：{zonal.loc[over, ['区名', '绿地覆盖率_%']].to_dict('records')}")

    zero = zonal.loc[zonal["有效绿地像元数"] == 0, "区名"].tolist()
    if zero:
        log(f"  [重要] 有效绿地像元为 0 的区：{zero}")
        log("         高度城市化中心城区，NDVI/Dynamic World 未判为绿地；")
        log("         这些区在 Q3 植被分析中会缺失，样本量 16 → "
            f"{16 - len(zero)}，须在报告中说明。")

    write_csv(zonal, processed / "green_resilience_zonal.csv")

    # 值域校验
    bad_gr = range_check(zonal, "遥感绿地占比均值_%", 0, 100)
    log(f"  [值域校验] 绿地占比均值 0–100：越界 {int(bad_gr.sum())} 条")
    log(f"  [方向提示] V2_AR1/V2_VAR 越负韧性越强；STL_AR1 负值已剔除")

    # ---------- 年鉴 ----------
    section("P0-2 绿地 · 年鉴绿地面积与人口密度")
    yb_dir = team / "统计年鉴气象、绿化数据（2024年）"
    g = parse_yearbook(yb_dir / "各区绿地面积.xls", YB_GREEN_COLS)
    p = parse_yearbook(yb_dir / "各区人口密度.xls", YB_POP_COLS)
    log(f"  年鉴绿地：{g.shape}；年鉴人口：{p.shape}")
    log("  [缺失值·绿地]\n" + missing_report(g).to_string(index=False))
    log("  [缺失值·人口]\n" + missing_report(p).to_string(index=False))
    # 人口密度 14 位小数 -> 2 位
    p["人口密度(人/平方公里)"] = p["人口密度(人/平方公里)"].round(2)
    write_csv(g, processed / "green_yearbook_green.csv")
    write_csv(p, processed / "green_yearbook_pop.csv")

    # ---------- 合并为区级宽表 ----------
    section("P0-2 绿地 · 合并区级宽表")
    wide = g.merge(p, on="区名", how="outer").merge(zonal, on="区名", how="outer")
    wide["_o"] = wide["区名"].map({d: i for i, d in enumerate(DISTRICTS_16)})
    wide = wide.sort_values("_o").drop(columns="_o").reset_index(drop=True)
    log(f"  合并后：{wide.shape[0]} 行 × {wide.shape[1]} 列")

    # 口径参照（不混用）
    if "遥感绿地面积_公顷" in wide and "绿地面积(公顷)" in wide:
        r_sum = wide["遥感绿地面积_公顷"].sum()
        y_sum = wide["绿地面积(公顷)"].sum()
        log(f"  [口径参照] 遥感绿地合计 {r_sum:,.1f} 公顷 vs 年鉴绿地合计 {y_sum:,.1f} 公顷"
            f"（比值 {y_sum / r_sum:.2f}×）—— 口径不同，仅互证不混用")

    check_district_triple({"绿地宽表": set(wide["区名"])})
    write_csv(wide, cleaned / "cleaned_green.csv")

    section("P0-2 绿地清洗完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
