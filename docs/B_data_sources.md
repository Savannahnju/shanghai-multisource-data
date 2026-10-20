# 上海地铁客流量 2017 数据源清单

> 数据源清单（上海地铁客流量 2017 子项目）
> 上传位置：`上海地铁客流量2017/data_sources.md`
> 最终由组长汇总为根目录 `data_sources.md`

---

## 0. 基本信息

| 项目 | 内容 |
|---|---|
| 子项目 | 上海地铁客流量 2017（2017 年上海市轨道交通进出站客流分析） |
| 负责数据源数量 | 4 个（1 个主数据源 + 3 个辅助数据源，均出自同一开源数据集 MetroFlow） |
| 记录时间 | 2026-10-16 |

---

## 1. 数据源总览表

> 每个数据源一行。主数据源为地铁进出站客流，其余为辅助数据源。

| 数据源名称 | 来源（URL/机构） | 获取方式 | 数据类型 | 原始规模 | 时间范围 | 采集时间 | 许可/使用说明 | 主要字段 | 跨源关联字段 |
|---|---|---|---|---|---|---|---|---|---|
| 2017年上海市地铁进出站客流数据 | 开源数据集 MetroFlow（GitHub：https://github.com/Ariza-Sun/MetroFlow ；数据托管于 figshare：https://doi.org/10.6084/m9.figshare.33436675 ） | 开源数据下载（GitHub 仓库 + figshare DOI） | CSV | 3,788,892 行 × 13 列，217,442,845 字节（约 207.4 MB） | 2017-05-01 ~ 2017-08-31，共 123 天 | 数据 2017 年采集、2025 年发布；本地下载约 2026-10 | MIT License；引用论文 Sun et al., Scientific Data (2025) | date,timeslot,startTime,endTime,station,inFlow,outFlow,CinFlow,HBOinFlow,NHBinFlow,CoutFlow,HBOoutFlow,NHBoutFlow | date/timeslot/startTime（时间）、station（站点ID） |
| 站点信息表（辅助） | 同上，MetroFlow 仓库 `Data/stationInfo.csv` | 开源数据下载 | CSV | 302 行 × 6 列，19,872 字节（约 19.4 KB） | 静态站点属性（2017 年线网） | 同主数据 | MIT License | stationID,name,lon,lat,neighbour | stationID（↔ 主数据 station）、lon/lat（空间关联） |
| 上海市逐小时气象数据（辅助） | 同上，MetroFlow 仓库 `Data/MetaData/shanghai_weatherHourly.csv`（气象字段命名与 Open-Meteo 一致） | 随数据集下载 | CSV | 2,952 行 × 5 列，146,252 字节（约 142.8 KB） | 2017-05-01 00:00 ~ 2017-08-31 23:00（逐小时） | 同主数据 | MIT License | date,temperature_2m,apparent_temperature,rain,wind_speed_10m | date（时间关联） |
| 工作日历表（辅助） | 同上，MetroFlow 仓库 `Data/MetaData/workday_calendar.csv` | 随数据集下载 | CSV | 123 行 × 2 列，1,367 字节（约 1.3 KB） | 2017-05-01 ~ 2017-08-31，共 123 天 | 同主数据 | MIT License | date,isWorday | date（时间关联） |

---

## 2. 各数据源详细说明

### 2.1 2017年上海市地铁进出站客流数据（主数据源）

| 项目 | 内容 |
|---|---|
| 来源 | 开源数据集 MetroFlow：GitHub 仓库 https://github.com/Ariza-Sun/MetroFlow ；数据托管于 figshare，修正版 https://doi.org/10.6084/m9.figshare.33436675 （原始版 https://doi.org/10.6084/m9.figshare.28844942 ） |
| 获取方式 | 开源数据下载（GitHub 仓库 + figshare DOI 直接下载，非 API/爬取） |
| 数据类型 | CSV（逗号分隔，UTF-8） |
| 原始规模 | 3,788,892 行 × 13 列；217,442,845 字节（约 207.4 MB），单源已远超 200 MB |
| 时间范围 | 2017-05-01 ~ 2017-08-31，共 123 天；每天 06:00 ~ 23:00，每 10 分钟一个时间片，共 102 片/日 |
| 采集时间 | 原始交易记录 2017 年采集；数据集 2025 年发布；本地下载约 2026-10 |
| 许可/使用说明 | MIT License（可自由使用、修改、分发，需保留版权声明）；引用要求：使用请引用 Sun, Peiyan, et al. "Human mobility datasets in the complex metro system of Shanghai." Scientific Data 12.1 (2025)。数据为站点级聚合客流，不含个人身份信息 |
| 主要字段 | date（日期，YYYYMMDD）、timeslot（全期连续时间片索引 0~12545，天序×102+日内片序）、startTime/endTime（日内起止时刻，HHMMSS）、station（站点ID，112~2057）、inFlow/outFlow（进/出站客流总量）、CinFlow/HBOinFlow/NHBinFlow（进站通勤/家-其他/非基于家分量）、CoutFlow/HBOoutFlow/NHBoutFlow（出站三分量） |
| 跨源关联字段 | date/timeslot/startTime（时间 → 天气/工作日）、station（→ 站点信息表 stationID）、站点坐标（→ 空间关联） |
| 可关联数据源 | 站点信息表、逐小时气象数据、工作日历表；以及组内其他成员的区划/POI/空气质量等数据（空间 Join） |
| 关联方式 | 时间（date/startTime 对齐到小时/日）/ 实体（station ↔ stationID）/ 空间（站点经纬度） |
| 采集脚本 | 无（现成开源数据下载） |
| 备注 | ① 出行目的三分量 C/HBO/NHB 由数据集处理流程 step1（出行标注）生成，分别对应通勤(Commuting)、基于家-其他(Home-Based Other)、非基于家(Non-Home-Based)，全网合计占比约为 32.0% / 29.5% / 38.5%（以进站计）；② 数据为闭合/配平客流：每日进站总量 == 出站总量（全网 728,868,609 == 728,868,609），可交叉验证；③ 所有字段无缺失、无完全重复行；④ 6 个日期当日总客流异常偏低（<500 万），判定为采集不完整，分析时建议剔除，剩 117 个完整日期；⑤ 302 个站点，站点ID 不连续（112~2057），需与站点信息表 join 还原名称与坐标 |

### 2.2 站点信息表（辅助数据源）

| 项目 | 内容 |
|---|---|
| 来源 | MetroFlow 仓库 `Data/stationInfo.csv`（与主数据同源） |
| 获取方式 | 随数据集下载 |
| 数据类型 | CSV（含行号列 Unnamed: 0） |
| 原始规模 | 302 行 × 6 列，19,872 字节（约 19.4 KB） |
| 时间范围 | 静态站点属性（2017 年线网，不随时间变化） |
| 采集时间 | 同主数据 |
| 许可/使用说明 | MIT License |
| 主要字段 | stationID（站点ID，112~2057）、name（站点英文名）、lon/lat（经纬度）、neighbour（相邻站点ID列表，JSON 数组字符串） |
| 跨源关联字段 | stationID（↔ 主数据 station）、lon/lat（空间关联）、name（实体关联） |
| 关联方式 | 实体（stationID 主键）/ 空间（经纬度） |
| 采集脚本 | 无 |
| 备注 | ① 302 行与主数据 302 个站点完全对应，无缺失、无重复；② neighbour 字段可用于构建站点邻接关系（网络拓扑/邻近度分析）；③ name 为英文，报告展示建议加中文对照或保留英文 |

### 2.3 上海市逐小时气象数据（辅助数据源）

| 项目 | 内容 |
|---|---|
| 来源 | MetroFlow 仓库 `Data/MetaData/shanghai_weatherHourly.csv`（字段命名与 Open-Meteo 历史气象 API 一致，为数据集作者整理的历史气象元数据） |
| 获取方式 | 随数据集下载（无需自行调用气象 API） |
| 数据类型 | CSV |
| 原始规模 | 2,952 行 × 5 列，146,252 字节（约 142.8 KB） |
| 时间范围 | 2017-05-01 00:00:00 ~ 2017-08-31 23:00:00，逐小时（123 天 × 24 = 2952 小时，完整） |
| 采集时间 | 同主数据 |
| 许可/使用说明 | MIT License（随数据集提供） |
| 主要字段 | date（时间，含时分秒）、temperature_2m（2 米气温 ℃）、apparent_temperature（体感温度 ℃）、rain（小时降雨量 mm）、wind_speed_10m（10 米风速 km/h） |
| 跨源关联字段 | date（时间，聚合到日/小时后与主数据关联） |
| 关联方式 | 时间（date/startTime 对齐） |
| 采集脚本 | 无（随数据集提供） |
| 备注 | ① 与主数据时间范围完全重合（2017-05-01 ~ 08-31），可直接按小时/日对齐；② 全字段无缺失；③ 与日客流的相关性较弱：日均气温 -0.08、最高气温 -0.09、日降雨量 -0.15、风速 -0.05，提示天气对地铁客流影响有限，降雨为相对最显著因子 |

### 2.4 工作日历表（辅助数据源）

| 项目 | 内容 |
|---|---|
| 来源 | MetroFlow 仓库 `Data/MetaData/workday_calendar.csv`（数据集作者整理的工作日历） |
| 获取方式 | 随数据集下载 |
| 数据类型 | CSV |
| 原始规模 | 123 行 × 2 列，1,367 字节（约 1.3 KB） |
| 时间范围 | 2017-05-01 ~ 2017-08-31，共 123 天（与主数据逐日对应） |
| 采集时间 | 同主数据 |
| 许可/使用说明 | MIT License（随数据集提供） |
| 主要字段 | date（日期，YYYYMMDD）、isWorday（是否工作日，1=工作日，0=非工作日/节假日） |
| 跨源关联字段 | date（时间关联） |
| 关联方式 | 时间（date 对齐） |
| 采集脚本 | 无 |
| 备注 | ① 123 天中工作日 87 天、非工作日 36 天（含节假日与周末）；② 剔除 6 个不完整日期后，完整工作日 81 天、非工作日 36 天；③ 用于工作日/非工作日客流差异分析，是本项目核心的分组维度之一 |

---

## 3. 跨源关联字段汇总

> 用于多源数据关联与后续融合参考。

| 本数据源 | 关联字段 | 可关联数据源 | 对方关联字段 | 关联方式 | 关联说明 |
|---|---|---|---|---|---|
| 地铁客流数据 | date, startTime | 逐小时气象数据 | date | 时间 | 将 10 分钟时间片的客流聚合到日/小时，与逐小时气象对齐 |
| 地铁客流数据 | date | 工作日历表 | date | 时间 | 按日期打标工作日/非工作日，用于客流分组对比 |
| 地铁客流数据 | station | 站点信息表 | stationID | 实体 | 站点ID 主键 join，还原站点名称与坐标 |
| 站点信息表 | lon, lat | 组内其他成员空间数据（POI/区划/绿地等） | 经纬度 | 空间 | 站点坐标空间 Join，分析站点周边用地/POI 结构对客流的影响 |

---

## 4. 采集日志摘要

| 数据源 | 采集脚本 | 采集频率 | 是否遵守robots/限速 | 原始数据存放位置 | 校验值 |
|---|---|---|---|---|---|
| 2017年上海市地铁进出站客流数据 | 无（开源数据下载） | 一次性 | 不适用 | `上海地铁客流量2017/metroData_InOutFlow.csv` | MD5（2026-10-16 计算）：c96e6be386c7abf1b6ab34f86a2fca4e |
| 站点信息表 | 无 | 一次性 | 不适用 | `上海地铁客流量2017/stationInfo.csv` | MD5：58923a0b7c296d286a2d62ba86058c14 |
| 上海市逐小时气象数据 | 无（随数据集提供） | 一次性 | 不适用 | `上海地铁客流量2017/天气&工作日/shanghai_weatherHourly.csv` | MD5：cdd89a29022efc008c9d746455b3cb2a |
| 工作日历表 | 无（随数据集提供） | 一次性 | 不适用 | `上海地铁客流量2017/天气&工作日/workday_calendar.csv` | MD5：3aaf9f34d64e3702a9555d150cebc698 |

---

## 5. 数据规模与合规说明

- 本子项目数据源总原始规模：约 207.6 MB（主数据 207.4 MB + 辅助约 0.16 MB）
- 是否满足单源≥200MB：是（主数据 207.4 MB 即已满足）
- 是否涉及个人敏感信息：否（为站点级聚合客流，不含个人身份信息，数据已脱敏）
- 是否遵守服务条款与robots：是（全部为 MIT License 开源数据集，可自由使用，无爬取行为）
- 其他说明：① 数据为 MetroFlow 开源数据集（GitHub + figshare），采用 MIT License，使用需保留版权声明并引用论文 Sun et al., Scientific Data 12 (2025)；② 主数据时间覆盖 2017 年 5–8 月（123 天），含工作日/节假日/夏季高温与降雨天气，适合做工作日-节假日差异、天气影响等分析；③ 数据为进出站闭合客流，可直接计算全网进站=出站总量校验；④ 6 个不完整日期（20170504、20170508、20170509、20170616、20170627、20170628）建议在正式建模前剔除

---

## 6. 备注

- 本文件为该子项目数据源清单，最终由组长汇总为根目录 `data_sources.md`。
- 本子项目 4 个数据文件均出自同一开源数据集 MetroFlow，MIT License 已覆盖全部文件。
- 跨源关联字段可在数据融合完成后补充或修正。
- 辅助数据源（站点信息表、气象数据、工作日历表）已在总览表与详细说明中注明"辅助数据源"。

---

## 附：数据引用（BibTeX）

```bibtex
@article{sun2025human,
  title   = {Human mobility datasets in the complex metro system of Shanghai},
  author  = {Sun, Peiyan and Yang, Jinming and Huang, Zongyuan and Huang, Shaoyu and
             Xu, Shengyuan and Wang, Weipeng and Guo, Wenxuan and Feng, Yuting and
             Zhai, Xi and Yang, Tao and others},
  journal = {Scientific Data},
  volume  = {12},
  number  = {1},
  pages   = {1--9},
  year    = {2025},
  publisher = {Nature Publishing Group}
}
```

- 论文数据描述：https://www.nature.com/articles/s41597-025-05416-8
- 数据 DOI（修正版）：https://doi.org/10.6084/m9.figshare.33436675
