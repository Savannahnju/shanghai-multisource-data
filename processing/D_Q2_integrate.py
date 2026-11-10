# -*- coding: utf-8 -*-
"""
D · 研究问题 Q2 数据融合脚本

把三类清洗后数据按「区名」融合为一张区级截面宽表：
  1. 环境质量（空气_区×年月.csv）—— 区 × 月 → 区级（2024 年均 + 两年均值）
  2. 植被（栅格分区统计原始结果.csv）—— 绿地占比、植被韧性（区级）
  3. 年鉴（绿地与植被_区级明细.csv）—— 绿地面积、人口密度（区级）

输入（D/data/cleaned/）：
  空气_区×年月.csv
  栅格分区统计原始结果.csv
  绿地与植被_区级明细.csv
输出：
  D/data/cleaned/主表_区级宽表.csv（16 区 × 17 列，字段名与 E 版本一致）
"""
import pandas as pd
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / 'data' / 'cleaned'  # D/data/cleaned
INT = Path(__file__).resolve().parent.parent / 'data' / 'integrated'  # D/data/integrated

# 1. 环境质量：区×月 → 区级 -------------------------------------------------
air = pd.read_csv(DATA / '空气_区×年月.csv', encoding='utf-8-sig')
env_cols = ['AQI优良率(%)', 'PM2.5(μg/m³)', 'O3(μg/m³)', '道路PM10(μg/m³)']
env_names = ['AQI优良率', 'PM2.5', 'O3', '道路PM10']

# 2024 年区级均值
air2024 = (
    air[air['年份'] == 2024]
    .groupby('区名')[env_cols].mean().reset_index()
    .rename(columns=dict(zip(env_cols, env_names)))
)
air2024.insert(1, '年份', 2024)

# 两年（2024-2025）区级均值
air2y = (
    air.groupby('区名')[env_cols].mean().reset_index()
    .rename(columns=dict(zip(env_cols, [c + '_两年均值' for c in env_names])))
)

# 2. 植被：栅格分区统计（区级） --------------------------------------------
veg = pd.read_csv(DATA / '栅格分区统计原始结果.csv', encoding='utf-8-sig')
veg = veg[[
    '区名', '有效绿地像元数', '遥感绿地占比均值_%',
    'STL_AR1均值_剔除负值', 'V2_AR1均值', 'V2_VAR均值',
]].rename(columns={
    '遥感绿地占比均值_%': '绿地占比',
    'STL_AR1均值_剔除负值': '韧性_STL_AR1',
    'V2_AR1均值': '韧性_V2_AR1',
    'V2_VAR均值': '韧性_V2_VAR',
})

# 3. 年鉴：绿地面积、人口密度（区级） --------------------------------------
yb = pd.read_csv(DATA / '绿地与植被_区级明细.csv', encoding='utf-8-sig')
yb = yb[['区名', '绿地面积(公顷)', '人口密度(人/平方公里)']].rename(columns={
    '绿地面积(公顷)': '绿地面积',
    '人口密度(人/平方公里)': '人口密度',
})

# 4. 按区名融合，并整理列顺序与 E 版本一致 ----------------------------------
wide = (
    air2024
    .merge(air2y, on='区名', how='left')
    .merge(veg, on='区名', how='left')
    .merge(yb, on='区名', how='left')
)
col_order = ['区名', '年份', 'AQI优良率', 'PM2.5', 'O3', '道路PM10',
             '绿地占比', '韧性_STL_AR1', '韧性_V2_AR1', '韧性_V2_VAR',
             '绿地面积', '人口密度', '有效绿地像元数',
             'AQI优良率_两年均值', 'PM2.5_两年均值', 'O3_两年均值', '道路PM10_两年均值']
wide = wide[col_order]

# 5. 输出 -------------------------------------------------------------------
wide.to_csv(INT / '主表_区级宽表.csv', index=False, encoding='utf-8-sig')
print(f'融合完成：{wide.shape[0]} 区 × {wide.shape[1]} 列')
print('列：', list(wide.columns))
print('植被为空的区：', sorted(wide[wide['绿地占比'].isna()]['区名'].tolist()))
