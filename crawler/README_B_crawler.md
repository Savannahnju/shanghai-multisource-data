# B · 数据采集说明（README · 采集 / 爬虫）

> 研究问题（Q1）：**城市环境质量是否与地铁客流量（2017 年）有关？**
> B 负责的 4 个数据源均出自开源数据集 **MetroFlow**，采用**开源数据下载**方式获取，**未编写爬虫**。
> 本文件说明采集方式、步骤、合规性与校验，供最终报告「数据源与采集」部分引用。

---

## 1. 采集方式总览

| 数据源 | 获取方式 | 采集脚本 | robots/限速 |
|---|---|---|---|
| 2017 年上海市地铁进出站客流 | 开源数据下载（GitHub + figshare） | 无 | 不适用 |
| 站点信息表 | 随数据集下载 | 无 | 不适用 |
| 上海市逐小时气象数据 | 随数据集下载 | 无 | 不适用 |
| 工作日历表 | 随数据集下载 | 无 | 不适用 |

## 2. 为什么不用爬虫

- 数据为**已发布的 MIT License 开源数据集**（MetroFlow），提供 GitHub 仓库与 figshare DOI 直接下载，无需爬取；
- 采用下载而非爬取，**天然遵守服务条款、无 robots 限制、无反爬风险**；
- 数据为站点级聚合客流，不含个人身份信息，合规安全。

## 3. 采集步骤（下载）

1. 访问 GitHub 仓库：https://github.com/Ariza-Sun/MetroFlow ；
2. 主数据 `metroData_InOutFlow.csv`（约 207.4 MB）自 figshare 修正版下载：https://doi.org/10.6084/m9.figshare.33436675 ；
3. 辅助数据 `stationInfo.csv`、`shanghai_weatherHourly.csv`、`workday_calendar.csv` 自仓库 `Data/` 与 `Data/MetaData/` 下载；
4. 本地按目录结构存放（见下），并计算 MD5 校验。

```
上海地铁客流量2017/
├── metroData_InOutFlow.csv          # 主数据（207.4 MB）
├── stationInfo.csv                  # 站点信息
└── 天气&工作日/
    ├── shanghai_weatherHourly.csv   # 逐小时气象
    └── workday_calendar.csv         # 工作日历
```

## 4. 许可与合规

- **许可**：MIT License，可自由使用、修改、分发，需保留版权声明并引用：
  Sun, Peiyan, et al. "Human mobility datasets in the complex metro system of Shanghai." *Scientific Data* 12.1 (2025).
- **合规**：全部为开源数据直接下载，无爬取行为，遵守服务条款与 robots 约定。

## 5. 校验（MD5，2026-10-16 计算）

| 数据源 | MD5 |
|---|---|
| `metroData_InOutFlow.csv` | `c96e6be386c7abf1b6ab34f86a2fca4e` |
| `stationInfo.csv` | `58923a0b7c296d286a2d62ba86058c14` |
| `shanghai_weatherHourly.csv` | `cdd89a29022efc008c9d746455b3cb2a` |
| `workday_calendar.csv` | `3aaf9f34d64e3702a9555d150cebc698` |

## 6. 说明

- 若课程要求「数据采集脚本」，本数据源可用一个**下载脚本（downloader）**代替爬虫：从 figshare DOI / GitHub raw 拉取并校验 MD5，逻辑简单、无需解析网页。
- 需要的话可补一个 `B_download.py`（urllib/requests + hashlib 校验），与现有 `fuse_environment_metro.py` 衔接，保证「采集 → 融合」全链路可复现。
