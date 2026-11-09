# B · Q1 可视化脚本 README

> 研究问题：**城市环境质量是否与地铁客流量（2017 年）有关？**
> 负责人：B。本脚本为**可视化专用**，从融合宽表产出 4 张报告插图；描述统计、相关与回归见 `analyze_q1.py`。

---

## 1. 脚本清单

| 脚本 | 作用 | 输入 | 输出 |
|---|---|---|---|
| `B_Q1_visualization.py` | 可视化（4 张插图） | `output/fused_environment_metro_2017.csv` | `figures/fig1~4.png` + `output/figure_captions.txt` |

## 2. 运行环境与命令

- Python 3.10+，依赖：`pandas`、`numpy`、`matplotlib`、`scipy`。
- 前置：先运行 `fuse_environment_metro.py` 生成融合宽表。

```bash
cd Q1_融合分析/可复现脚本
python -I B_Q1_visualization.py
```

> 输入/输出路径在脚本顶部参数化（`BASE = 脚本上一级目录`，即 `Q1_融合分析/`），迁移目录只需保持该相对层级不变。

## 3. 输入与输出

| 类型 | 路径（相对 `Q1_融合分析/`） | 说明 |
|---|---|---|
| 输入 | `output/fused_environment_metro_2017.csv` | 融合宽表，52 行 × 12 列（13 区 × 4 月） |
| 输出 | `figures/fig1_corr_heatmap.png` | 相关矩阵热图 |
| 输出 | `figures/fig2_scatter.png` | 散点 + 拟合线 |
| 输出 | `figures/fig3_district_bar.png` | 区级客流强度条形图 |
| 输出 | `figures/fig4_time_series.png` | 月际趋势图 |
| 输出 | `output/figure_captions.txt` | 4 张图的图注文本 |

## 4. 图注（可写入报告）

1. **fig1_corr_heatmap.png** — 8 个融合变量的 Pearson 相关矩阵热图，发散色板（RdBu_r）以 0 为中心，色块内标注相关系数 r。
2. **fig2_scatter.png** — 客流强度对 PM2.5（a）与降尘量（b）的散点图，点按月份着色，虚线为 OLS 拟合线，标注 r/p 与青浦区（单站离群点）。
3. **fig3_district_bar.png** — 13 区地铁客流强度（5–8 月均值，万人次/站·月）横向条形图，按值升序排列，颜色深浅表示强度，条内标注站点数。
4. **fig4_time_series.png** — 2017 年 5–8 月全市月总客流、月均 PM2.5、月均降尘量的月际趋势（三个单轴子图，点旁标注数值）。

## 5. 可视化设计要点

| 项 | 选择 | 理由 |
|---|---|---|
| 色板 | Okabe-Ito（蓝/橙/绿/红） | 色盲友好，月份 5/6/7/8 固定映射 |
| 中文字体 | SimSun（宋体）/ SimHei（黑体） | Windows 中文环境原生可用，避免豆腐块 |
| 热图色板 | RdBu_r，`vmin=-1, vmax=1` | 相关系数以 0 为中心，红蓝表示正负 |
| 负号 | `axes.unicode_minus=False` | 坐标轴负号正常显示 |
| 清晰度 | `dpi=160`、`bbox_inches="tight"` | 报告插图清晰、无多余留白 |
| 无显示环境 | `matplotlib.use("Agg")` | 服务器 / 无 GUI 环境可出图 |

## 6. 复现说明

- 脚本只读融合宽表，不修改原始数据；输出为 4 张 PNG 与 1 份图注，可重复运行（幂等）。
- 图 2、图 3 涉及的散点/条形均基于融合宽表现有字段，无额外抽样，随机种子不涉及（流程中无随机操作）。
- 若重跑 `fuse_environment_metro.py` 后融合宽表内容一致，则本脚本产出的 4 张图逐字节一致。
