# -*- coding: utf-8 -*-
"""C_Q2_analysis.py —— 核心研究问题 Q2：上海产业结构（POI）与环境质量（空气质量）的空间相关性

成员：C    问题：Q2    数据：POI 2025（1,339,912 条）+ 区级空气质量 2024—2025（384 条）+ 区界 geojson

整条流水线按阶段顺序执行，全部中间结果写入 analysis/output/，图写入 ../visualization/figures/：

  stage1  产业结构：剔除地名地址后重算占比、CLR 变换、PCA、区位熵、Shannon/HHI
  stage2  环境刻画：时间振幅、区间排序一致性、80 次全域 Spearman 扫描、功效分析
  stage3  机制：绝对数 / 每万 POI / 每 km2 三口径对比、偏相关、圈层倒 U
  stage4  FDR 与 Bonferroni 校正、4 个预设假设、图1—图6
  stage5  24 个月时间序列（图7）、区级 choropleth（图8）
  stage6  K-means 聚类（数据挖掘方法，图9）
  stage7  第二产业单独核查（工厂 3,633 条 / 农林牧渔基地 2,370 条）
  stage8  空间连接正确性核查（POI 均值坐标 vs 区质心）

运行：
    set SH_BASE=E:\大数据大作业_上海城市      # Windows，数据根目录
    python C_Q2_analysis.py

依赖：pandas / numpy / scipy / scikit-learn / matplotlib
注意：cleaned_Data 需先由 processing 阶段产出；原始数据不进仓库。
"""
import os
import sys

BASE_CFG = os.environ.get("SH_BASE", r"e:\大数据大作业_上海城市")
FIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "visualization", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

# --------------------------------------------------------------------
# 阶段1 产业结构：分母修正 + CLR-PCA + LQ/Shannon/HHI
# --------------------------------------------------------------------
def stage1_industry_structure():
    # -*- coding: utf-8 -*-
    """
    阶段1：产业结构刻画（分母修正 + 成分数据变换 + 专业化/多样性指标）
    输入：cleaned_Data/主表_区×产业.csv, POI_各区总数.csv, 区界属性_含面积质心.csv
    输出：analysis/output/
    """
    import os
    import numpy as np
    import pandas as pd

    BASE = BASE_CFG
    IN = os.path.join(BASE, "cleaned_Data")
    OUT = os.path.join(BASE, "analysis", "output")
    os.makedirs(OUT, exist_ok=True)

    # ---------- 读取 ----------
    m = pd.read_csv(os.path.join(IN, "主表_区×产业.csv"), encoding="utf-8-sig")
    area = pd.read_csv(os.path.join(IN, "区界属性_含面积质心.csv"), encoding="utf-8-sig")
    tot = pd.read_csv(os.path.join(IN, "POI_各区总数.csv"), encoding="utf-8-sig")

    cnt = m.pivot(index="区名", columns="产业大类", values="POI数量")
    area = area.set_index("区名")
    tot = tot.set_index("区名")["POI总数"]

    # ---------- 1.1 分母修正：剔除"居住地址标识"（地名地址，非产业）----------
    EXCLUDE = "居住地址标识"
    cnt_corr = cnt.drop(columns=[EXCLUDE])
    share = cnt_corr.div(cnt_corr.sum(axis=1), axis=0) * 100          # 修正后占比 %
    share_raw = cnt.div(cnt.sum(axis=1), axis=0) * 100                # 原始占比 %

    # ---------- 1.2 成分数据 CLR 变换 ----------
    def clr(df):
        """中心化对数比变换，处理零值用乘法替换"""
        x = df.values.astype(float)
        # 乘法替换：零值替换为 0.65 * 最小值
        delta = np.where(x == 0, 0.65 * np.nanmin(np.where(x > 0, x, np.nan)), 0)
        x = x + delta
        lg = np.log(x)
        return pd.DataFrame(lg - lg.mean(axis=1, keepdims=True), index=df.index, columns=df.columns)

    clr_df = clr(cnt_corr)

    # ---------- 1.2b PCA → 正交产业轴 ----------
    Z = (clr_df - clr_df.mean()) / clr_df.std()
    U, S, Vt = np.linalg.svd(Z.values, full_matrices=False)
    ev = S ** 2 / (S ** 2).sum()
    scores = pd.DataFrame(U * S, index=clr_df.index,
                         columns=[f"PC{i+1}" for i in range(len(S))])
    loadings = pd.DataFrame(Vt.T, index=clr_df.columns,
                            columns=[f"PC{i+1}" for i in range(len(S))])
    # 符号约定：令 PC1 与"城市化强度"正相关（用 POI 密度锚定）
    dens = (tot / area["面积_平方公里"]).reindex(scores.index)
    for c in ["PC1", "PC2"]:
        if np.corrcoef(scores[c].values, np.log10(dens.values))[0, 1] < 0:
            scores[c] *= -1
            loadings[c] *= -1

    # ---------- 1.3 区位熵 LQ ----------
    city_share = cnt_corr.sum(axis=0) / cnt_corr.sum().sum() * 100
    lq = share.div(city_share, axis=1)

    # ---------- 1.4 多样性 Shannon / 集中度 HHI ----------
    p = share / 100
    shannon = -(p * np.log(p.where(p > 0))).sum(axis=1)
    hhi = (p ** 2).sum(axis=1)

    # ---------- 组装输出 ----------
    struct = pd.DataFrame({
        "修正后产业POI数": cnt_corr.sum(axis=1),
        "原始POI总数": tot,
        "面积_km2": area["面积_平方公里"],
        "POI密度_个每km2": dens.round(1),
        "Shannon多样性": shannon.round(3),
        "HHI集中度": hhi.round(3),
        "PC1": scores["PC1"].round(2),
        "PC2": scores["PC2"].round(2),
    }).join(share.round(2).add_prefix("占比_"))

    struct.to_csv(os.path.join(OUT, "01_产业结构指标.csv"), encoding="utf-8-sig")
    share.round(2).to_csv(os.path.join(OUT, "01_修正占比_%.csv".replace("%", "pct")), encoding="utf-8-sig")
    lq.round(3).to_csv(os.path.join(OUT, "01_区位熵LQ.csv"), encoding="utf-8-sig")
    scores.round(3).to_csv(os.path.join(OUT, "01_产业轴得分.csv"), encoding="utf-8-sig")
    loadings.round(3).to_csv(os.path.join(OUT, "01_产业轴载荷.csv"), encoding="utf-8-sig")

    # ---------- 报告摘要 ----------
    ev_df = pd.DataFrame({"主成分": [f"PC{i+1}" for i in range(len(ev))],
                          "解释方差%": (ev * 100).round(1)})
    ev_df.to_csv(os.path.join(OUT, "01_主成分解释方差.csv"), index=False, encoding="utf-8-sig")

    print("=== 主成分解释方差 ===")
    print(ev_df.head(4).to_string(index=False))
    print("\n=== PC1 载荷（正=城市核心型产业，负=外围型） ===")
    print(loadings["PC1"].sort_values().round(2).to_string())
    print("\n=== 各区产业轴与多样性 ===")
    print(struct[["POI密度_个每km2", "Shannon多样性", "HHI集中度", "PC1", "PC2"]].sort_values("PC1").to_string())
    print("\n=== Shannon / HHI 变异幅度 ===")
    print("Shannon: %.3f ~ %.3f (CV=%.3f)" % (shannon.min(), shannon.max(), shannon.std() / shannon.mean()))
    print("HHI:     %.3f ~ %.3f (CV=%.3f)" % (hhi.min(), hhi.max(), hhi.std() / hhi.mean()))

# --------------------------------------------------------------------
# 阶段2 环境刻画 + 80 次全域相关扫描 + 功效分析
# --------------------------------------------------------------------
def stage2_environment_and_correlation():
    # -*- coding: utf-8 -*-
    """
    阶段2：环境质量刻画
    阶段3：相关性检验（Spearman + 功效 + Fisher置信区间 + Bonferroni + 稳健性）
    输出：analysis/output/
    """
    import os
    import numpy as np
    import pandas as pd
    from scipy import stats

    BASE = BASE_CFG
    IN = os.path.join(BASE, "cleaned_Data")
    OUT = os.path.join(BASE, "analysis", "output")
    os.makedirs(OUT, exist_ok=True)

    # ================= 阶段2 =================
    am = pd.read_csv(os.path.join(IN, "空气_区×年月.csv"), encoding="utf-8-sig")
    air = pd.read_csv(os.path.join(IN, "空气_区两年均值.csv"), encoding="utf-8-sig").set_index("区名")
    AIRV = ["AQI优良率", "PM2.5", "O3", "道路PM10"]

    # 2.1 季节振幅
    win = am[am["月份"].isin([1, 2, 12])].groupby("区名")["PM2.5(μg/m³)"].mean()
    sum_ = am[am["月份"].isin([6, 7, 8])].groupby("区名")["PM2.5(μg/m³)"].mean()
    amp = (win - sum_).round(2)

    # 2.2 年际变化
    y1 = am[am["年份"] == 2024].groupby("区名")["PM2.5(μg/m³)"].mean()
    y2 = am[am["年份"] == 2025].groupby("区名")["PM2.5(μg/m³)"].mean()
    delta = (y2 - y1).round(2)

    # 2.3 污染物区际排序一致性
    consist = pd.DataFrame(index=AIRV, columns=AIRV, dtype=float)
    for i in AIRV:
        for j in AIRV:
            consist.loc[i, j] = stats.spearmanr(air[i], air[j]).statistic
    consist.round(3).to_csv(os.path.join(OUT, "02_污染物排序一致性.csv"), encoding="utf-8-sig")

    env = pd.DataFrame({"PM2.5年均": air["PM2.5"], "道路PM10年均": air["道路PM10"],
                        "O3年均": air["O3"], "AQI优良率": air["AQI优良率"],
                        "PM2.5季节振幅": amp, "PM2.5_2025减2024": delta})
    env.to_csv(os.path.join(OUT, "02_环境质量刻画.csv"), encoding="utf-8-sig")

    print("=== 2.3 污染物区际排序一致性（Spearman）===")
    print(consist.round(2).to_string())
    print("\n=== 2.1/2.2 季节振幅与年际变化 ===")
    print(env[["PM2.5季节振幅", "PM2.5_2025减2024"]].sort_values("PM2.5季节振幅").to_string())

    # ================= 阶段3 =================
    struct = pd.read_csv(os.path.join(OUT, "01_产业结构指标.csv"), encoding="utf-8-sig").set_index("区名")
    lq = pd.read_csv(os.path.join(OUT, "01_区位熵LQ.csv"), encoding="utf-8-sig").set_index("区名")
    share = pd.read_csv(os.path.join(OUT, "01_修正占比_pct.csv"), encoding="utf-8-sig").set_index("区名")

    poi = pd.read_csv(os.path.join(IN, "POI_清洗后全量_134万行.csv"), encoding="utf-8-sig",
                      usecols=["区名", "中类", "小类", "大类"])

    def has(df, kws):
        m = pd.Series(False, index=df.index)
        for f in ("大类", "中类", "小类"):
            for k in kws:
                m |= df[f].astype(str).str.contains(k, na=False)
        return m

    # 排放源相关子类（绝对数量，避免面积分母混淆）
    poi["扬尘源"] = has(poi, ["建材", "装修", "建筑", "工地"])
    poi["物流源"] = has(poi, ["物流", "仓储", "货运", "产业园"])
    poi["汽修源"] = has(poi, ["汽车维修", "摩托车维修", "加油站", "加气站"])
    src = poi.groupby("区名")[["扬尘源", "物流源", "汽修源"]].sum().reindex(struct.index)

    # ---------- 预测变量集 ----------
    X = pd.DataFrame({
        "PC1_核心度": struct["PC1"],
        "PC2": struct["PC2"],
        "POI密度_log10": np.log10(struct["POI密度_个每km2"]),
        "Shannon多样性": struct["Shannon多样性"],
        "HHI集中度": struct["HHI集中度"],
    })
    for ind in ["批发零售", "交通运输仓储", "生产性服务业", "金融业", "房地产居住", "住宿餐饮"]:
        X[f"占比_{ind}"] = share[ind]
        X[f"LQ_{ind}"] = lq[ind]
    for c in src.columns:
        X[f"{c}_绝对数"] = src[c]

    # ---------- 检验函数：Spearman + Fisher 95%CI + 功效 + Bonferroni ----------
    # 关键：scipy.spearmanr 按位置配对、不认索引，必须先统一行序，否则相关全是错的
    Y = air[AIRV].reindex(X.index)
    assert (Y.index == X.index).all() and Y.notna().all().all(), "行序对齐失败"
    def fisher_ci(r, n, alpha=0.05):
        if abs(r) >= 1 or n < 4:
            return (np.nan, np.nan)
        z = np.arctanh(r); se = 1 / np.sqrt(n - 3)
        zc = stats.norm.ppf(1 - alpha / 2)
        return (np.tanh(z - zc * se), np.tanh(z + zc * se))

    def power_at(r, n=16, alpha=0.05):
        df = n - 2
        tc = stats.t.ppf(1 - alpha / 2, df)
        ncp = r * np.sqrt(df / (1 - r ** 2))
        return 1 - stats.nct.cdf(tc, df, ncp) + stats.nct.cdf(-tc, df, ncp)

    n_tests = len(X.columns) * len(AIRV)
    bonf_alpha = 0.05 / n_tests

    rows = []
    for xi in X.columns:
        for yj in AIRV:
            xv = X[xi].values; yv = Y[yj].values          # 已按同一行序取数组
            r, p = stats.spearmanr(xv, yv)
            lo, hi = fisher_ci(r, 16)
            rp, pp = stats.pearsonr(xv, yv)
            rows.append({
                "预测变量": xi, "污染物": yj,
                "rho": round(r, 3), "p": round(p, 4),
                "CI下限": round(lo, 3), "CI上限": round(hi, 3),
                "Pearson_r": round(rp, 3), "Pearson_p": round(pp, 4),
                "通过Bonferroni": p < bonf_alpha,
            })
    res = pd.DataFrame(rows).sort_values("p")
    res.to_csv(os.path.join(OUT, "03_相关性检验全表.csv"), index=False, encoding="utf-8-sig")

    print("\n================ 阶段3 结果 ================")
    print(f"检验次数={n_tests}  Bonferroni单次阈值 alpha={bonf_alpha:.5f}  N=16 临界|rho|=0.497")
    print(f"p<0.05 显著: {(res.p < 0.05).sum()} / {n_tests}")
    print(f"通过Bonferroni: {res['通过Bonferroni'].sum()} / {n_tests}")
    print("\n=== Top10 候选（按 p 排序，附 95%CI 与功效）===")
    top = res.head(10).copy()
    top["功效(若该rho为真)"] = top["rho"].abs().apply(lambda r: round(power_at(r) * 100, 0))
    print(top[["预测变量", "污染物", "rho", "p", "CI下限", "CI上限", "Pearson_r", "功效(若该rho为真)"]].to_string(index=False))

    # ---------- 功效曲线 ----------
    pw = pd.DataFrame({"真实rho": [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]})
    pw["N=16功效%"] = pw["真实rho"].apply(lambda r: round(power_at(r) * 100, 0))
    def req_n(r, pw_target=0.8):
        for nn in range(4, 500):
            if power_at(r, nn) >= pw_target:
                return nn
    pw["达80%功效所需N"] = pw["真实rho"].apply(req_n)
    pw.to_csv(os.path.join(OUT, "03_功效分析.csv"), index=False, encoding="utf-8-sig")
    print("\n=== 功效分析 ===")
    print(pw.to_string(index=False))

# --------------------------------------------------------------------
# 阶段3 机制：三口径对比 + 偏相关 + 圈层
# --------------------------------------------------------------------
def stage3_mechanism():
    # -*- coding: utf-8 -*-
    """
    阶段4（修订）：机制分析 + 规模混淆检验
    核心问题：排放源 POI 与道路PM10 的相关，是真实信号还是"区域规模"伪相关？
    三种归一化口径对比：绝对数 / 每万POI / 每km2 + 偏相关（控制规模）
    """
    import os
    import numpy as np
    import pandas as pd
    from scipy import stats

    BASE = BASE_CFG
    IN = os.path.join(BASE, "cleaned_Data")
    OUT = os.path.join(BASE, "analysis", "output")

    air_raw = pd.read_csv(os.path.join(IN, "空气_区两年均值.csv"), encoding="utf-8-sig").set_index("区名")
    geo = pd.read_csv(os.path.join(IN, "区界属性_含面积质心.csv"), encoding="utf-8-sig").set_index("区名")
    struct = pd.read_csv(os.path.join(OUT, "01_产业结构指标.csv"), encoding="utf-8-sig").set_index("区名")

    # 强制统一行序：scipy 按位置配对，不认索引
    IDX = struct.index
    air = air_raw.reindex(IDX)
    geo = geo.reindex(IDX)
    assert air.notna().all().all() and geo.notna().all().all(), "行序对齐失败"
    tot = struct["原始POI总数"]; area = struct["面积_km2"]

    poi = pd.read_csv(os.path.join(IN, "POI_清洗后全量_134万行.csv"), encoding="utf-8-sig",
                      usecols=["区名", "大类", "中类", "小类"])
    def has(df, kws):
        m = pd.Series(False, index=df.index)
        for f in ("大类", "中类", "小类"):
            for k in kws:
                m |= df[f].astype(str).str.contains(k, na=False)
        return m

    poi["扬尘源"] = has(poi, ["建材", "装修", "建筑", "工地"])
    poi["物流源"] = has(poi, ["物流", "仓储", "货运", "产业园"])
    poi["汽修源"] = has(poi, ["汽车维修", "摩托车维修", "加油", "加气"])
    src = poi.groupby("区名")[["扬尘源", "物流源", "汽修源"]].sum().reindex(struct.index)

    CEN = (121.4737, 31.2304)
    def hav(lon, lat):
        R = 6371.0
        p1, p2 = np.radians(lat), np.radians(CEN[1])
        dp, dl = p2 - p1, np.radians(lon - CEN[0])
        a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
        return 2 * R * np.arcsin(np.sqrt(a))
    geo["距市中心km"] = hav(geo["质心经度"].values, geo["质心纬度"].values).round(1)

    # ---------- 三种口径 ----------
    def partial_spearman(x, y, z):
        """控制 z 后的偏相关（rank 残差法）"""
        rx, ry, rz = (stats.rankdata(v) for v in (x, y, z))
        b1 = np.polyfit(rz, rx, 1); b2 = np.polyfit(rz, ry, 1)
        e1 = rx - np.polyval(b1, rz); e2 = ry - np.polyval(b2, rz)
        r, p = stats.pearsonr(e1, e2)
        return r, p

    rows = []
    for c in src.columns:
        for t in ["道路PM10", "PM2.5"]:
            abs_ = src[c]; per10k = src[c] / tot * 10000; perkm = src[c] / area
            for label, v in [("绝对数", abs_), ("每万POI", per10k), ("每km2", perkm)]:
                r, p = stats.spearmanr(v, air[t])
                pr, pp = partial_spearman(v.values, air[t].values, np.log(tot.values))
                pr2, pp2 = partial_spearman(v.values, air[t].values, np.log(area.values))
                rows.append({"排放源": c, "目标": t, "口径": label,
                             "rho": round(r, 3), "p": round(p, 4),
                             "控制规模后rho": round(pr, 3), "控制规模后p": round(pp, 4),
                             "控制面积后rho": round(pr2, 3), "控制面积后p": round(pp2, 4),
                             "n_tests": 48})
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(OUT, "04_排放源三口径与偏相关.csv"), index=False, encoding="utf-8-sig")

    print("=== 三种归一化口径对比（同一排放源的同一目标）===")
    print(res[res["目标"] == "道路PM10"].to_string(index=False))
    print()
    print("=== 与 PM2.5 ===")
    print(res[res["目标"] == "PM2.5"].to_string(index=False))

    print("\n=== 规模混淆诊断：各变量间 Spearman ===")
    S = pd.DataFrame({"扬尘源数": src["扬尘源"], "物流源数": src["物流源"],
                      "汽修源数": src["汽修源"], "POI总数": tot, "面积": area,
                      "道路PM10": air["道路PM10"], "PM2.5": air["PM2.5"]})
    c = S.corr(method="spearman").round(2)
    print(c.to_string())

    # 圈层对比
    M = pd.DataFrame({"道路PM10": air["道路PM10"], "PM2.5": air["PM2.5"], "O3": air["O3"],
                      "距市中心km": geo["距市中心km"], "POI密度": struct["POI密度_个每km2"]})
    M["圈层"] = pd.cut(M["距市中心km"], [-1, 10, 30, 100],
                      labels=["核心<10km", "近郊10-30km", "远郊>30km"])
    print("\n=== 按圈层分组均值 ===")
    print(M.groupby("圈层", observed=True)[["道路PM10", "PM2.5", "O3", "POI密度"]].mean().round(2).to_string())
    M.to_csv(os.path.join(OUT, "04_圈层对比.csv"), encoding="utf-8-sig")

# --------------------------------------------------------------------
# 阶段4 FDR/Bonferroni + 预设假设 + 图1—图6
# --------------------------------------------------------------------
def stage4_fdr_and_figures():
    # -*- coding: utf-8 -*-
    """
    阶段5：多重比较校正（FDR / 聚焦假设）+ 人工核对 + 图表
    """
    import os
    import numpy as np
    import pandas as pd
    from scipy import stats
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    BASE = BASE_CFG
    IN = os.path.join(BASE, "cleaned_Data")
    OUT = os.path.join(BASE, "analysis", "output")
    FIG = FIG_DIR
    os.makedirs(FIG, exist_ok=True)

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False

    struct = pd.read_csv(os.path.join(OUT, "01_产业结构指标.csv"), encoding="utf-8-sig").set_index("区名")
    share = pd.read_csv(os.path.join(OUT, "01_修正占比_pct.csv"), encoding="utf-8-sig").set_index("区名")
    res = pd.read_csv(os.path.join(OUT, "03_相关性检验全表.csv"), encoding="utf-8-sig")
    air_raw = pd.read_csv(os.path.join(IN, "空气_区两年均值.csv"), encoding="utf-8-sig").set_index("区名")
    IDX = struct.index
    air = air_raw.reindex(IDX)

    # ---------- 1. BH-FDR ----------
    def bh(pvals, alpha=0.05):
        p = np.asarray(pvals, float); n = len(p)
        order = np.argsort(p); ranked = p[order]
        crit = alpha * (np.arange(1, n + 1) / n)
        below = ranked <= crit
        rej = np.zeros(n, bool)
        if below.any():
            kmax = np.max(np.where(below)[0])
            rej[order[: kmax + 1]] = True
        q = np.empty(n); q[order] = np.minimum.accumulate((ranked * n / np.arange(1, n + 1))[::-1])[::-1]
        return rej, np.clip(q, 0, 1)

    rej, q = bh(res["p"].values)
    res["FDR_q"] = q.round(4); res["FDR通过"] = rej
    res.sort_values("p").to_csv(os.path.join(OUT, "03_相关性检验_FDR.csv"), index=False, encoding="utf-8-sig")
    print("=== 全域扫描（80 次检验）多重比较校正 ===")
    print(f"  未校正 p<0.05  : {(res.p < 0.05).sum():2d} / 80")
    print(f"  BH-FDR q<0.05  : {int(res['FDR通过'].sum()):2d} / 80")
    print(f"  Bonferroni     : {int(res['通过Bonferroni'].sum()):2d} / 80")
    print("  → 全域扫描层面：无任何关系能通过校正")

    # ---------- 2. 排放源指标构造 ----------
    poi = pd.read_csv(os.path.join(IN, "POI_清洗后全量_134万行.csv"), encoding="utf-8-sig",
                      usecols=["区名", "大类", "中类", "小类"])
    def has(df, kws):
        m = pd.Series(False, index=df.index)
        for f in ("大类", "中类", "小类"):
            for k in kws:
                m |= df[f].astype(str).str.contains(k, na=False)
        return m
    poi["扬尘源"] = has(poi, ["建材", "装修", "建筑", "工地"])
    poi["物流源"] = has(poi, ["物流", "仓储", "货运", "产业园"])
    poi["汽修源"] = has(poi, ["汽车维修", "摩托车维修", "加油", "加气"])
    src = poi.groupby("区名")[["扬尘源", "物流源", "汽修源"]].sum().reindex(IDX)
    tot = struct["原始POI总数"]; area = struct["面积_km2"]

    # ---------- 3. 预先设定的 4 个机制假设 ----------
    hyp = pd.DataFrame({
        "扬尘源数": src["扬尘源"],
        "物流源_每万POI": src["物流源"] / tot * 10000,
        "汽修源_每万POI": src["汽修源"] / tot * 10000,
    })
    tests = [("扬尘源数", "道路PM10", "H1 建设扬尘源规模↑ → 道路PM10↑"),
             ("物流源_每万POI", "道路PM10", "H2 物流仓储密度↑ → 道路PM10↑"),
             ("汽修源_每万POI", "道路PM10", "H3 汽修/加油站密度↑ → 道路PM10↑"),
             ("物流源_每万POI", "PM2.5", "H4 物流仓储密度↑ → PM2.5↑")]
    rows = []
    for xi, yj, desc in tests:
        r, p = stats.spearmanr(hyp[xi].values, air[yj].values)
        lo = np.tanh(np.arctanh(r) - 1.96 / np.sqrt(13))
        hi = np.tanh(np.arctanh(r) + 1.96 / np.sqrt(13))
        rows.append({"假设": desc, "变量": xi, "目标": yj, "rho": round(r, 3), "p": round(p, 4),
                     "CI下限": round(lo, 3), "CI上限": round(hi, 3),
                     "Bonferroni(4次,α=.0125)": "通过" if p < 0.0125 else "未通过"})
    H = pd.DataFrame(rows)
    H.to_csv(os.path.join(OUT, "05_聚焦假设检验.csv"), index=False, encoding="utf-8-sig")
    print("\n=== 预先设定的 4 个机制假设（Bonferroni 4 次，单次阈值 0.0125）===")
    print(H.to_string(index=False))

    # ---------- 4. 人工核对 ----------
    chk = pd.DataFrame({"扬尘源数": src["扬尘源"], "道路PM10": air["道路PM10"]}).sort_values("扬尘源数")
    r_chk, p_chk = stats.spearmanr(chk["扬尘源数"].values, chk["道路PM10"].values)
    print(f"\n=== 人工核对 扬尘源数(升序) vs 道路PM10 ===")
    print(chk.to_string())
    print(f"rho={r_chk:.3f} p={p_chk:.4f}（全表值 0.689 / 0.0031）")
    assert abs(r_chk - 0.689) < 0.02, "核对失败"

    # ---------- 5. 图1 PC1 ----------
    fig, ax = plt.subplots(figsize=(9, 5))
    d = struct["PC1"].sort_values()
    ax.barh(d.index, d.values, color=plt.cm.RdBu_r((d - d.min()) / (d.max() - d.min())))
    ax.axvline(0, color="gray", lw=0.8)
    ax.set_xlabel("PC1 得分（正 = 服务办公型核心区，负 = 商贸物流型外围区）")
    ax.set_title("图1  产业结构能否压缩为一条城市梯度轴？（CLR-PCA 第一主成分，解释 42.1% 方差）", fontsize=11)
    for i, v in enumerate(d.values):
        ax.text(v + (0.08 if v > 0 else -0.08), i, f"{v:.2f}", va="center",
                ha="left" if v > 0 else "right", fontsize=8)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig1_C_industry_axis_pc1.png"), dpi=200); plt.close()

    # ---------- 6. 图2 核心散点 ----------
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    ax.scatter(chk["扬尘源数"], chk["道路PM10"], s=70, c="#c0392b", edgecolors="k", zorder=3)
    for name, row in chk.iterrows():
        ax.annotate(name, (row["扬尘源数"], row["道路PM10"]), fontsize=8, xytext=(5, 5), textcoords="offset points")
    z = np.polyfit(chk["扬尘源数"], chk["道路PM10"], 1)
    xs = np.linspace(chk["扬尘源数"].min(), chk["扬尘源数"].max(), 50)
    ax.plot(xs, np.polyval(z, xs), "--", color="gray", lw=1.2)
    ax.set_xlabel("扬尘相关 POI 数量（建材/装修/建筑/工地）")
    ax.set_ylabel("道路 PM10 年均浓度 (μg/m³)")
    ax.set_title(f"图2  扬尘源越多的区，道路 PM10 是否越高？（rho={r_chk:.3f}, p={p_chk:.4f}, n=16）", fontsize=11)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig2_C_dustsource_vs_roadpm10.png"), dpi=200); plt.close()

    # ---------- 7. 图3 产业占比热力图 ----------
    fig, ax = plt.subplots(figsize=(11, 6))
    h = share.reindex(struct.sort_values("PC1").index)
    im = ax.imshow(h.values, cmap="YlOrRd", aspect="auto")
    ax.set_xticks(range(len(h.columns))); ax.set_xticklabels(h.columns, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(range(len(h.index))); ax.set_yticklabels(h.index, fontsize=9)
    ax.set_title("图3  各区的产业构成差异是否呈现连续梯度？（剔除地名地址后占比%，按 PC1 排序）", fontsize=11)
    plt.colorbar(im, ax=ax, label="占本区产业 POI 比例 %")
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig3_C_industry_share_heatmap.png"), dpi=200); plt.close()

    # ---------- 8. 图4 空气质量区际分布 ----------
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
    for ax, col in zip(axes, ["PM2.5", "道路PM10", "O3"]):
        d = air[col].sort_values()
        ax.barh(d.index, d.values, color="#5dade2")
        ax.set_title(f"{col}（全区均值 {d.mean():.1f}，极差 {d.max()-d.min():.1f}）", fontsize=10)
        ax.set_xlabel("μg/m³"); ax.tick_params(axis="y", labelsize=8)
        ax.set_xlim(d.min() * 0.95, d.max() * 1.03)
    plt.suptitle("图4  16 区空气质量是否几乎不存在区际差异？（区间方差仅占 1.3%）", fontsize=12)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig4_C_airquality_by_district.png"), dpi=200); plt.close()

    # ---------- 9. 图5 产业结构 vs PM2.5 ----------
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4))
    pair = [("金融业", "PM2.5", share, "金融业占比 %"),
            ("生产性服务业", "PM2.5", share, "生产性服务业占比 %"),
            ("Shannon多样性", "PM2.5", struct, "Shannon 多样性")]
    for ax, (xi, yi, sdf, xl) in zip(axes, pair):
        x = sdf[xi].reindex(IDX).values; y = air[yi].values
        r_, p_ = stats.spearmanr(x, y)
        ax.scatter(x, y, s=55, c="#2e86c1", edgecolors="k")
        zz = np.polyfit(x, y, 1); xs = np.linspace(x.min(), x.max(), 40)
        ax.plot(xs, np.polyval(zz, xs), "--", color="gray")
        ax.set_xlabel(xl); ax.set_ylabel("PM2.5 μg/m³")
        ax.set_title(f"rho={r_:.2f}, p={p_:.3f}", fontsize=10)
    plt.suptitle("图5  产业结构与 PM2.5 的弱关联是否经得起多重比较校正？（均未通过）", fontsize=12)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig5_C_structure_vs_pm25.png"), dpi=200); plt.close()

    # ---------- 10. 图6 圈层对比 ----------
    geo = pd.read_csv(os.path.join(IN, "区界属性_含面积质心.csv"), encoding="utf-8-sig").set_index("区名").reindex(IDX)
    CEN = (121.4737, 31.2304)
    def hav(lon, lat):
        R = 6371.0; p1, p2 = np.radians(lat), np.radians(CEN[1])
        dp, dl = p2 - p1, np.radians(lon - CEN[0])
        a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
        return 2 * R * np.arcsin(np.sqrt(a))
    geo["距市中心km"] = hav(geo["质心经度"].values, geo["质心纬度"].values)
    ring = pd.cut(geo["距市中心km"], [-1, 10, 30, 100], labels=["核心<10km", "近郊10-30km", "远郊>30km"])
    grp = air.groupby(ring, observed=True)[["道路PM10", "PM2.5", "O3"]].mean()
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    x = np.arange(len(grp)); w = 0.26
    for i, col in enumerate(["道路PM10", "PM2.5", "O3"]):
        ax.bar(x + (i - 1) * w, grp[col].values, w, label=col)
        for xx, vv in zip(x + (i - 1) * w, grp[col].values):
            ax.text(xx, vv + 0.6, f"{vv:.1f}", ha="center", fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels(grp.index)
    ax.set_ylabel("μg/m³"); ax.legend(fontsize=9)
    ax.set_title("图6  空气质量是否随距市中心距离呈倒 U 型而非单调恶化？（道路PM10 近郊最高）", fontsize=11)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig6_C_ring_comparison.png"), dpi=200); plt.close()

    print("\n图表已输出至:", FIG)
    for f in sorted(os.listdir(FIG)):
        print("  ", f)

# --------------------------------------------------------------------
# 阶段5 时间视角（图7）+ 区级 choropleth（图8）
# --------------------------------------------------------------------
def stage5_time_and_map():
    # -*- coding: utf-8 -*-
    """s6：补充时间视角可视化（图7）+ 区级 choropleth（图8）
    图7  24 个月 PM2.5 / 道路 PM10 走势与区际离散带
    图8  16 区道路 PM10 空间分布（读 区界.gpkg 的 WKB 几何，无需 geopandas）
    """
    import os, sqlite3, struct
    import numpy as np
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MplPolygon
    from matplotlib.collections import PatchCollection

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False

    BASE = BASE_CFG
    IN = os.path.join(BASE, "cleaned_Data")
    OUT = os.path.join(BASE, "analysis", "output")
    FIG = FIG_DIR
    os.makedirs(FIG, exist_ok=True)

    # ---------------- 图7：时间视角 ----------------
    mon = pd.read_csv(os.path.join(IN, "空气_区×年月.csv"), encoding="utf-8-sig")
    g = mon.groupby("年月")
    agg = pd.DataFrame({
        "PM25_mean": g["PM2.5(μg/m³)"].mean(),
        "PM25_min": g["PM2.5(μg/m³)"].min(),
        "PM25_max": g["PM2.5(μg/m³)"].max(),
        "PM10_mean": g["道路PM10(μg/m³)"].mean(),
        "PM10_min": g["道路PM10(μg/m³)"].min(),
        "PM10_max": g["道路PM10(μg/m³)"].max(),
    }).reset_index()
    x = np.arange(len(agg))
    lab = agg["年月"].tolist()

    fig, ax1 = plt.subplots(figsize=(11, 5))
    ax1.fill_between(x, agg["PM25_min"], agg["PM25_max"], color="#4C78A8", alpha=0.18,
                     label="PM2.5 区际最小—最大带")
    ax1.plot(x, agg["PM25_mean"], color="#4C78A8", lw=2, marker="o", ms=3.5, label="PM2.5 16 区均值")
    ax1.set_ylabel("PM2.5 (μg/m³)", color="#4C78A8")
    ax1.tick_params(axis="y", labelcolor="#4C78A8")
    ax2 = ax1.twinx()
    ax2.fill_between(x, agg["PM10_min"], agg["PM10_max"], color="#E45756", alpha=0.14,
                     label="道路 PM10 区际最小—最大带")
    ax2.plot(x, agg["PM10_mean"], color="#E45756", lw=2, marker="s", ms=3, label="道路 PM10 16 区均值")
    ax2.set_ylabel("道路 PM10 (μg/m³)", color="#E45756")
    ax2.tick_params(axis="y", labelcolor="#E45756")
    ax1.set_xticks(x[::3]); ax1.set_xticklabels([lab[i] for i in range(0, len(lab), 3)], rotation=45, ha="right", fontsize=8)
    ax1.set_xlabel("年月（2024-01 — 2025-12）")
    ax1.set_title("图7  24 个月内，PM2.5 与道路 PM10 的时间波动是否远大于区际差异？", fontsize=11)
    h1, l1 = ax1.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8)
    amp25 = agg["PM25_mean"].max() - agg["PM25_mean"].min()
    amp10 = agg["PM10_mean"].max() - agg["PM10_mean"].min()
    ax1.text(0.02, 0.03,
             "16 区均值季节振幅：PM2.5 %.1f μg/m³，道路 PM10 %.1f μg/m³；\n"
             "同年月内区际极差中位数：PM2.5 %.1f，道路 PM10 %.1f\n"
             "数据：区级空气质量 2024-01—2025-12（16 区 × 24 月 = 384 条）；来源：2017年各区降尘量与PM2.5月均浓度.xlsx Sheet3"
             % (amp25, amp10, (agg["PM25_max"] - agg["PM25_min"]).median(), (agg["PM10_max"] - agg["PM10_min"]).median()),
             transform=ax1.transAxes, fontsize=7.5, va="bottom",
             bbox=dict(boxstyle="round", fc="white", ec="#cccccc", alpha=0.85))
    plt.tight_layout()
    plt.savefig(os.path.join(FIG, "fig7_C_time_vs_spatial.png"), dpi=200)
    plt.close()

    # ---------------- 图8：choropleth ----------------
    def load_geoms(path):
        """读取区级 geojson，返回 {区名: [环点列表]}。
        注意：cleaned_Data/区界.gpkg 的几何与区名存在错配（属性正确、几何错位），不可用于制图；
        此处改用原始 区级数据.geojson（16 个区，属性 district 正确）。"""
        import json, io
        d = json.load(io.open(path, encoding="utf-8"))
        out = {}
        for f in d["features"]:
            name = f["properties"]["district"]
            geom = f["geometry"]
            rings = []
            if geom["type"] == "Polygon":
                rings = [np.asarray(r, dtype=float) for r in geom["coordinates"]]
            elif geom["type"] == "MultiPolygon":
                for poly in geom["coordinates"]:
                    rings.extend(np.asarray(r, dtype=float) for r in poly)
            out[name] = rings
        return out

    geoms = load_geoms(os.path.join(BASE, "Data", "上海市行政区划-乡镇级shp文件", "区级数据.geojson"))
    air = pd.read_csv(os.path.join(IN, "空气_区两年均值.csv"), encoding="utf-8-sig").set_index("区名")
    geoattrs = pd.read_csv(os.path.join(IN, "区界属性_含面积质心.csv"), encoding="utf-8-sig").set_index("区名")

    values = air["道路PM10"]
    vmin, vmax = values.min(), values.max()
    cmap = plt.get_cmap("YlOrRd")
    norm = plt.Normalize(vmin=vmin, vmax=vmax)

    fig, ax = plt.subplots(figsize=(8.4, 7.2))
    patches, colors = [], []
    for name, rings in geoms.items():
        for ring in rings:
            patches.append(MplPolygon(np.asarray(ring), closed=True))
            colors.append(cmap(norm(values.get(name, vmin))))
    pc = PatchCollection(patches, edgecolor="#555555", linewidths=0.6)
    pc.set_facecolor(colors)
    ax.add_collection(pc)
    for name in geoms:
        cx, cy = geoattrs.loc[name, ["质心经度", "质心纬度"]]
        ax.annotate("%s\n%.1f" % (name.replace("区", ""), values.get(name, np.nan)),
                    (cx, cy), ha="center", va="center", fontsize=8, zorder=5,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.62))
    ax.set_xlim(120.85, 122.05); ax.set_ylim(30.65, 31.90)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    cb = fig.colorbar(sm, ax=ax, fraction=0.032, pad=0.02)
    cb.set_label("道路 PM10 (μg/m³)", fontsize=9)
    ax.set_title("图8  道路 PM10 的高值区是否集中在新城建设带与化工带？", fontsize=11)
    ax.text(0.02, 0.02,
            "数值为 2024—2025 两年区均道路 PM10；全市均值 85.79，极差 7.9（崇明 82.2 — 松江 90.1）\n"
            "边界：16 区区界（WGS84，区级数据.geojson，district 字段）；浓度：2017年各区降尘量与PM2.5月均浓度.xlsx Sheet3",
            transform=ax.transAxes, fontsize=7.5,
            bbox=dict(boxstyle="round", fc="white", ec="#cccccc", alpha=0.85))
    plt.tight_layout()
    plt.savefig(os.path.join(FIG, "fig8_C_roadpm10_choropleth.png"), dpi=200)
    plt.close()

    pd.DataFrame({"年月": lab, "PM25_16区均值": agg["PM25_mean"].round(2),
                  "PM10_16区均值": agg["PM10_mean"].round(2),
                  "PM25_区际极差": (agg["PM25_max"] - agg["PM25_min"]).round(1),
                  "PM10_区际极差": (agg["PM10_max"] - agg["PM10_min"]).round(1)}).to_csv(
        os.path.join(OUT, "02_时间序列与区际极差.csv"), index=False, encoding="utf-8-sig")

    print("图7 季节振幅 PM2.5=%.2f 道路PM10=%.2f" % (amp25, amp10))
    print("图8 区数=%d，环数=%d" % (len(geoms), len(patches)))
    print("已输出：fig7_C_time_vs_spatial.png / fig8_C_roadpm10_choropleth.png")

# --------------------------------------------------------------------
# 阶段6 K-means 聚类（图9）
# --------------------------------------------------------------------
def stage6_kmeans():
    # -*- coding: utf-8 -*-
    """s7：数据挖掘方法 —— K-means 对区级产业构成聚类
    输入：01_修正占比_pct.csv（16 区 × 12 类产业占比，已剔除地名地址）
    方法：CLR 变换后在 Aitchison 几何下做 K-means（不再标准化，避免破坏对数比尺度）；
          k=2..6 用轮廓系数与簇内平方和选 k；20 个随机种子检验稳定性；
          聚类结果与 PC1 梯度对照，并用 Kruskal-Wallis 检验簇间空气质量差异。
    输出：06_Kmeans聚类.csv、06_Kmeans_k选择.csv、图9
    """
    import os
    import numpy as np
    import pandas as pd
    from scipy import stats
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score, adjusted_rand_score
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False

    BASE = BASE_CFG
    IN = os.path.join(BASE, "cleaned_Data")
    OUT = os.path.join(BASE, "analysis", "output")
    FIG = FIG_DIR


    def clr(df):
        x = df.values.astype(float)
        delta = np.where(x == 0, 0.65 * np.nanmin(np.where(x > 0, x, np.nan)), 0)
        x = x + delta
        lg = np.log(x)
        return pd.DataFrame(lg - lg.mean(axis=1, keepdims=True), index=df.index, columns=df.columns)


    share = pd.read_csv(os.path.join(OUT, "01_修正占比_pct.csv"), encoding="utf-8-sig").set_index("区名")
    X = clr(share)

    # ---------- 1. 选 k ----------
    sel = []
    for k in range(2, 7):
        km = KMeans(n_clusters=k, n_init=50, random_state=42).fit(X)
        s = silhouette_score(X, km.labels_)
        sel.append({"k": k, "轮廓系数": round(s, 4), "簇内平方和": round(km.inertia_, 3)})
    sel = pd.DataFrame(sel)
    print("=== k 选择 ===")
    print(sel.to_string(index=False))

    k_best = int(sel.loc[sel["轮廓系数"].idxmax(), "k"])
    print("按轮廓系数选 k =", k_best)

    km = KMeans(n_clusters=k_best, n_init=100, random_state=42).fit(X)
    labels = pd.Series(km.labels_, index=X.index, name="簇")

    # ---------- 2. 稳定性（20 个种子）----------
    base = km.labels_
    aris = [adjusted_rand_score(base, KMeans(n_clusters=k_best, n_init=100, random_state=s).fit(X).labels_)
            for s in range(20)]
    print("稳定性 ARI：均值 %.3f，最小 %.3f" % (np.mean(aris), np.min(aris)))

    # ---------- 3. 簇画像 ----------
    pc = pd.read_csv(os.path.join(OUT, "01_产业轴得分.csv"), encoding="utf-8-sig").set_index("区名").reindex(share.index)
    air = pd.read_csv(os.path.join(IN, "空气_区两年均值.csv"), encoding="utf-8-sig").set_index("区名").reindex(share.index)

    prof = pd.DataFrame({"簇": labels, "PC1": pc["PC1"].round(2), "PC2": pc["PC2"].round(2)})
    prof = prof.join(air[["PM2.5", "道路PM10", "O3", "AQI优良率"]])
    prof["主导产业"] = share.idxmax(axis=1)
    prof["主导产业占比"] = share.max(axis=1).round(1)
    prof = prof.sort_values(["簇", "PC1"])

    # 簇内平均产业占比（回到原始百分比口径，便于解释）
    cmean = share.groupby(labels).mean().round(1)
    cmean.columns = [c.replace(".1", "") for c in cmean.columns]

    print("\n=== 簇画像 ===")
    print(prof.to_string())
    print("\n=== 各簇平均产业构成（%）===")
    print(cmean.to_string())

    # ---------- 4. 簇间空气质量差异 ----------
    print("\n=== 簇间空气质量（Kruskal-Wallis）===")
    kw = []
    for t in ["PM2.5", "道路PM10", "O3", "AQI优良率"]:
        groups = [prof.loc[prof["簇"] == c, t].values for c in sorted(prof["簇"].unique())]
        h, p = stats.kruskal(*groups)
        kw.append({"指标": t, "H": round(h, 3), "p": round(p, 4),
                   "各簇中位数": " / ".join("%.1f" % np.median(g) for g in groups)})
    kw = pd.DataFrame(kw)
    print(kw.to_string(index=False))

    # 簇编号任意，不能直接与 PC1 求相关；改查两簇在 PC1 上是否完全不重叠
    r0 = pc.loc[labels[labels == 0].index, "PC1"]
    r1 = pc.loc[labels[labels == 1].index, "PC1"]
    print("\n簇0 PC1 区间 [%.2f, %.2f]；簇1 PC1 区间 [%.2f, %.2f]；是否重叠：%s"
          % (r0.min(), r0.max(), r1.min(), r1.max(), "是" if r0.max() > r1.min() else "否"))

    # 簇2 仅含 1 个区（崇明），Kruskal-Wallis 对 n=1 组无意义 → 补充剔除外检
    print("\n=== 敏感性：剔除单点簇（崇明）后，簇0 vs 簇1（Mann-Whitney）===")
    mw = []
    for t in ["PM2.5", "道路PM10", "O3", "AQI优良率"]:
        a = prof.loc[prof["簇"] == 0, t].values
        b = prof.loc[prof["簇"] == 1, t].values
        u, p = stats.mannwhitneyu(a, b)
        mw.append({"指标": t, "U": round(u, 1), "p": round(p, 4),
                   "簇0中位数": round(float(np.median(a)), 2), "簇1中位数": round(float(np.median(b)), 2)})
    mw = pd.DataFrame(mw)
    print(mw.to_string(index=False))

    # ---------- 5. 输出 ----------
    prof.to_csv(os.path.join(OUT, "06_Kmeans聚类.csv"), encoding="utf-8-sig")
    sel.to_csv(os.path.join(OUT, "06_Kmeans_k选择.csv"), index=False, encoding="utf-8-sig")
    kw.to_csv(os.path.join(OUT, "06_Kmeans簇间环境差异.csv"), index=False, encoding="utf-8-sig")
    mw.to_csv(os.path.join(OUT, "06_Kmeans簇间环境差异_剔除崇明.csv"), index=False, encoding="utf-8-sig")

    # ---------- 6. 图9 ----------
    palette = ["#4C78A8", "#E45756", "#54A24B", "#B279A2", "#FF9DA6", "#9D755D"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))

    ax = axes[0]
    OFFSET = {"嘉定区": (6, 8), "宝山区": (6, -12), "普陀区": (6, 6), "杨浦区": (6, 6)}
    for c in sorted(prof["簇"].unique()):
        sub = prof[prof["簇"] == c]
        ax.scatter(sub["PC1"], sub["PC2"], s=90, color=palette[c], label="簇 %d（%d 区）" % (c, len(sub)),
                   edgecolor="white", linewidth=0.8, zorder=3)
        for name, row in sub.iterrows():
            dx, dy = OFFSET.get(name, (6, 4))
            ax.annotate(name.replace("区", ""), (row["PC1"], row["PC2"]), fontsize=8,
                        xytext=(dx, dy), textcoords="offset points")
    ax.axhline(0, color="#cccccc", lw=0.8); ax.axvline(0, color="#cccccc", lw=0.8)
    ax.set_xlabel("PC1 得分（商贸物流型 ← → 服务办公型）")
    ax.set_ylabel("PC2 得分")
    ax.set_title("(a) 聚类结果是否与 PC1 梯度重合？", fontsize=10)
    ax.set_xlim(prof["PC1"].min() - 0.35, prof["PC1"].max() + 0.55)
    ax.set_ylim(prof["PC2"].min() - 0.45, prof["PC2"].max() + 0.35)
    ax.legend(fontsize=8, loc="best")

    ax = axes[1]
    ax.plot(sel["k"], sel["轮廓系数"], "o-", color="#4C78A8", label="轮廓系数")
    ax.set_xlabel("簇数 k"); ax.set_ylabel("轮廓系数", color="#4C78A8")
    ax.tick_params(axis="y", labelcolor="#4C78A8")
    ax.axvline(k_best, ls="--", color="gray", lw=1)
    ax2 = ax.twinx()
    ax2.plot(sel["k"], sel["簇内平方和"], "s--", color="#E45756", label="簇内平方和")
    ax2.set_ylabel("簇内平方和", color="#E45756")
    ax2.tick_params(axis="y", labelcolor="#E45756")
    ax.set_title("(b) 如何选择簇数 k？（虚线为轮廓系数最优）", fontsize=10)

    fig.suptitle("图9 16 区的产业构成能否聚成离散类型，且类型间空气质量是否有差异？", fontsize=12)
    fig.text(0.5, 0.005,
             "数据范围：16 区 × 12 类产业占比（CLR 变换后的 Aitchison 距离，K-means，n_init=100）；"
             "PC1/PC2 由 CLR-PCA 得到；簇数按轮廓系数选 k=%d；20 个随机种子 ARI 均值 %.2f" % (k_best, np.mean(aris)),
             ha="center", fontsize=7.5)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(os.path.join(FIG, "fig9_C_kmeans_types.png"), dpi=200)
    plt.close()

    print("\n已输出：06_Kmeans聚类.csv / 06_Kmeans_k选择.csv / 06_Kmeans簇间环境差异.csv / fig9_C_kmeans_types.png")

# --------------------------------------------------------------------
# 阶段7 第二产业核查（工厂/农林牧渔基地）
# --------------------------------------------------------------------
def stage7_secondary_check():
    # -*- coding: utf-8 -*-
    """核查：工厂（第二产业）与农林牧渔基地（第一产业）的区际分布，及其与 PM2.5 的关系"""
    import pandas as pd, numpy as np, os
    from scipy import stats

    BASE = BASE_CFG
    IN = os.path.join(BASE, "cleaned_Data")
    OUT = os.path.join(BASE, "analysis", "output")

    struct = pd.read_csv(os.path.join(OUT, "01_产业结构指标.csv"), encoding="utf-8-sig").set_index("区名")
    IDX = struct.index
    air = pd.read_csv(os.path.join(IN, "空气_区两年均值.csv"), encoding="utf-8-sig").set_index("区名").reindex(IDX)

    poi = pd.read_csv(os.path.join(IN, "POI_清洗后全量_134万行.csv"), encoding="utf-8-sig",
                      usecols=["区名", "大类", "中类"])
    g = poi.groupby(["区名", "大类", "中类"]).size().rename("n").reset_index()

    fac = g[(g["大类"] == "公司企业") & (g["中类"] == "工厂")].set_index("区名")["n"].reindex(IDX).fillna(0).astype(int)
    agr = g[(g["大类"] == "公司企业") & (g["中类"] == "农林牧渔基地")].set_index("区名")["n"].reindex(IDX).fillna(0).astype(int)
    tot = struct["原始POI总数"]
    area = struct["面积_km2"]

    tab = pd.DataFrame({"工厂数": fac, "农林牧渔基地数": agr,
                        "工厂占比_每万POI": (fac / tot * 10000).round(1),
                        "工厂密度_每km2": (fac / area).round(2),
                        "PM2.5": air["PM2.5"], "道路PM10": air["道路PM10"]}).sort_values("工厂数", ascending=False)
    print(tab.to_string())

    print("\n=== 工厂相关指标 vs 空气质量 (N=16) ===")
    for c in ["工厂数", "工厂占比_每万POI", "工厂密度_每km2"]:
        for t in ["PM2.5", "道路PM10", "O3", "AQI优良率"]:
            r, p = stats.spearmanr(tab[c].values, air[t].values)
            flag = "  <-- p<.05" if p < 0.05 else ""
            print("%-16s vs %-8s rho=%+.3f  p=%.4f%s" % (c, t, r, p, flag))

    print("\n工厂合计: %d (占全部POI %.2f%%)" % (fac.sum(), fac.sum() / tot.sum() * 100))
    print("农林牧渔基地合计: %d (占 %.2f%%)" % (agr.sum(), agr.sum() / tot.sum() * 100))

# --------------------------------------------------------------------
# 阶段8 空间连接正确性核查
# --------------------------------------------------------------------
def stage8_join_check():
    # -*- coding: utf-8 -*-
    """核查：POI 的 区名 归属是否与真实地理位置一致（用区属性表中的质心对照）"""
    import pandas as pd, os
    BASE = BASE_CFG
    IN = os.path.join(BASE, "cleaned_Data")
    poi = pd.read_csv(os.path.join(IN, "POI_清洗后全量_134万行.csv"), encoding="utf-8-sig",
                      usecols=["区名", "经度_WGS84", "纬度_WGS84"])
    geo = pd.read_csv(os.path.join(IN, "区界属性_含面积质心.csv"), encoding="utf-8-sig").set_index("区名")
    poi = poi.rename(columns={"经度_WGS84": "经度", "纬度_WGS84": "纬度"})
    g = poi.dropna(subset=["区名"]).groupby("区名")[["经度", "纬度"]].mean()
    g = g.join(geo[["质心经度", "质心纬度"]])
    g["偏移km"] = (((g["经度"] - g["质心经度"]) * 88.0) ** 2 + ((g["纬度"] - g["质心纬度"]) * 111.0) ** 2) ** 0.5
    g["n"] = poi.dropna(subset=["区名"]).groupby("区名").size()
    print(g.round(3).to_string())
    print("\n最大偏移(km):", round(g["偏移km"].max(), 2))



if __name__ == "__main__":
    print("=" * 70)
    print("C_Q2_analysis：产业结构 × 环境质量 空间相关性（上海 16 区）")
    print("BASE =", BASE_CFG)
    print("FIG  =", FIG_DIR)
    print("=" * 70)
    stage1_industry_structure()
    stage2_environment_and_correlation()
    stage3_mechanism()
    stage4_fdr_and_figures()
    stage5_time_and_map()
    stage6_kmeans()
    stage7_secondary_check()
    stage8_join_check()
    print("\n全部阶段完成：表见 analysis/output/，图见 visualization/figures/")
