# 《大数据系统和原理》中期大作业 —— 上海多源城市数据分析

围绕城市环境质量，整合地铁客流、空气质量、气象、POI、绿地、行政区划与统计年鉴等多源数据，以"区"为统一分析单元，完成采集 → 清洗 → 融合 → 分析 → 可视化全流程。

## 小组成员

| 成员 | 分工 |
|---|---|
| A | 统筹 / PPT / 写作 / 数据采集 |
| B | 研究问题 1 + 分析 |
| C | 研究问题 2 + 分析 |
| D | 研究问题 3 + 分析 |
| E | 数据清洗 |

**研究问题**：Q1 环境质量 × 地铁客流（B，区 × 月共 52 观测）；Q2 环境质量 × 产业结构（C，16 区）；Q3 环境质量 × 植被/绿地（D，16 区）。

## 数据源

| 数据源 | 内容与规模 | 获取方式 |
|---|---|---|
| 地铁客流 | MetroFlow，2017 年进出站流水，主表约 207.4 MB | [GitHub](https://github.com/Ariza-Sun/MetroFlow) + [figshare](https://doi.org/10.6084/m9.figshare.33436675)（MIT） |
| 行政区划 | 上海市乡镇级 SHP，16 区区界（WGS-84） | 政府公开数据 |
| 空气质量 | 2024-01—2025-12 区级月均，384 条（16 区 × 24 月） | 政府公开数据 / 组内共享 |
| POI 兴趣点 | 高德 POI（2025 截面）1,422,977 条 × 15 字段，约 2.4 GB | CSDN 资源包；仓库仅存抽样 |
| 绿地 | 绿地占比 / 植被韧性 250 m 栅格（UTM 49N） | [DOI 10.3974/geodb.2024.12.04.V1](https://doi.org/10.3974/geodb.2024.12.04.V1) |
| 气象 / 年鉴 | 逐小时气象、工作日历；绿地面积、人口密度 | MetroFlow `Data/`；《上海统计年鉴 2025》 |

全量原始数据不入仓库（GitHub 单文件限 100 MB），仅提交抽样样本、索引与校验值。

- **执行 AI 可自动获取**：MetroFlow 地铁客流、绿地栅格（DOI）。
- **必须人工提供**（需登录/付费/组内共享，AI 无法自行下载）：POI（CSDN 资源包）、空气质量（政府公开数据）、统计年鉴（组内共享）。缺任一项，对应模块无法复现。

**MetroFlow 下载**：

1. 打开 [figshare DOI](https://doi.org/10.6084/m9.figshare.33436675)，下载 `metroData_InOutFlow.csv`（约 207.4 MB）；
2. 打开 [Ariza-Sun/MetroFlow](https://github.com/Ariza-Sun/MetroFlow)，从 `Data/` 与 `Data/MetaData/` 下载 `stationInfo.csv`、`shanghai_weatherHourly.csv`、`workday_calendar.csv`；
3. 按下方目录放置后校验主表：

```bash
md5sum raw_data/上海地铁客流量2017/metroData_InOutFlow.csv
# 期望 c96e6be386c7abf1b6ab34f86a2fca4e
```

## 目录结构

```
shanghai-multisource-data/
├── reproduce.py                       # 一键复现入口
├── requirements.txt
├── data/
│   ├── raw/                           # 原始数据抽样/索引
│   ├── cleaned/                       # E 清洗产物（抽样入仓）
│   ├── integrated/                    # B/C/D 融合表（integrated_C_Q2_sample.csv 等）
│   └── metadata/                      # checksums、数据量报告、文件清单
├── crawler/                           # 采集代码/说明
├── processing/                        # E 清洗 + B/C/D 融合
├── analysis/                          # B/C/D 分析与 output/
├── visualization/                     # 可视化脚本
│   └── figures/                       # fig1_*.png 等全部图件
├── docs/                              # 数据源、描述性分析、报告
├── data_sources.md                    # 汇总数据源清单
├── AI_USAGE.md                        # 汇总 AI 使用记录
└── README.md
```

## 复现说明

各模块的脚本接口与产物说明见对应目录下的 `README_*.md`（`README_E_cleaning.md`、`README_B_*.md`、`README_C_*.md`、`README_D_*.md`）。

### 环境与数据

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt                      # Python 3.11+（推荐 3.13）
```

原始数据按下列结构放入 `raw_data/`（目录名需一致，脚本按名读取）：

```
raw_data/
├── 上海地铁客流量2017/
│   ├── metroData_InOutFlow.csv          # 进出站流水主表（207.4 MB）
│   ├── stationInfo.csv                  # 站点表
│   ├── B_数据清洗要求/站点_区映射.csv    # 302 站 → 区
│   ├── 2017年各区降尘量与PM2.5月均浓度.xlsx
│   └── 天气&工作日/
│       ├── shanghai_weatherHourly.csv
│       └── workday_calendar.csv
├── 空气/                        # 区级空气质量 xlsx（3 个 sheet，含 2024-01—2025-12 月度）
├── POI/上海市.csv               # 高德 POI 全量（1,422,977 条）
├── 绿地占比、植被韧性/data/      # 4 幅 GeoTIFF（UTM 49N）
├── 上海市行政区划-乡镇级shp文件/  # 区界 SHP（WGS-84）
└── 上海统计年鉴/                # 4 个 xls（双行表头）
```

### 一键复现

```bash
python reproduce.py --team-data "$PWD/raw_data" --sh-base "$PWD"
```

按 **E 清洗 → B/C/D 融合 → 分析 → 可视化** 顺序执行 16 个步骤，逐步校验产物行数，失败即停；每步日志写入 `logs/<步骤>.log`。

> 首次运行前先执行 `python reproduce.py --check`：缺脚本报 `MISSING_SCRIPT`，缺产物报 `MISSING_OUTPUT`，全部通过再正式运行。

| 选项 | 作用 |
|---|---|
| `--check` | 只检查脚本与产物，不执行 |
| `--skip-cleaning` | 跳过 E 清洗（`data/cleaned/` 已就绪时） |
| `--only B` / `--only C,D` | 只跑指定成员 |
| `--keep-going` | 单步失败后继续 |
| `--isolate` | 用 `python -I` 运行 |

> B 的脚本若仍在 `Q1_融合分析/可复现脚本/`、D 的在 `D/` 下，`reproduce.py` 会自动回退查找；C 的脚本读 `SH_BASE`，需包含 `cleaned_Data/` 与 `Data/`（`reproduce.py` 会自动建立兼容链接）。

### 分模块执行

```bash
# 1. E 清洗（7 个脚本，按序；E_common.py 为公共模块，不需单独运行）
python processing/E_cleaning_air.py
python processing/E_cleaning_green.py
python processing/E_cleaning_district.py
python processing/E_cleaning_metro.py
python processing/E_cleaning_weather.py
python processing/E_cleaning_poi.py
python processing/E_handoff_tables.py      # 最后运行，产出 B/C/D 主表

# 2. 融合
python processing/fuse_environment_metro.py    # B：52 × 12
python processing/C_Q2_integrate.py            # C：16 × 36
python processing/D_Q2_integrate.py            # D：16 × 17

# 3. 分析
python analysis/analyze_q1.py                  # B
python analysis/C_Q2_analysis.py               # C：8 阶段，output/01~06_*.csv
python analysis/D_Q2_analysis.py               # D

# 4. 可视化
python visualization/B_Q1_visualization.py     # 4 图
python visualization/C_Q2_visualization.py     # 9 图
python visualization/D_Q2_visualization.py     # 5 图
```

### 校验点

| 产物 | 期望规模 |
|---|---|
| `data/cleaned/cleaned_air_monthly.csv` | 384 行（16 区 × 24 月） |
| `data/cleaned/cleaned_metro_month_district.csv` | 52 行（13 区 × 4 月） |
| `data/cleaned/cleaned_poi_district_industry.csv` | 208 行（16 区 × 13 类） |
| B `fused_environment_metro_2017.csv` | 52 × 12 |
| C `integrated_C_Q2_sample.csv` | 16 × 36 |
| D `主表_区级宽表.csv` | 16 × 17 |

若 E 输出名与 B/C/D 输入名不一致，按 `data/cleaned/` 中的同名文件建立软链接/复制，不修改脚本。

关键结果（必须与实跑输出一致）：

| 模块 | 指标 | 期望值 |
|---|---|---|
| B | 客流强度 ~ PM2.5 | r=+0.047，p=0.739 |
| B | 总客流 ~ PM2.5 | r=−0.487，p=0.0003 |
| C | CLR-PC1 解释率 | 42.1% |
| C | 扬尘源 ~ 道路 PM10 | ρ=0.689，p=0.0031 |
| C | FDR / Bonferroni 显著数 | 0 / 80 |
| D | 绿地占比 ~ O₃（13 区） | ρ=0.678，p=0.011 |
| D | 绿地占比 ~ O₃（9 区稳健） | r=0.85 |

### 常见问题

| 现象 | 处理 |
|---|---|
| `ModuleNotFoundError` | `pip install -r requirements.txt`；去掉 `python -I` |
| `UnicodeDecodeError` | 读取用 `encoding="utf-8-sig"`，写出显式 `utf-8-sig` |
| C 找不到 `cleaned_Data/` | `ln -s data/cleaned cleaned_Data`（Windows：`mklink /D`） |
| 栅格读取报错 | 用 `tifffile + imagecodecs`（PIL 不支持 LZW float64） |
| POI 空间连接错区 | GCJ-02 先转 WGS-84 再 `sjoin` |
| 坐标越界 | GeoTIFF 为 UTM 49N，先用 `pyproj` 投影到 WGS-84 |
| 地铁每日进出站不配平 | 加回昆山 3 站（1114/1115/1116），残差应为 0 |

### 主要结论

- **Q1**：环境质量与地铁客流无稳健显著关联；M3 降尘量边际显著在 M4/M5 中消失。
- **Q2**：产业结构仅对道路 PM10 有可检出关联（3/4 预设假设通过 Bonferroni）；80 次全域扫描经 FDR 后 0 组显著。
- **Q3**：绿地占比与 O₃ 显著正相关（13 区 ρ=0.678；9 区 r=0.85），与 AQI/PM2.5 不显著。

> 约束：N=16 区，统计功效上限约 |ρ|>0.6；POI 为 2025 年单期截面，不能做面板或因果推断。AI 使用记录见 [`AI_USAGE.md`](AI_USAGE.md)；MetroFlow 为 MIT 许可。
