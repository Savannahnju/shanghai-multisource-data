# -*- coding: utf-8 -*-
"""
Q1 分析脚本：环境质量 × 地铁客流量（2017 年 5–8 月）统计分析与可视化

输入：
  output/fused_environment_metro_2017.csv   （由 fuse_environment_metro.py 生成）

输出：
  figures/fig1_corr_heatmap.png   相关矩阵热图
  figures/fig2_scatter.png        客流强度 vs PM2.5 / 降尘量 散点 + 拟合线
  figures/fig3_district_bar.png   区级客流强度（5–8 月均值）横向条形图
  figures/fig4_time_series.png    月际趋势（全市总客流 / 月均 PM2.5 / 降尘量）
  output/analysis_summary.txt     全部统计量与回归结果（供撰写报告引用）

运行命令：python -I analyze_q1.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats
import statsmodels.api as sm

BASE = Path(__file__).resolve().parent
OUT = BASE / "output"
FIG = BASE / "figures"
FIG.mkdir(exist_ok=True)

plt.rcParams["font.family"] = ["SimSun", "SimHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

# 色板（Okabe-Ito，色盲友好；月份 5/6/7/8 固定顺序）
C5, C6, C7, C8 = "#0072B2", "#E69F00", "#009E73", "#D55E00"
MONTH_COLOR = {5: C5, 6: C6, 7: C7, 8: C8}
MONTH_LABEL = {5: "5 月", 6: "6 月", 7: "7 月", 8: "8 月"}
INK = "#1a1a1a"
GRAY = "#8a8a8a"

df = pd.read_csv(OUT / "fused_environment_metro_2017.csv", encoding="utf-8-sig")

S = []  # 汇总文本


def w(*a):
    S.append(" ".join(str(x) for x in a))


# ---------- 1. 描述统计 ----------
w("=" * 60)
w("一、融合样本描述统计（13 区 × 4 月 = 52 观测）")
w("=" * 60)
num_cols = ["降尘量", "PM2.5", "地铁总客流", "地铁日均客流", "客流强度", "站点数", "月均温", "月总降雨"]
desc = df[num_cols].describe().T[["mean", "std", "min", "50%", "max"]].round(2)
desc.columns = ["均值", "标准差", "最小", "中位", "最大"]
w(desc.to_string())

# ---------- 2. 相关矩阵 ----------
w("\n" + "=" * 60)
w("二、Pearson 相关矩阵（面板 52 观测）")
w("=" * 60)
corr_cols = ["降尘量", "PM2.5", "客流强度", "地铁日均客流", "地铁总客流", "站点数", "月均温", "月总降雨"]
corr = df[corr_cols].corr().round(3)
w(corr.to_string())

def pearson(x, y):
    r, p = stats.pearsonr(df[x], df[y])
    return r, p

pairs = [
    ("客流强度", "PM2.5"),
    ("客流强度", "降尘量"),
    ("地铁日均客流", "PM2.5"),
    ("地铁日均客流", "降尘量"),
    ("地铁总客流", "PM2.5"),
    ("地铁总客流", "降尘量"),
]
w("\n关键变量两两相关（r, p 值）：")
for a, b in pairs:
    r, p = pearson(a, b)
    w(f"  {a} ~ {b}: r={r:+.3f}, p={p:.4f}")

# 截面相关（区级 5–8 月均值，13 观测）
w("\n截面相关（区级 5–8 月均值，n=13）：")
dmean = df.groupby("区名")[["降尘量", "PM2.5", "客流强度", "地铁日均客流", "地铁总客流", "站点数"]].mean()
for a, b in [("客流强度", "PM2.5"), ("客流强度", "降尘量"),
             ("地铁日均客流", "PM2.5"), ("地铁日均客流", "降尘量")]:
    r, p = stats.pearsonr(dmean[a], dmean[b])
    w(f"  {a} ~ {b}: r={r:+.3f}, p={p:.4f}")

# ---------- 3. 回归 ----------
w("\n" + "=" * 60)
w("三、OLS 回归（稳健标准误 HC1）")
w("=" * 60)

r = df.rename(columns={
    "客流强度": "y", "PM2.5": "pm", "降尘量": "dust",
    "月均温": "temp", "月总降雨": "rain", "工作日数": "wd", "区名": "dist",
})

def ols(formula, data, name):
    m = sm.formula.ols(formula, data=data).fit(cov_type="HC1")
    w(f"\n[{name}] {formula}")
    w(f"  R2={m.rsquared:.3f}, adjR2={m.rsquared_adj:.3f}, n={int(m.nobs)}")
    for var in m.params.index:
        ci = m.conf_int().loc[var]
        w(f"  {var:>14s}: coef={m.params[var]:+.4f}, se={m.bse[var]:.4f}, "
          f"t={m.tvalues[var]:+.3f}, p={m.pvalues[var]:.4f}, 95%CI=[{ci[0]:+.3f},{ci[1]:+.3f}]")
    return m

m1 = ols("y ~ pm + dust", r, "M1 双变量")
m2 = ols("y ~ pm + dust + temp + rain + wd", r, "M2 加控制变量")
m3 = ols("y ~ pm + dust + temp + rain + wd + C(dist)", r, "M3 区固定效应")
# 稳健性：剔除单站区（青浦区）后
r2 = r[r["dist"] != "青浦区"]
m4 = ols("y ~ pm + dust + temp + rain + wd", r2, "M4 剔除青浦区(1站)")
# 稳健性：对数因变量
r3 = r.copy()
r3["logy"] = np.log(r3["y"])
m5 = ols("logy ~ pm + dust + temp + rain + wd", r3, "M5 对数客流强度")

# ---------- 4. 图表 ----------
# Fig 1 相关矩阵热图（diverging，0 为中心）
fig, ax = plt.subplots(figsize=(7.4, 6.2))
c = corr.values
im = ax.imshow(c, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
ax.set_xticks(range(len(corr_cols))); ax.set_xticklabels(corr_cols, rotation=45, ha="right", fontsize=9)
ax.set_yticks(range(len(corr_cols))); ax.set_yticklabels(corr_cols, fontsize=9)
for i in range(len(corr_cols)):
    for j in range(len(corr_cols)):
        ax.text(j, i, f"{c[i,j]:.2f}", ha="center", va="center",
                fontsize=8, color="white" if abs(c[i, j]) > 0.6 else INK)
ax.set_title("融合变量 Pearson 相关矩阵（13 区 × 4 月，n=52）", fontsize=11, pad=12)
cb = fig.colorbar(im, ax=ax, shrink=0.85)
cb.set_label("相关系数 r", fontsize=9)
fig.tight_layout()
fig.savefig(FIG / "fig1_corr_heatmap.png", dpi=160, bbox_inches="tight")
plt.close(fig)

# Fig 2 散点 + 拟合线（客流强度 vs PM2.5 / 降尘量）
fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8))
for ax, xvar, tag in [(axes[0], "PM2.5", "a"), (axes[1], "降尘量", "b")]:
    for mo, col in MONTH_COLOR.items():
        sub = df[df["月份"] == mo]
        ax.scatter(sub[xvar], sub["客流强度"], s=34, color=col,
                   edgecolor="white", linewidth=0.5, label=MONTH_LABEL[mo], zorder=3)
    r, p = stats.pearsonr(df[xvar], df["客流强度"])
    # OLS 拟合线
    b, a = np.polyfit(df[xvar], df["客流强度"], 1)
    xs = np.linspace(df[xvar].min(), df[xvar].max(), 50)
    ax.plot(xs, a + b * xs, color=INK, lw=1.6, ls="--", zorder=4)
    # 标注青浦区（单站区离群点）
    qp = df[df["区名"] == "青浦区"]
    for _, row in qp.iterrows():
        ax.annotate("青浦区", (row[xvar], row["客流强度"]),
                    xytext=(6, 6), textcoords="offset points", fontsize=8, color=INK)
    ax.text(0.03, 0.96, f"r={r:+.3f}  p={p:.3f}", transform=ax.transAxes,
            va="top", fontsize=10)
    ax.text(-0.06, 1.04, f"({tag})", transform=ax.transAxes, fontsize=11, va="bottom")
    ax.set_xlabel(xvar + ("（μg/m³）" if xvar == "PM2.5" else "（t/km²·月）"), fontsize=10)
    ax.set_ylabel("客流强度（人次/站·月）", fontsize=10)
    ax.grid(axis="both", color=GRAY, lw=0.4, alpha=0.35)
    ax.spines[["top", "right"]].set_visible(False)
axes[1].legend(fontsize=8, frameon=False, loc="lower left")
fig.suptitle("区月客流强度 与 环境质量的散点关系（n=52，按月份着色）", fontsize=11)
fig.tight_layout(rect=[0, 0, 1, 0.96])
fig.savefig(FIG / "fig2_scatter.png", dpi=160, bbox_inches="tight")
plt.close(fig)

# Fig 3 区级客流强度（5–8 月均值）横向条形图
dintensity = dmean.sort_values("客流强度")
fig, ax = plt.subplots(figsize=(7.6, 5.4))
norm = plt.Normalize(dintensity["客流强度"].min(), dintensity["客流强度"].max())
colors = plt.cm.Blues(norm(dintensity["客流强度"].values))
ax.barh(dintensity.index, dintensity["客流强度"] / 1e4, color=colors, edgecolor="white", lw=0.5)
for i, (name, v, st) in enumerate(zip(dintensity.index, dintensity["客流强度"], dintensity["站点数"])):
    ax.text(v / 1e4 + 2, i, f"{v/1e4:,.0f} 万", va="center", fontsize=8, color=INK)
    ax.text(2, i, f"{int(st)}站", va="center", ha="right", fontsize=7, color="white", fontweight="bold")
ax.set_xlabel("区客流强度（万人次 / 站 · 月，5–8 月均值）", fontsize=10)
ax.set_title("各区地铁客流强度（5–8 月均值）", fontsize=11)
ax.grid(axis="x", color=GRAY, lw=0.4, alpha=0.35)
ax.spines[["top", "right"]].set_visible(False)
ax.tick_params(axis="y", labelsize=9)
fig.tight_layout()
fig.savefig(FIG / "fig3_district_bar.png", dpi=160, bbox_inches="tight")
plt.close(fig)

# Fig 4 月际趋势（全市总量 / 月均 PM2.5 / 降尘量，三个子图，无双轴）
fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.8))
months = [5, 6, 7, 8]
total = df.groupby("月份")["地铁总客流"].sum() / 1e7
avg_pm = df.groupby("月份")["PM2.5"].mean()
avg_dust = df.groupby("月份")["降尘量"].mean()
series = [
    (total, "全市月总客流（千万人次）", "#0072B2", "a"),
    (avg_pm, "全市月均 PM2.5（μg/m³）", "#D55E00", "b"),
    (avg_dust, "全市月均降尘量（t/km²·月）", "#009E73", "c"),
]
for ax, (s, ylab, col, tag) in zip(axes, series):
    ax.plot(months, s.values, color=col, lw=2, marker="o", ms=5)
    for x, y in zip(months, s.values):
        ax.annotate(f"{y:.1f}", (x, y), xytext=(0, 6), textcoords="offset points",
                    ha="center", fontsize=8, color=INK)
    ax.set_xticks(months); ax.set_xticklabels([f"{m}月" for m in months], fontsize=9)
    ax.set_ylabel(ylab, fontsize=9)
    ax.text(-0.06, 1.05, f"({tag})", transform=ax.transAxes, fontsize=11, va="bottom")
    ax.grid(axis="y", color=GRAY, lw=0.4, alpha=0.35)
    ax.spines[["top", "right"]].set_visible(False)
fig.suptitle("2017 年 5–8 月 全市客流与环境质量月际趋势", fontsize=11)
fig.tight_layout(rect=[0, 0, 1, 0.94])
fig.savefig(FIG / "fig4_time_series.png", dpi=160, bbox_inches="tight")
plt.close(fig)

# ---------- 写出汇总 ----------
(OUT / "analysis_summary.txt").write_text("\n".join(S), encoding="utf-8")
print("done. wrote", len(S), "summary lines and 4 figures")
