# -*- coding: utf-8 -*-
"""
C_sample_raw_data.py —— C 负责数据（上海市行政区划 GeoJSON）抽样脚本

功能：
    从原始行政区划 GeoJSON 中生成上传 GitHub 用的代表性抽样样本。
    1. 区级数据（16 个区，文件本身即为小样本）：原样保留全部要素与几何精度；
    2. 乡镇级数据（214 个街镇乡）：按"中心城区 / 近郊 / 远郊岛屿"分层，
       抽取 黄浦区、青浦区、崇明区 三个区的全部乡镇（共 39 个要素），
       保证抽样同时覆盖三种典型空间形态。

输入（在仓库根目录运行时）：
    ../Data/上海市行政区划-乡镇级shp文件/区级数据.geojson
    ../Data/上海市行政区划-乡镇级shp文件/乡镇级数据.geojson
    （原始数据不入库，仅本地持有；可用 --src 指定其他路径）

输出：
    data/raw/raw_C_district_sample.geojson   区级抽样（16 要素）
    data/raw/raw_C_township_sample.geojson   乡镇级抽样（39 要素）

运行：
    python processing/C_sample_raw_data.py --src "../Data/上海市行政区划-乡镇级shp文件"
"""

import argparse
import json
import os
import sys

# 乡镇级分层抽样：三个区代表中心城区 / 近郊 / 远郊岛屿
SAMPLE_DISTRICTS = ["黄浦区", "青浦区", "崇明区"]

FILES = {
    "district": ("区级数据.geojson", "raw_C_district_sample.geojson", None),
    "township": ("乡镇级数据.geojson", "raw_C_township_sample.geojson", SAMPLE_DISTRICTS),
}


def filter_features(features, districts):
    if districts is None:
        return features
    if "district" in features[0]["properties"]:
        key = "district"
    else:
        key = "AREA"
    return [f for f in features if f["properties"].get(key) in districts]


def make_sample(src_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for level, (src_name, out_name, districts) in FILES.items():
        src_path = os.path.join(src_dir, src_name)
        with open(src_path, encoding="utf-8") as f:
            gj = json.load(f)
        feats = filter_features(gj["features"], districts)
        sample = {"type": "FeatureCollection", "features": feats}
        out_path = os.path.join(out_dir, out_name)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(sample, f, ensure_ascii=False, separators=(",", ":"))
        size_kb = os.path.getsize(out_path) / 1024
        print(f"[OK] {level}: {len(feats)} 要素 -> {out_path} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="生成行政区划 GeoJSON 抽样样本")
    parser.add_argument("--src", default="../Data/上海市行政区划-乡镇级shp文件",
                        help="原始 GeoJSON 所在目录")
    parser.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "data", "raw"),
                        help="抽样输出目录")
    args = parser.parse_args()
    make_sample(args.src, os.path.abspath(args.out))
