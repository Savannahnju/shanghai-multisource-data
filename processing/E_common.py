# -*- coding: utf-8 -*-
"""
E 数据清洗公共工具（供 processing/E_cleaning_*.py 六个脚本复用）

统一落实《数据清洗标准（草案）》第二章「统一标准」：
  2.1 文件与编码   -> write_csv() 统一 utf-8-sig、列名去空格、空值留空
  2.3 实体规范：区名 -> normalize_district() / DISTRICTS_16
  2.6 缺失值       -> missing_report()
  2.8 异常值       -> iqr_flags()（仅标记不删除）
  2.11 可追溯      -> log() 统一日志前缀，便于复制到清洗报告
  2.12 样本规范    -> sample_by_group()

输入路径全部参数化：优先 --参数 > 环境变量 SH_TEAM_DATA > 相对推导，
脚本内不写死任何绝对路径，换机器可直接运行。
"""
from __future__ import annotations

import io
import os
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- 路径

def project_root() -> Path:
    """
    项目根目录。

    优先级：环境变量 E_PROJECT_ROOT > 脚本所在目录的上一级。
    设了 E_PROJECT_ROOT 后，脚本可从任意位置运行（例如交付包里的 脚本/ 目录），
    输出仍写到该根目录下的 data/cleaned 与 data/processed。
    """
    env = os.environ.get("E_PROJECT_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


def default_team_data() -> Path:
    """
    团队原始数据目录（BCD + E 的全部原始文件所在）。
    优先级：环境变量 SH_TEAM_DATA > 相对推导 > 项目内 data/raw。
    """
    env = os.environ.get("SH_TEAM_DATA")
    if env:
        return Path(env)
    guess = project_root().parent / "绿地占比、植被韧性" / "data"
    if guess.exists():
        return guess
    return project_root() / "data" / "raw"


def ensure_dir(p: Path | str) -> Path:
    p = Path(p)
    p.mkdir(parents=True, exist_ok=True)
    return p


def find_district_file(team: Path | None = None) -> Path | None:
    """
    定位 A 提供的权威区界。

    团队附件实际结构（易漏）：
      <team-data>/上海市行政区划-乡镇级shp文件/
          shp/区级数据.shp + .prj      <- 优先（.prj 明确 WGS84）
          shp2/乡镇级数据.shp + .prj   <- 乡镇级，本期不下钻
          区级数据.geojson / 乡镇级数据.geojson

    优先返回带 .prj 的 shp；找不到再退回 geojson。
    """
    team = Path(team) if team else default_team_data()
    d = team / "上海市行政区划-乡镇级shp文件"
    candidates = [
        d / "shp" / "区级数据.shp",
        d / "区级数据.shp",
        d / "区级数据.geojson",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


# ---------------------------------------------------------------- 区名（跨源唯一主键）

DISTRICTS_16 = [
    "黄浦区", "徐汇区", "长宁区", "静安区", "普陀区", "虹口区", "杨浦区",
    "闵行区", "宝山区", "嘉定区", "浦东新区", "金山区", "松江区",
    "青浦区", "奉贤区", "崇明区",
]

_WS = re.compile(r"[\s\u3000]+")            # 半角空白 + 全角空格 U+3000
_TOTAL = re.compile(r"^(总\s*计|全\s*市|合计|小\s*计|全市)$")
_PREFIX_SH = re.compile(r"^(上海市|上海)")
# 表头行写法（年鉴双行表头常见："地  区" / "区  名" / "行  政  区"）
_HEADER_ROW = {"地区", "区名", "区县", "行政区", "区域", "名称", "区划"}
# 表标题行（如 "表10.17 各区绿化面积（2024）"）
_TITLE_ROW = re.compile(r"^表\s*\d|^\d+\.\d+\s")


def clean_ws(x) -> str:
    """去首尾与内部所有空白（含全角空格）。非字符串安全转换。"""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return ""
    s = _WS.sub("", str(x))
    return s


def is_total(x) -> bool:
    """判定是否为汇总行（总计/全市）。"""
    return bool(_TOTAL.match(clean_ws(x)))


def is_header_row(x) -> bool:
    """判定是否为表头行（'地  区' / '区  名' 等）或表标题行。"""
    s = clean_ws(x)
    if not s:
        return True
    return s in _HEADER_ROW or bool(_TITLE_ROW.match(s))


def normalize_district(x) -> str:
    """
    区名标准化：
      1) 去首尾与内部空白（含全角空格，年鉴原表有 '  浦东新区'）
      2) 去 '上海市' 前缀
      3) 缺 '区' 字则补齐（'浦东' -> '浦东新区' 的特例另行处理）
      非区级实体（如 '上海市外（昆山）'）原样返回。
    """
    s = clean_ws(x)
    if not s:
        return ""
    # 昆山特例必须在去"上海市"前缀**之前**判定，
    # 否则 "上海市外（昆山）" 会被剥成 "外（昆山）" 再补成 "外（昆山）区"
    if "昆山" in s:
        return "上海市外（昆山）"
    s = _PREFIX_SH.sub("", s)
    # 汇总行与表头行原样返回：否则 "总计" 会被误补成 "总计区"
    if is_total(s) or is_header_row(s):
        return s
    if not s.endswith("区"):
        # 常见简称补全
        alias = {"浦东": "浦东新区", "崇明": "崇明区", "奉贤": "奉贤区", "金山": "金山区"}
        s = alias.get(s, s + "区")
    return s


def check_district_triple(sets: dict[str, set], label: str = "") -> bool:
    """
    三方区名校验（标准 2.3 第 5 条）。
    sets: {'区划': {...}, '年鉴': {...}, '空气': {...}}
    返回 True/False，并打印差异。
    """
    ok = True
    std = set(DISTRICTS_16)
    for name, s in sets.items():
        miss = std - s
        extra = s - std
        if miss:
            ok = False
            log(f"  [区名校验] {name} 缺失 {len(miss)}: {sorted(miss)}")
        if extra:
            ok = False
            log(f"  [区名校验] {name} 多出 {len(extra)}: {sorted(extra)}")
        if not miss and not extra:
            log(f"  [区名校验] {name} 16/16 一致")
    if ok:
        log(f"  [区名校验] {label or ''}三方区名完全一致（16/16）")
    return ok


# ---------------------------------------------------------------- IO

def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """列名去首尾空格（含全角），并去除可能的 BOM。"""
    df = df.copy()
    df.columns = [clean_ws(c).lstrip("\ufeff") for c in df.columns]
    return df


def write_csv(df: pd.DataFrame, path: Path | str, *, index: bool = False) -> Path:
    """
    统一写出：UTF-8 with BOM（Excel 直开不乱码）、空值留空、LF 换行。
    """
    path = Path(path)
    ensure_dir(path.parent)
    df.to_csv(path, index=index, encoding="utf-8-sig", lineterminator="\n")
    log(f"  写出 {path.relative_to(project_root())}  ({len(df):,} 行 × {df.shape[1]} 列)")
    return path


def read_zip_csv(zip_path: Path | str, member: str, **kw) -> pd.DataFrame:
    """读取 zip 内的 csv（用于 Zenodo 补充包）。"""
    zip_path = Path(zip_path)
    with zipfile.ZipFile(zip_path) as z:
        return pd.read_csv(io.BytesIO(z.read(member)), **kw)


# ---------------------------------------------------------------- 质量报告

def missing_report(df: pd.DataFrame) -> pd.DataFrame:
    """每字段缺失条数 / 缺失率（%）。"""
    n = len(df)
    na = df.isna().sum()
    return pd.DataFrame({
        "字段": df.columns,
        "缺失条数": na.values,
        "缺失率(%)": (na.values / n * 100).round(2) if n else 0.0,
    })


def iqr_flags(s: pd.Series, k: float = 1.5) -> pd.Series:
    """IQR 异常标记（布尔 Series）。仅标记，不删除（标准 2.8）。"""
    v = pd.to_numeric(s, errors="coerce")
    q1, q3 = v.quantile(0.25), v.quantile(0.75)
    iqr = q3 - q1
    if pd.isna(iqr) or iqr == 0:
        return pd.Series(False, index=s.index)
    return (v < q1 - k * iqr) | (v > q3 + k * iqr)


def range_check(df: pd.DataFrame, col: str, lo: float | None, hi: float | None) -> pd.Series:
    """值域校验，返回越界布尔 Series（True = 异常）。"""
    v = pd.to_numeric(df[col], errors="coerce")
    bad = pd.Series(False, index=df.index)
    if lo is not None:
        bad |= v < lo
    if hi is not None:
        bad |= v > hi
    return bad.fillna(True)  # 无法解析为数值亦视为异常


# ---------------------------------------------------------------- 抽样（标准 2.12）

def sample_by_group(df: pd.DataFrame, group_col: str, values: list, random_state: int = 42):
    """
    按完整语义单元抽样：取 group_col ∈ values 的全部行。
    用于地铁（抽 2 个完整日）等必须保住结构的场景。
    """
    return df[df[group_col].isin(values)].copy()


def sample_frac(df: pd.DataFrame, frac: float, random_state: int = 42):
    """简单随机抽样（POI 1%）。"""
    return df.sample(frac=frac, random_state=random_state).copy()


def file_size_mb(p: Path | str) -> float:
    return Path(p).stat().st_size / 1024 / 1024


# ---------------------------------------------------------------- 日志

def log(msg: str) -> None:
    print(msg, flush=True)


def section(title: str) -> None:
    log("\n" + "=" * 68)
    log(title)
    log("=" * 68)
