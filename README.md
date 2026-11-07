# shanghai-multisource-data

《大数据系统和原理》中期大作业 —— 上海多源城市数据分析

## 小组成员

| 成员 | 分工 |
|------|------|------|
| A | 统筹 / PPT / 写作 / 数据采集 |
| B | 研究问题 1 + 分析 |
| C | 研究问题 2 + 分析 |
| D | 研究问题 3 + 分析 |
| E | 数据清洗 |

## 数据源

- 地铁客流
- 行政区划
- 空气质量
- POI 兴趣点
- 绿地
- 气象 / 年鉴

## 目录结构

```
project/
├── data/                          # 数据（抽样/索引）
│   ├── raw/                       # 原始数据的抽样/索引（raw_C_*.geojson）
│   ├── cleaned/                   # 清洗后数据的抽样/索引
│   └── integrated/                # 区×结构×空气融合表（integrated_C_Q2_sample.csv）
├── crawler/                       # 数据采集代码
├── processing/                    # 清洗、规范化、实体/时间/空间对齐（C_sample_raw_data.py）
├── analysis/                      # 分析与数据挖掘
│   ├── README_C_analysis.md       # Q2 分析说明（8 个阶段、方法要点、已知约束）
│   ├── C_Q2_analysis.py           # Q2 流水线（单文件，按阶段执行）
│   └── output/                    # 阶段产物 CSV（20 张）
├── visualization/                 # 可视化代码与结果
│   ├── README_C_visualization.md  # 图题、数据范围、单位、来源对照表
│   ├── C_Q2_visualization.py      # 图1—图9 重绘入口
│   └── figures/                   # fig1_C_*.png … fig9_C_*.png
├── docs/                          # 数据源、方法、图表说明等
│   ├── C_data_sources.md          # 成员 C 的数据源清单
│   └── C_descriptive_analysis.md  # 描述性分析
├── data_sources.md                # 汇总数据源清单（由各组员分项合并）
├── AI_USAGE.md                    # 汇总 AI 使用记录
└── README.md
```

## 复现说明

各模块的脚本接口与产物说明见对应目录下的 `README_*.md`。

**成员 C / Q2（产业结构 × 环境质量）**：

```powershell
set SH_BASE=<数据根目录>              # 需含 cleaned_Data/ 与 Data/
python analysis\C_Q2_analysis.py      # 生成 analysis/output/ 的 20 张表
python visualization\C_Q2_visualization.py   # 重绘 visualization/figures/ 的 9 张图
```

数据依赖：`cleaned_Data/` 由 processing 阶段产出（POI 点级表、空气区×年月表、区界属性与 geojson）；
原始 253 MB 数据不入仓库，仅提交抽样与索引。
