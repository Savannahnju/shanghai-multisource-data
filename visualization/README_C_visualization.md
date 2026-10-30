# README_C_visualization —— Q2 可视化说明

> 成员：C    问题：Q2（产业结构 × 环境质量）
> 入口脚本：`C_Q2_visualization.py`　图目录：`figures/`

## 1. 怎么跑

```powershell
set SH_BASE=E:\大数据大作业_上海城市
python ..\analysis\C_Q2_analysis.py     # 先生成表（一次即可）
python C_Q2_visualization.py            # 重绘 9 张图
```

绘图与数据加工耦合较紧（图1 用 PCA 得分、图5 用相关检验结果、图8 读区界几何），因此 `C_Q2_visualization.py` 复用
`analysis/C_Q2_analysis.py` 中的出图阶段（stage4 / stage5 / stage6），不另写一套绘图代码，避免两套实现漂移。

## 2. 九张图（均为问题式标题）

| 文件 | 图题（回答什么问题） | 数据范围 | 单位 | 来源 |
|---|---|---|---|---|
| `fig1_C_industry_axis_pc1.png` | 产业结构能否压缩为一条城市梯度轴？ | 2025 年 POI，16 区 × 12 类 | CLR-PCA 得分，无量纲 | `cleaned_Data/POI_清洗后全量_134万行.csv` |
| `fig2_C_dustsource_vs_roadpm10.png` | 扬尘源越多的区，道路 PM10 是否越高？ | n=16 区 | 条；μg/m³ | POI + xlsx Sheet3 |
| `fig3_C_industry_share_heatmap.png` | 各区产业构成差异是否呈连续梯度？ | 16 区 × 12 类，按 PC1 排序 | %（行和 100） | 同上 |
| `fig4_C_airquality_by_district.png` | 16 区空气质量是否几乎不存在区际差异？ | 2024—2025 两年区均 | μg/m³；% | `2017年各区降尘量与PM2.5月均浓度.xlsx` Sheet3 |
| `fig5_C_structure_vs_pm25.png` | 产业结构与 PM2.5 的弱关联是否经得起校正？ | n=16 区 | %；μg/m³ | 同上 |
| `fig6_C_ring_comparison.png` | 空气质量是否随距市中心距离呈倒 U 型？ | 3 圈层（<10 / 10—30 / >30 km） | μg/m³；个/km² | 质心 + POI + Sheet3 |
| `fig7_C_time_vs_spatial.png` | 24 个月内时间波动是否远大于区际差异？ | 2024-01—2025-12，16×24=384 条 | μg/m³ | Sheet3 |
| `fig8_C_roadpm10_choropleth.png` | 道路 PM10 高值区是否集中在新城建设带？ | 两年区均，16 区 | μg/m³（82.2—90.1，未截断） | `区级数据.geojson` + Sheet3 |
| `fig9_C_kmeans_types.png` | 产业构成能否聚成离散类型，类型间空气质量是否有差异？ | 16 区 × 12 类，CLR/Aitchison，k=3 | 得分无量纲；μg/m³ | `output/01_修正占比_pct.csv` |

## 3. 制图规范（为满足课程要求）

- **问题式标题**：每张图标题是一个可回答的问题，不写"某某折线图"。
- **三要素标注**：每图正文下方脚注给出数据范围、单位、来源。
- **不误导**：所有色带按全区间等比着色，不截断坐标；图8 标注了实际最小/最大值（82.2—90.1）。
- **可复现**：图为脚本产物（`dpi=200`），不手工修改，图题与脚注写在代码里。

## 4. 视角覆盖

| 视角 | 图 |
|---|---|
| 总体特征 | 图1、图3、图4 |
| 跨源关系 | 图2、图5、图9 |
| 空间 | 图6、图8 |
| 时间 | 图7 |

满足"至少 5 张核心图、覆盖总体特征 / 跨源关系 / 时间或空间等 3 种视角"的要求。
