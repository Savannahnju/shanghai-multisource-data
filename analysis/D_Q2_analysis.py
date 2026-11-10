# -*- coding: utf-8 -*-
"""
D · 研究问题 Q2 分析脚本
城市环境质量是否与植被环境（植被结构、绿地占比）有关？

输入：data/cleaned/主表_区级宽表.csv（16 区 × 17 列，E 清洗后交付）
输出：analysis/D_Q2_analysis_results.txt（相关分析 + 聚类结果，UTF-8）

方法：
1. 核心相关分析（Pearson + Spearman），主样本 13 区（剔除植被为空的徐汇/静安/普陀），
   稳健性检验 9 区（有效绿地像元 >= 100）。
2. 数据挖掘：KMeans 聚类（对标准化后的环境-植被特征），识别"环境-植被"类型。
"""
import pandas as pd
import numpy as np
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent  # D/ 目录
DATA = BASE / 'data' / 'cleaned'                 # D/data/cleaned
INT = BASE / 'data' / 'integrated'               # D/data/integrated

OUT = []
def w(s=''):
    OUT.append(s)

# 1. 读取数据 ---------------------------------------------------------------
df = pd.read_csv(INT / '主表_区级宽表.csv', encoding='utf-8-sig')
env_vars = ['AQI优良率', 'PM2.5', 'O3', '道路PM10']          # 环境质量
veg_vars = ['绿地占比', '韧性_STL_AR1', '韧性_V2_AR1', '韧性_V2_VAR']  # 植被

w('=' * 90)
w('D Q2 分析结果：环境质量 × 植被环境')
w('=' * 90)
w(f'原始区数：{len(df)}；植被为空（有效绿地像元=0）的区：'
  f'{sorted(df[df["绿地占比"].isna()]["区名"].tolist())}')
w(f'有效绿地像元 >=100 的区（9 区稳健样本）：'
  f'{sorted(df[df["有效绿地像元数"]>=100]["区名"].tolist())}')
w()

# 2. 相关分析 ---------------------------------------------------------------
def corr_table(data, label):
    w('-' * 90)
    w(f'【{label}】 n = {len(data)}')
    w('-' * 90)
    w(f'{"指标":<16}{"方法":<12}' + ''.join(f'{v:>14}' for v in veg_vars))
    for env in env_vars:
        for method, func in [('Pearson', lambda a, b: stats.pearsonr(a, b)),
                             ('Spearman', lambda a, b: stats.spearmanr(a, b))]:
            row = f'{env:<16}{method:<12}'
            for veg in veg_vars:
                d = data[[env, veg]].dropna()
                if len(d) < 5:
                    row += f'{"—":>14}'
                else:
                    r, p = func(d[env], d[veg])
                    star = '*' if p < 0.05 else ('**' if p < 0.01 else '')
                    row += f'{r:>8.2f}{star:>6}'
            w(row)
    w()

# 主样本：13 区（剔除植被为空）
sub13 = df.dropna(subset=['绿地占比']).copy()
# 稳健样本：9 区（有效绿地像元 >=100）
sub9 = df[df['有效绿地像元数'] >= 100].copy()

corr_table(sub13, '主样本 13 区（剔除植被为空）')
corr_table(sub9, '稳健性检验 9 区（有效绿地像元 >=100）')

# 关键结果明细：绿地占比 vs 各环境指标（13 区）
w('-' * 90)
w('核心结果：绿地占比 与 各环境质量指标（13 区，Pearson + Spearman）')
w('-' * 90)
for env in env_vars:
    d = sub13[['绿地占比', env]].dropna()
    rp, pp = stats.pearsonr(d['绿地占比'], d[env])
    rs, ps = stats.spearmanr(d['绿地占比'], d[env])
    w(f'绿地占比 × {env}: Pearson r={rp:.3f} (p={pp:.3f})，Spearman ρ={rs:.3f} (p={ps:.3f})')
w()

# 3. 聚类分析 ---------------------------------------------------------------
w('=' * 90)
w('聚类分析（KMeans，标准化后的环境-植被特征）')
w('=' * 90)
# 用 13 区，特征取绿地占比 + 环境指标（PM2.5 与 AQI优良率高度冗余，选 PM2.5 + O3 + 绿地占比 + 道路PM10）
feat_cols = ['绿地占比', 'PM2.5', 'O3', '道路PM10']
cdata = sub13[feat_cols].copy()
X = StandardScaler().fit_transform(cdata)

# 确定 k（用惯性肘部法简单示意）
inertia = [KMeans(n_clusters=k, n_init=10, random_state=42).fit(X).inertia_
           for k in range(2, 7)]
w('K=2..6 的簇内平方和(inertia)：' + ', '.join(f'{v:.1f}' for v in inertia))

k = 3
km = KMeans(n_clusters=k, n_init=10, random_state=42)
sub13['聚类'] = km.fit_predict(X)
w(f'采用 K={k}，各簇成员：')
for c in sorted(sub13['聚类'].unique()):
    members = sorted(sub13[sub13['聚类'] == c]['区名'].tolist())
    w(f'  簇{c}：{members}')
    w(f'    中心特征：绿地占比均值 {sub13[sub13["聚类"]==c]["绿地占比"].mean():.1f}%，'
      f'PM2.5 均值 {sub13[sub13["聚类"]==c]["PM2.5"].mean():.1f}，'
      f'O3 均值 {sub13[sub13["聚类"]==c]["O3"].mean():.1f}，'
      f'道路PM10 均值 {sub13[sub13["聚类"]==c]["道路PM10"].mean():.1f}')
w()

# 保存带聚类的中间表
sub13[['区名', '聚类']].to_csv(INT / '主表_区级宽表_聚类标签.csv',
                              index=False, encoding='utf-8-sig')
w('聚类标签已保存至 D/data/cleaned/主表_区级宽表_聚类标签.csv')

with open(BASE / 'analysis' / 'D_Q2_analysis_results.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(OUT))
print('分析完成，结果已写入 D/analysis/D_Q2_analysis_results.txt')
