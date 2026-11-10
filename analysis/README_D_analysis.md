# README — D Q2 分析脚本

## 脚本

- `D_Q2_analysis.py`：相关分析（Pearson + Spearman）+ KMeans 聚类。

## 输入

- `D/data/cleaned/主表_区级宽表.csv`（E 清洗后交付，16 区 × 17 列）

## 输出

- `D/analysis/D_Q2_analysis_results.txt`：相关分析结果与聚类结果（UTF-8）
- `D/data/cleaned/主表_区级宽表_聚类标签.csv`：各区聚类标签

## 运行命令（在项目根目录执行）

```bash
python D/analysis/D_Q2_analysis.py
```

脚本基于自身位置自动定位数据，从任意目录运行均可。

## 依赖

pandas、numpy、scipy、scikit-learn

## 字段变化说明

- 读取 16 区宽表 → 剔除植被为空（徐汇/静安/普陀）得 13 区主样本、筛选有效绿地像元 ≥ 100 得 9 区稳健样本。
- 新增字段：`聚类`（K=3 的簇标签）。
