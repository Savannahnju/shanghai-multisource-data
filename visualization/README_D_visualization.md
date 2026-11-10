# README — D Q2 可视化脚本

## 脚本

- `D_Q2_visualization.py`：生成 5 张问题式标题图表。

## 输入

- `D/data/cleaned/主表_区级宽表.csv`
- `D/data/cleaned/主表_区级宽表_聚类标签.csv`（由分析脚本生成）
- `D/data/cleaned/区界.gpkg`（区级边界，choropleth 用）

## 输出（D/visualization/figures/）

- `fig1_绿地占比与AQI优良率.png`
- `fig2_绿地占比与O3.png`
- `fig3_相关矩阵热图.png`
- `fig4_聚类散点图.png`
- `fig5_空间分布.png`

## 运行命令（在项目根目录执行）

```bash
python D/visualization/D_Q2_visualization.py
```

脚本基于自身位置自动定位数据，从任意目录运行均可。

## 依赖

pandas、numpy、matplotlib、geopandas

## 字段变化说明

- 读取宽表并剔除植被为空三区得 13 区样本；图 5 用全部 16 区（植被为空区显示为灰）。
- 图表标题为问题式标题，图内注明数据来源、单位、样本范围。
