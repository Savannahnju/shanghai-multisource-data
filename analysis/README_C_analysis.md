# README_C_analysis —— Q2 产业结构 × 环境质量 分析说明

> 成员：C
> 核心问题（Q2）：利用多源异构数据，探究上海城市环境质量与产业结构（POI 各产业比例 / 聚集数量）有何相关性
> 数据源：① 百度地图 POI（2025，1,339,912 条）　② 区级空气质量月均（2024-01—2025-12，16 区 × 24 月 = 384 条）　③ 区界 geojson（16 区）

---

## 1. 文件

| 文件 | 说明 |
|---|---|
| `C_Q2_analysis.py` | 单文件流水线，8 个阶段顺序执行，产出全部表与图 |
| `output/*.csv` | 阶段产物（16 区 × 指标宽表、相关检验全表、聚类结果等） |
| `../visualization/C_Q2_visualization.py` | 只重绘图的入口（复用本文件 stage4—stage6） |
| `../visualization/figures/fig1_C_*.png … fig9_C_*.png` | 9 张核心可视化 |

## 2. 运行

```powershell
# 数据根目录（需含 cleaned_Data/ 与 Data/，由 processing 阶段产出）
set SH_BASE=E:\大数据大作业_上海城市
python C_Q2_analysis.py
```

依赖：`pandas`、`numpy`、`scipy`、`scikit-learn`、`matplotlib`。
`cleaned_Data/` 来自上游清洗（POI 点级表、空气区×年月表、区界属性表），原始 253 MB 数据不入仓库。

## 3. 八个阶段

| 阶段 | 函数 | 做什么 | 关键产物 |
|---|---|---|---|
| 1 | `stage1_industry_structure` | 剔除`居住地址标识`（占 9.7%–29%）后重算 12 类产业占比；CLR 变换 + PCA（PC1 符号用 POI 密度锚定）；区位熵 LQ、Shannon 多样性、HHI | `01_*.csv`（6 张） |
| 2 | `stage2_environment_and_correlation` | 环境刻画（时间振幅、区间排序一致性）；20 个结构指标 × 4 项污染物 = 80 次 Spearman 扫描；非中心 t 功效分析 | `02_*.csv`、`03_相关性检验全表.csv`、`03_功效分析.csv` |
| 3 | `stage3_mechanism` | 绝对数 / 每万 POI / 每 km² 三口径对比；rank 残差偏相关；距人民广场圈层倒 U | `04_*.csv`（3 张） |
| 4 | `stage4_fdr_and_figures` | BH-FDR 与 Bonferroni 校正；4 个机制预设假设（α=0.0125）；人工复算核对（ρ=0.689 断言）；图1—图6 | `03_相关性检验_FDR.csv`、`05_聚焦假设检验.csv`、fig1—fig6 |
| 5 | `stage5_time_and_map` | 24 个月时间序列与同月区际极差；读 geojson 手绘 choropleth（无 geopandas 依赖） | `02_时间序列与区际极差.csv`、fig7—fig8 |
| 6 | `stage6_kmeans` | **K-means 数据挖掘**：CLR/Aitchison 空间、轮廓系数选 k、20 种子 ARI 稳定性、KW + Mann-Whitney 簇间检验 | `06_Kmeans*.csv`（4 张）、fig9 |
| 7 | `stage7_secondary_check` | 单独核查 `公司企业/工厂`（3,633 条）与`农林牧渔基地`（2,370 条）的区际分布与相关性 | 控制台 |
| 8 | `stage8_join_check` | 空间连接正确性：每区 POI 均值坐标 vs 区质心（偏移 0.36—13.04 km） | 控制台 |

## 4. 方法要点（评审可能追问的点）

1. **成分数据**：12 类占比每行和为 100，直接做相关会产生约束导致的虚假负相关，故先 CLR 再 PCA。
2. **索引对齐**：`scipy.stats.spearmanr` 按位置配对、不认 pandas 索引；所有检验前强制 `reindex` 统一行序，并用扬尘源升序明细表人工复算核对。
3. **多重比较**：未校正 11/80 达 p<0.05，**FDR 与 Bonferroni 均为 0/80**；预设假设 3/4 通过 Bonferroni（α=0.0125），全部指向道路 PM10。
4. **阴性结果的性质**：N=16 时 \|ρ\|=0.5 的功效仅 52%，故"PM2.5 无关联"表述为**"不可检出"**而非"不存在"。
5. **聚类不替代相关**：K-means 与 PC1 主轴同构，簇间 PM2.5 差异 1.15 μg/m³，与未过校正的同一信号同源，不作为独立证据。

## 5. 已知约束

- 区级是最小可用空间单元（N=16），功效上限约 \|ρ\|>0.6；
- 空气质量区间方差仅占 1.3%（PM2.5）/ 0.7%（道路 PM10），因变量空间变异极低；
- POI 为 2025 年截面，无时间维度，不能做面板或因果推断；
- `cleaned_Data/区界.gpkg` 的几何与区名错配，制图统一改用 `区级数据.geojson`。
