# -*- coding: utf-8 -*-
"""
B · Q1 可视化脚本：城市环境质量 × 地铁客流量（2017 年 5–8 月）

研究问题：城市环境质量（区月降尘量、区月 PM2.5 均值）是否与地铁客流量有关？
本脚本为**可视化专用**（描述统计 / 相关 / 回归见 analyze_q1.py），
从融合宽表一次性产出 4 张报告插图。

────────────────────────────────────────────────────────────────────
输入：
  output/fused_environment_metro_2017.csv   融合宽表（13 区 × 4 月 = 52 行，由 fuse_environment_metro.py 生成）

输出（写入 figures/）：
  fig1_corr_heatmap.png    相关矩阵热图（8 变量 Pearson 相关，发散色板、0 为中心）
  fig2_scatter.png         客流强度 vs PM2.5 / 降尘量 散点 + 拟合线（按月份着色）
  fig3_district_bar.png    区级客流强度（5–8 月均值）横向条形图
  fig4_time_series.png     月际趋势（全市总客流 / 月均 PM2.5 / 月均降尘量）

另写 output/figure_captions.txt：4 张图的图注（供报告直接引用）。

运行命令：
  cd Q1_融合分析/可复现脚本 && python -I B_Q1_visualization.py
────────────────────────────────────────────────────────────────────
"""
import matplotlib
matplotlib.use("Agg")          # 无显示环境下仍可出图
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats

BASE = Path(__file__).resolve().parents[1]   # Q1_融合分析/
OUT = BASE / "output"
FIG = BASE / "figures"
FIG.mkdir(exist_ok=True)

# 中文字体（SimSun/SimHei）+ 负号正常显示
plt.rcParams["font.family"] = ["SimSun", "SimHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

# 色板：Okabe-Ito（色盲友好），月份 5/6/7/8 固定顺序
C5, C6, C7, C8 = "#0072B2", "#E69F00", "#009E73", "#D55E00"
MONTH_COLOR = {5: C5, 6: C6, 7: C7, 8: C8}
MONTH_LABEL = {5: "5 月", 6: "6 月", 7: "7 月", 8: "8 月"}
INK = "#1a1a1a"
GRAY = "#8a8a8a"

df = pd.read_csv(OUT / "fused_environment_metro_2017.csv", encoding="utf-8-sig")

captions = []


def caption(name, text):
    captions.append(f"**{name}**　{text}")


# ---------- Fig 1 相关矩阵热图 ----------
corr_cols = ["降尘量", "PM2.5", "客流强度", "地铁日均客流", "地铁总客流", "站点数", "月均温", "月总降雨"]
corr = df[corr_cols].corr().round(3)

fig, ax = plt.subplots(figsize=(7.4, 6.2))
c = corr.values
im = ax.imshow(c, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
ax.set_xticks(range(len(corr_cols))); ax.set_xticklabels(corr_cols, rotation=45, ha="right", fontsize=9)
ax.set_yticks(range(len(corr_cols))); ax.set_yticklabels(corr_cols, fontsize=9)
for i in range(len(corr_cols)):
    for j in range(len(corr_cols)):
        ax.text(j, i, f"{c[i, j]:.2f}", ha="center", va="center",
                fontsize=8, color="white" if abs(c[i, j]) > 0.6 else INK)
ax.set_title("融合变量 Pearson 相关矩阵（13 区 × 4 月，n=52）", fontsize=11, pad=12)
cb = fig.colorbar(im, ax=ax, shrink=0.85)
cb.set_label("相关系数 r", fontsize=9)
fig.tight_layout()
fig.savefig(FIG / "fig1_corr_heatmap.png", dpi=160, bbox_inches="tight")
plt.close(fig)
caption("fig1_corr_heatmap.png", "8 个融合变量的 Pearson 相关矩阵热图，发散色板（RdBu_r）以 0 为中心，色块内标注相关系数 r。")

# ---------- Fig 2 散点 + 拟合线 ----------
fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8))
for ax, xvar, tag in [(axes[0], "PM2.5", "a"), (axes[1], "降尘量", "b")]:
    for mo, col in MONTH_COLOR.items():
        sub = df[df["月份"] == mo]
        ax.scatter(sub[xvar], sub["客流强度"], s=34, color=col,
                   edgecolor="white", linewidth=0.5, label=MONTH_LABEL[mo], zorder=3)
    r, p = stats.pearsonr(df[xvar], df["客流强度"])
    b, a = np.polyfit(df[xvar], df["客流强度"], 1)
    xs = np.linspace(df[xvar].min(), df[xvar].max(), 50)
    ax.plot(xs, a + b * xs, color=INK, lw=1.6, ls="--", zorder=4)
    qp = df[df["区名"] == "青浦区"]
    for _, row in qp.iterrows():
        ax.annotate("青浦区", (row[xvar], row["客流强度"]),
                    xytext=(6, 6), textcoords="offset points", fontsize=8, color=INK)
    ax.text(0.03, 0.96, f"r={r:+.3f}  p={p:.3f}", transform=ax.transAxes, va="top", fontsize=10)
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
caption("fig2_scatter.png", "客流强度对 PM2.5（a）与降尘量（b）的散点图，点按月份着色，虚线为 OLS 拟合线，标注 r/p 与青浦区（单站离群点）。")

# ---------- Fig 3 区级客流强度横向条形图 ----------
dmean = df.groupby("区名")[["客流强度", "站点数"]].mean()
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
caption("fig3_district_bar.png", "13 区地铁客流强度（5–8 月均值，万人次/站·月）横向条形图，按值升序排列，颜色深浅表示强度，条内标注站点数。")

# ---------- Fig 4 月际趋势 ----------
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
caption("fig4_time_series.png", "2017 年 5–8 月全市月总客流、月均 PM2.5、月均降尘量的月际趋势（三个单轴子图，点旁标注数值）。")

# ---------- 写出图注 ----------
(OUT / "figure_captions.txt").write_text("\n".join(captions), encoding="utf-8")
print(f"done. 生成 4 张图 -> {FIG}；图注 -> {OUT / 'figure_captions.txt'}")
