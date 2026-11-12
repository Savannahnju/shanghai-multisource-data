#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键复现入口 —— 上海市多源城市数据分析（小组 ABCDE）.

用法:
    python reproduce.py --team-data ./raw_data --sh-base .
    python reproduce.py --check
    python reproduce.py --skip-cleaning --only B,C,D

执行顺序: E 清洗 -> B/C/D 融合 -> 分析 -> 可视化.
任一步失败默认立即停止; --keep-going 可继续.
"""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Windows 控制台/管道下默认可能是 GBK，统一为 UTF-8，避免中文乱码
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent


@dataclass
class Step:
    key: str
    name: str
    scripts: list[str]
    outputs: list[str] = field(default_factory=list)
    rows: dict[str, int] = field(default_factory=dict)
    modules: tuple[str, ...] = ("E", "B", "C", "D")
    needs_team_data: bool = False
    needs_sh_base: bool = False


STEPS: list[Step] = [
    # ---------------- E 清洗 ----------------
    Step("E1", "E 清洗·空气", ["processing/E_cleaning_air.py"],
         ["data/cleaned/cleaned_air_monthly.csv"], {"data/cleaned/cleaned_air_monthly.csv": 384},
         modules=("E",), needs_team_data=True),
    Step("E2", "E 清洗·植被与年鉴", ["processing/E_cleaning_green.py"],
         ["data/cleaned/cleaned_green.csv"], {"data/cleaned/cleaned_green.csv": 16},
         modules=("E",), needs_team_data=True),
    Step("E3", "E 清洗·行政区划", ["processing/E_cleaning_district.py"],
         ["data/cleaned/cleaned_district.gpkg", "data/cleaned/cleaned_district.geojson"],
         modules=("E",), needs_team_data=True),
    Step("E4", "E 清洗·地铁客流", ["processing/E_cleaning_metro.py"],
         ["data/cleaned/cleaned_metro_sample.csv"], {"data/cleaned/cleaned_metro_sample.csv": 30498},
         modules=("E",), needs_team_data=True),
    Step("E5", "E 清洗·气象", ["processing/E_cleaning_weather.py"],
         ["data/cleaned/cleaned_weather_hourly.csv"], {"data/cleaned/cleaned_weather_hourly.csv": 2808},
         modules=("E",), needs_team_data=True),
    Step("E6", "E 清洗·POI", ["processing/E_cleaning_poi.py"],
         ["data/cleaned/cleaned_poi_sample.csv"], {"data/cleaned/cleaned_poi_sample.csv": 13399},
         modules=("E",), needs_team_data=True),
    Step("E7", "E 交接宽表", ["processing/E_handoff_tables.py"],
         ["data/cleaned/cleaned_metro_month_district.csv",
          "data/cleaned/cleaned_poi_district_industry.csv",
          "data/cleaned/cleaned_green_analysis_wide.csv"],
         {"data/cleaned/cleaned_metro_month_district.csv": 52,
          "data/cleaned/cleaned_poi_district_industry.csv": 208,
          "data/cleaned/cleaned_green_analysis_wide.csv": 16},
         modules=("E",), needs_team_data=True),

    # ---------------- B Q1 ----------------
    Step("B1", "B 融合（Q1 区 × 月宽表）",
         ["processing/fuse_environment_metro.py",
          "Q1_融合分析/可复现脚本/fuse_environment_metro.py"],
         ["output/fused_environment_metro_2017.csv",
          "data/integrated/integrated_B_Q1_sample.csv"],
         {"output/fused_environment_metro_2017.csv": 52}, modules=("B",)),
    Step("B2", "B 分析（相关 + OLS M1–M5）", ["analysis/analyze_q1.py"],
         ["output/analysis_summary.txt"], modules=("B",)),
    Step("B3", "B 可视化（4 图）", ["visualization/B_Q1_visualization.py"],
         ["visualization/figures/fig1_corr_heatmap.png",
          "figures/fig1_corr_heatmap.png"], modules=("B",)),

    # ---------------- C Q2 ----------------
    Step("C1", "C 分析流水线（8 阶段）", ["analysis/C_Q2_analysis.py"],
         ["analysis/output/03_相关性检验全表.csv",
          "analysis/output/06_Kmeans聚类.csv"], modules=("C",), needs_sh_base=True),
    Step("C2", "C 融合（16 × 36 宽表）", ["processing/C_Q2_integrate.py"],
         ["data/integrated/integrated_C_Q2_sample.csv"],
         {"data/integrated/integrated_C_Q2_sample.csv": 16}, modules=("C",), needs_sh_base=True),
    Step("C3", "C 可视化（9 图）", ["visualization/C_Q2_visualization.py"],
         ["visualization/figures/fig1_C_industry_axis_pc1.png",
          "figures/fig1_C_industry_axis_pc1.png"], modules=("C",), needs_sh_base=True),

    # ---------------- D Q3 ----------------
    Step("D1", "D 融合（16 × 17 宽表）",
         ["processing/D_Q2_integrate.py", "D/processing/D_Q2_integrate.py"],
         ["D/data/integrated/主表_区级宽表.csv",
          "data/integrated/integrated_D_Q3_sample_主表_区级宽表.csv"], modules=("D",)),
    Step("D2", "D 分析（相关 + KMeans）",
         ["analysis/D_Q2_analysis.py", "D/analysis/D_Q2_analysis.py"],
         ["D/analysis/D_Q2_analysis_results.txt",
          "analysis/D_Q2_analysis_results.txt"], modules=("D",)),
    Step("D3", "D 可视化（5 图）",
         ["visualization/D_Q2_visualization.py", "D/visualization/D_Q2_visualization.py"],
         ["D/visualization/figures/fig1_绿地占比与AQI优良率.png",
          "visualization/figures/fig1_绿地占比与AQI优良率.png"], modules=("D",)),
]


def log(msg: str) -> None:
    print(msg, flush=True)


def find_script(step: Step) -> Path | None:
    for rel in step.scripts:
        p = ROOT / rel
        if p.is_file():
            return p
    return None


def first_existing(paths: list[str]) -> Path | None:
    for rel in paths:
        p = ROOT / rel
        if p.exists():
            return p
    return None


def count_csv_rows(path: Path) -> int | None:
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
            reader = csv.reader(f)
            next(reader, None)
            return sum(1 for _ in reader)
    except Exception:
        return None


def validate(step: Step, verbose: bool = True) -> tuple[bool, list[str]]:
    problems: list[str] = []
    found_any = False
    for rel in step.outputs:
        p = ROOT / rel
        if not p.exists():
            continue
        found_any = True
        expected = step.rows.get(rel)
        if expected is not None and p.suffix.lower() == ".csv":
            actual = count_csv_rows(p)
            if actual is not None and actual != expected:
                problems.append(f"{rel}: 期望 {expected} 行，实际 {actual} 行")
            elif verbose and actual is not None:
                log(f"    ✓ {rel}: {actual} 行")
    if not found_any:
        problems.append("未找到任何期望产物: " + " / ".join(step.outputs))
    return (not problems), problems


def make_dir_link(src: Path, dst: Path) -> bool:
    """创建目录链接（Windows 用 junction，无需管理员权限）。"""
    if dst.exists() or dst.is_symlink():
        return True
    if not src.exists():
        return False
    try:
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(dst), str(src)],
                           check=True, capture_output=True)
        else:
            os.symlink(src, dst, target_is_directory=True)
        return True
    except Exception:
        return False


def make_file_link(src: Path, dst: Path) -> bool:
    if dst.exists() or dst.is_symlink():
        return True
    if not src.exists():
        return False
    try:
        os.link(src, dst)  # 同卷硬链接，不占额外空间
        return True
    except Exception:
        try:
            os.symlink(src, dst)
            return True
        except Exception:
            return False


def prepare_compat_links(team_data: Path, need_c: bool) -> None:
    """为 B/C 的历史路径约定建立兼容链接。"""
    pairs_dir = [
        (team_data / "上海地铁客流量2017", ROOT / "上海地铁客流量2017"),
    ]
    if need_c:
        pairs_dir += [
            (ROOT / "data" / "cleaned", ROOT / "cleaned_Data"),
            (team_data, ROOT / "Data"),
        ]
    for src, dst in pairs_dir:
        if src.exists() and not dst.exists():
            ok = make_dir_link(src, dst)
            log(f"  [link] {dst.relative_to(ROOT)} -> {src} {'OK' if ok else 'FAILED'}")

    # B 的脚本也可能在仓库根目录直接读该 xlsx
    for name in ("2017年各区降尘量与PM2.5月均浓度.xlsx",):
        candidates = [team_data / name,
                      team_data / "上海地铁客流量2017" / name]
        src = next((p for p in candidates if p.exists()), None)
        dst = ROOT / name
        if src is not None and not dst.exists():
            ok = make_file_link(src, dst)
            log(f"  [link] {name} {'OK' if ok else 'FAILED (请手动复制到仓库根目录)'}")


def run_step(step: Step, script: Path, env: dict, isolate: bool, log_dir: Path | None) -> int:
    cmd = [sys.executable]
    if isolate:
        cmd.append("-I")
    cmd.append(str(script))

    log(f"\n>>> [{step.key}] {step.name}")
    log(f"    cmd: {' '.join(cmd)}")
    log(f"    cwd: {ROOT}")

    log_file = None
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = (log_dir / f"{step.key}.log").open("w", encoding="utf-8")

    proc = subprocess.Popen(
        cmd, cwd=str(ROOT), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        print(line, end="", flush=True)
        if log_file is not None:
            log_file.write(line)
    code = proc.wait()
    if log_file is not None:
        log_file.close()
    return code


def main() -> int:
    ap = argparse.ArgumentParser(description="上海市多源城市数据分析 · 一键复现")
    ap.add_argument("--team-data", default=str(ROOT / "raw_data"),
                    help="原始数据根目录（默认 ./raw_data）")
    ap.add_argument("--sh-base", default=str(ROOT),
                    help="C 脚本的 SH_BASE（默认仓库根目录）")
    ap.add_argument("--skip-cleaning", action="store_true", help="跳过 E 清洗")
    ap.add_argument("--only", default="", help="只跑指定成员，如 B 或 B,C,D")
    ap.add_argument("--check", action="store_true", help="只检查，不执行")
    ap.add_argument("--keep-going", action="store_true", help="单步失败后继续")
    ap.add_argument("--isolate", action="store_true", help="用 python -I 运行")
    ap.add_argument("--log-dir", default="logs", help="日志目录（默认 logs）")
    args = ap.parse_args()

    team_data = Path(args.team_data).expanduser().resolve()
    sh_base = Path(args.sh_base).expanduser().resolve()
    only = {x.strip().upper() for x in args.only.split(",") if x.strip()}
    log_dir = (ROOT / args.log_dir) if args.log_dir else None

    log("=" * 72)
    log("上海市多源城市数据分析 · 一键复现")
    log(f"仓库根目录 : {ROOT}")
    log(f"原始数据   : {team_data}")
    log(f"SH_BASE    : {sh_base}")
    log(f"Python     : {sys.version.split()[0]}")
    log("=" * 72)

    if not team_data.exists():
        log(f"[WARN] 原始数据目录不存在: {team_data}")
        log("       若 data/cleaned 已就绪，可加 --skip-cleaning；否则请按 README 5.2 放置数据。")

    need_c = (not only) or ("C" in only)
    if not args.check:
        prepare_compat_links(team_data, need_c)

    env = os.environ.copy()
    env["SH_TEAM_DATA"] = str(team_data)
    env["SH_BASE"] = str(sh_base)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    results: list[tuple[str, str, str]] = []
    checked_ok = True

    for step in STEPS:
        if only and not (set(step.modules) & only):
            continue
        if args.skip_cleaning and "E" in step.modules:
            continue

        script = find_script(step)
        if args.check:
            if script is None:
                results.append((step.key, step.name, "MISSING_SCRIPT"))
                checked_ok = False
                continue
            ok, problems = validate(step, verbose=False)
            status = "OK" if ok else "MISSING_OUTPUT"
            results.append((step.key, step.name, status))
            if not ok:
                checked_ok = False
                for p in problems:
                    log(f"  [check] {step.key}: {p}")
            continue

        if script is None:
            msg = "脚本未找到: " + " / ".join(step.scripts)
            results.append((step.key, step.name, "MISSING_SCRIPT"))
            log(f"\n[FAIL] {step.key}: {msg}")
            if not args.keep_going:
                break
            continue

        code = run_step(step, script, env, args.isolate, log_dir)
        if code != 0:
            results.append((step.key, step.name, f"FAILED(exit={code})"))
            log(f"\n[FAIL] {step.key} 退出码 {code}，详见 {log_dir / (step.key + '.log') if log_dir else '控制台'}")
            if not args.keep_going:
                break
            continue

        ok, problems = validate(step, verbose=True)
        if not ok:
            results.append((step.key, step.name, "OUTPUT_CHECK_FAILED"))
            for p in problems:
                log(f"  [check] {p}")
        else:
            results.append((step.key, step.name, "OK"))

    log("\n" + "=" * 72)
    log("复现结果汇总")
    log("=" * 72)
    for key, name, status in results:
        log(f"  {key:<3} {status:<20} {name}")

    if args.check:
        log("\n检查完成: " + ("全部通过" if checked_ok else "存在缺失项"))
        return 0 if checked_ok else 1

    failed = [r for r in results if r[2] != "OK"]
    log("\n完成: " + ("全部步骤通过" if not failed else f"{len(failed)} 个步骤未通过"))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
