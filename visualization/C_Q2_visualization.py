# -*- coding: utf-8 -*-
"""C_Q2_visualization.py —— Q2 的图 1—图 9 重绘入口

成员：C    问题：Q2

设计说明：
本问题的绘图与数据加工高度耦合（图1 要 PCA 得分、图5 要相关检验结果、图8 要读区界几何），
因此不复制一套绘图代码，而是复用 analysis/C_Q2_analysis.py 中负责出图的阶段：
    stage4_fdr_and_figures  →  fig1—fig6
    stage5_time_and_map     →  fig7—fig8
    stage6_kmeans           →  fig9

用法：
    python ../analysis/C_Q2_analysis.py     # 先生成表（一次性）
    python C_Q2_visualization.py            # 只重绘图（会同时刷新这三张相关表，结果一致）

图目录：visualization/figures/
    fig1_C_industry_axis_pc1.png        产业结构主轴（PC1）
    fig2_C_dustsource_vs_roadpm10.png   扬尘源规模 vs 道路 PM10
    fig3_C_industry_share_heatmap.png   16 区产业占比热力图
    fig4_C_airquality_by_district.png   空气质量区际分布
    fig5_C_structure_vs_pm25.png        结构指标 vs PM2.5
    fig6_C_ring_comparison.png          三圈层对比
    fig7_C_time_vs_spatial.png          24 个月时间波动 vs 区际差异
    fig8_C_roadpm10_choropleth.png      道路 PM10 区级 choropleth
    fig9_C_kmeans_types.png             K-means 产业类型
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS_DIR = os.path.join(os.path.dirname(HERE), "analysis")
MOD_PATH = os.path.join(ANALYSIS_DIR, "C_Q2_analysis.py")


def load_analysis():
    spec = importlib.util.spec_from_file_location("c_q2_analysis", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["c_q2_analysis"] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    if not os.path.exists(MOD_PATH):
        raise SystemExit("未找到 %s，请确认仓库结构完整" % MOD_PATH)
    m = load_analysis()
    print("图目录：", m.FIG_DIR)
    print("[1/3] 图1—图6 …")
    m.stage4_fdr_and_figures()
    print("[2/3] 图7—图8 …")
    m.stage5_time_and_map()
    print("[3/3] 图9 …")
    m.stage6_kmeans()
    print("完成：9 张图已写入", m.FIG_DIR)


if __name__ == "__main__":
    main()
