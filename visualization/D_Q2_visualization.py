# -*- coding: utf-8 -*-
"""
D · 研究问题 Q2 可视化脚本
生成 5 张核心可视化图（问题式标题），输出至 visualization/figures/

图1 绿地占比 vs AQI优良率（散点 + 拟合线）
图2 绿地占比 vs O₃（散点 + 标注区名，核心发现）
图3 环境质量 × 植被 相关矩阵热图
图4 KMeans 聚类散点图（绿地占比 × PM2.5，按簇着色）
图5 各区绿地占比空间分布图（choropleth）
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import geopandas as gpd
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent  # D/ 目录
DATA = BASE / 'data' / 'cleaned'                 # D/data/cleaned
INT = BASE / 'data' / 'integrated'               # D/data/integrated

# 中文字体
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'SimSun', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

FIGDIR = str(BASE / 'visualization' / 'figures') + '/'
SRC = '数据来源：E 清洗后数据（主表_区级宽表.csv，2024 年）'

# 读取数据 -----------------------------------------------------------------
df = pd.read_csv(INT / '主表_区级宽表.csv', encoding='utf-8-sig')
sub13 = df.dropna(subset=['绿地占比']).copy()          # 13 区（剔除植被为空）
cluster = pd.read_csv(INT / '主表_区级宽表_聚类标签.csv', encoding='utf-8-sig')
sub13 = sub13.merge(cluster, on='区名', how='left')

env_vars = ['AQI优良率', 'PM2.5', 'O3', '道路PM10']
veg_vars = ['绿地占比', '韧性_STL_AR1', '韧性_V2_AR1', '韧性_V2_VAR']
veg_labels = {'绿地占比': '绿地占比(%)', '韧性_STL_AR1': '韧性STL_AR1',
              '韧性_V2_AR1': '韧性V2_AR1(越负越强)', '韧性_V2_VAR': '韧性V2_VAR(越负越强)'}

# 统一配色
C_MAIN = '#3b7a9e'   # 主色（蓝）
C_ACC  = '#c0392b'   # 强调（红）
cluster_colors = {0: '#3b7a9e', 1: '#c0392b', 2: '#7d8f69'}

def style(ax, xlabel, ylabel):
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.grid(True, linestyle='--', alpha=0.4)
    ax.spines[['top', 'right']].set_visible(False)

# 图1 绿地占比 vs AQI优良率 -------------------------------------------------
fig, ax = plt.subplots(figsize=(7, 5))
ax.scatter(sub13['绿地占比'], sub13['AQI优良率'], s=70, color=C_MAIN, alpha=0.85, edgecolor='white')
for _, r in sub13.iterrows():
    ax.annotate(r['区名'], (r['绿地占比'], r['AQI优良率']),
                textcoords='offset points', xytext=(6, 3), fontsize=8)
k, b = np.polyfit(sub13['绿地占比'], sub13['AQI优良率'], 1)
xs = np.linspace(sub13['绿地占比'].min(), sub13['绿地占比'].max(), 50)
ax.plot(xs, k * xs + b, color=C_ACC, linestyle='--', linewidth=1.2,
        label=f'线性拟合（r={np.corrcoef(sub13["绿地占比"], sub13["AQI优良率"])[0,1]:.2f}）')
ax.legend(fontsize=9)
style(ax, '绿地占比（%）', 'AQI优良率（%）')
ax.set_title('图1  绿地占比越高的区，AQI优良率是否越高？', fontsize=12, fontweight='bold')
fig.text(0.02, 0.02, SRC, fontsize=7, color='gray')
fig.tight_layout()
fig.savefig(FIGDIR + 'fig1_绿地占比与AQI优良率.png', dpi=150, bbox_inches='tight')
plt.close(fig)

# 图2 绿地占比 vs O3（核心发现） ---------------------------------------------
fig, ax = plt.subplots(figsize=(7, 5))
ax.scatter(sub13['绿地占比'], sub13['O3'], s=70, color=C_ACC, alpha=0.85, edgecolor='white')
for _, r in sub13.iterrows():
    ax.annotate(r['区名'], (r['绿地占比'], r['O3']),
                textcoords='offset points', xytext=(6, 3), fontsize=8)
k, b = np.polyfit(sub13['绿地占比'], sub13['O3'], 1)
xs = np.linspace(sub13['绿地占比'].min(), sub13['绿地占比'].max(), 50)
ax.plot(xs, k * xs + b, color=C_MAIN, linestyle='--', linewidth=1.2,
        label=f'线性拟合（Spearman ρ={sub13["绿地占比"].corr(sub13["O3"], method="spearman"):.2f}）')
ax.legend(fontsize=9)
style(ax, '绿地占比（%）', 'O3 月均浓度（μg/m³）')
ax.set_title('图2  绿地占比越高的区，O3浓度是否反而越高？', fontsize=12, fontweight='bold')
fig.text(0.02, 0.02, SRC, fontsize=7, color='gray')
fig.tight_layout()
fig.savefig(FIGDIR + 'fig2_绿地占比与O3.png', dpi=150, bbox_inches='tight')
plt.close(fig)

# 图3 相关矩阵热图 ---------------------------------------------------------
corr = sub13[env_vars + veg_vars].corr().round(2)
fig, ax = plt.subplots(figsize=(7, 6))
cmap = LinearSegmentedColormap.from_list('rdbu', ['#d73027', '#f7f7f7', '#4575b4'])
im = ax.imshow(corr.values, cmap=cmap, vmin=-1, vmax=1)
labels = [f'{v}\n(相关系数)' if i == 0 else v for i, v in enumerate(env_vars + veg_vars)]
ax.set_xticks(range(len(labels))); ax.set_xticklabels(env_vars + veg_vars, rotation=45, ha='right', fontsize=8)
ax.set_yticks(range(len(labels))); ax.set_yticklabels(env_vars + veg_vars, fontsize=8)
for i in range(len(labels)):
    for j in range(len(labels)):
        ax.text(j, i, f'{corr.values[i, j]:.2f}', ha='center', va='center',
                fontsize=8, color='black' if abs(corr.values[i, j]) < 0.6 else 'white')
fig.colorbar(im, ax=ax, shrink=0.8, label='Pearson 相关系数')
ax.set_title('图3  环境质量与植被指标之间存在怎样的相关关系？', fontsize=11, fontweight='bold')
fig.text(0.02, 0.02, SRC + '（13 区）', fontsize=7, color='gray')
fig.tight_layout()
fig.savefig(FIGDIR + 'fig3_相关矩阵热图.png', dpi=150, bbox_inches='tight')
plt.close(fig)

# 图4 聚类散点图 -----------------------------------------------------------
fig, ax = plt.subplots(figsize=(7, 5))
for c in sorted(sub13['聚类'].unique()):
    d = sub13[sub13['聚类'] == c]
    ax.scatter(d['绿地占比'], d['PM2.5'], s=90, color=cluster_colors[c],
               edgecolor='white', label=f'簇{c}（{len(d)}区）')
for _, r in sub13.iterrows():
    ax.annotate(r['区名'], (r['绿地占比'], r['PM2.5']),
                textcoords='offset points', xytext=(6, 3), fontsize=8)
ax.legend(fontsize=9)
style(ax, '绿地占比（%）', 'PM2.5 月均浓度（μg/m³）')
ax.set_title('图4  上海各区可分成哪几类「环境—植被」类型？', fontsize=12, fontweight='bold')
fig.text(0.02, 0.02, SRC + '（KMeans，K=3，标准化特征）', fontsize=7, color='gray')
fig.tight_layout()
fig.savefig(FIGDIR + 'fig4_聚类散点图.png', dpi=150, bbox_inches='tight')
plt.close(fig)

# 图5 choropleth 绿地占比空间分布 ------------------------------------------
gdf = gpd.read_file(DATA / '区界.gpkg')
gdf = gdf.merge(df[['区名', '绿地占比', 'AQI优良率']], on='区名', how='left')

fig, axes = plt.subplots(1, 2, figsize=(14, 6))
for ax, col, title, cmap in [
    (axes[0], '绿地占比', '图5a  各区绿地占比的空间分布如何？', 'YlGn'),
    (axes[1], 'AQI优良率', '图5b  各区AQI优良率的空间分布如何？', 'RdYlGn')]:
    gdf.plot(column=col, ax=ax, cmap=cmap, edgecolor='white', linewidth=0.5,
             legend=True, legend_kwds={'shrink': 0.6}, missing_kwds={'color': '#cccccc'})
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_axis_off()
fig.text(0.02, 0.02, SRC + '（灰=植被为空的三区：徐汇/静安/普陀）', fontsize=7, color='gray')
fig.tight_layout()
fig.savefig(FIGDIR + 'fig5_空间分布.png', dpi=150, bbox_inches='tight')
plt.close(fig)

print('5 张图已生成至 visualization/figures/')
