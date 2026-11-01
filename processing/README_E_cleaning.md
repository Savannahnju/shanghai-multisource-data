# 数据清洗脚本说明（E · 舒栎洁）

> 配套文档：`docs/E\_cleaning\_report.md`（清洗结果报告）、`docs/E\_data\_quality.md`（字段质量检查）
> 最后更新：2026-11-01

\---

## 一、脚本清单与执行顺序

按**优先级**排列（P0 = D 的研究问题相关，优先交付；P1 = B / C）。

|顺序|脚本|优先级|清洗对象|主要产出|
|-|-|-|-|-|
|1|`E\_cleaning\_air.py`|P0-1|空气 xlsx（3 个 sheet）+ Zenodo 补充|区×月、区年均、2017 长表|
|2|`E\_cleaning\_green.py`|P0-2|植被韧性栅格 + 年鉴绿地/人口|区级 16 行宽表|
|3|`E\_cleaning\_district.py`|P0-3|区级 shp/geojson|16 区边界 + 面积 + 质心|
|4|`E\_cleaning\_metro.py`|P1-4|地铁客流 378 万行 + 站点 + 日历|全量 + 样本 + 区×日|
|5|`E\_cleaning\_weather.py`|P1-5|小时气象 + 工作日历|小时表 + 日聚合|
|6|`E\_cleaning\_poi.py`|P1-6|POI 142 万行|全量 + 样本 + 区×产业|
|7|`E\_handoff\_tables.py`|交接|汇总上述产出为分析宽表|**B 的区×月（52 行）、D 的区级宽表（16 行）**|

公共模块：`E\_common.py`（区名标准化、编码规范、缺失统计、日志），**不单独运行**。

一键重跑：

```bash
PY="C:/Users/34719/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
$PY processing/E\_cleaning\_air.py
$PY processing/E\_cleaning\_green.py
$PY processing/E\_cleaning\_district.py
$PY processing/E\_cleaning\_metro.py
$PY processing/E\_cleaning\_weather.py
$PY processing/E\_cleaning\_poi.py
$PY processing/E\_handoff\_tables.py   # 最后跑，依赖上面全部产出
```

> 交给 B / C / D 的宽表字段说明见 `data/metadata/metro\_columns.csv`。

\---

## 二、依赖

```
pandas==3.0.6        numpy==2.5.4        xlrd==2.0.2
openpyxl==3.1.5      tifffile==2026.10.15 imagecodecs==2026.10.10
pyshp==3.1.6         pyproj==3.8.0       shapely==2.2.0
geopandas==1.2.0     pyogrio==0.13.0
```

`geopandas` 仅用于 POI 空间连接与 `.gpkg` 导出；缺失时 `E\_cleaning\_district.py`
会自动降级为 `.geojson + .csv`，POI 空间连接则会失败。

\---

## 三、输入路径（参数化，无硬编码绝对路径）

优先级：**命令行参数 > 环境变量 > 相对推导**

```bash
# 方式一：环境变量（推荐，设一次即可）
export SH\_TEAM\_DATA="/d/团队数据/data"

# 方式二：每个脚本单独指定
$PY processing/E\_cleaning\_air.py --team-data "D:/团队数据/data"

# 方式三：默认相对推导
#   项目根/../绿地占比、植被韧性/data  ->  存在则使用
#   否则回退到 项目根/data/raw
```

常用参数：

|参数|适用脚本|说明|
|-|-|-|
|`--team-data`|全部|团队原始数据根目录|
|`--district-file`|green / district / poi|指定区界文件（shp 或 geojson）|
|`--raster-dir`|green|植被韧性栅格目录|
|`--cleaned` / `--processed`|全部|输出目录|
|`--no-full`|metro / poi|跳过全量 CSV 写出（只需样本时用，快很多）|
|`--sample-frac`|poi|样本比例，默认 0.01|

\---

## 四、输出文件对照

### data/cleaned/（交付层）

|文件|行数|用途|入仓文件名|
|-|-|-|-|
|`cleaned\_air\_monthly.csv`|384|区×月 空气质量（2024–2025）|`cleaned\_air\_sample.csv`|
|`cleaned\_green.csv`|16|**D 的 Q3** 主表（植被+年鉴）|`cleaned\_green\_sample.csv`|
|`cleaned\_district.gpkg`|16|区界与面积质心|`cleaned\_district\_sample.shp`（+4 附属）|
|`cleaned\_weather\_hourly.csv`|2,808|小时气象（117 天）|`cleaned\_weather\_sample.csv`|
|`cleaned\_weather\_daily.csv`|117|**B 的 Q1** 日尺度气象|—|
|`cleaned\_metro.csv`|3,568,266|客流全量（554 MB）|— 超 100 MB 上限|
|**`cleaned\_metro\_sample.csv`**|30,498|1 个完整工作日 × 25 列|`cleaned\_metro\_sample.csv`（4.72 MB）|
|`cleaned\_metro\_daily\_district.csv`|1,521|**B 的 Q1** 区×日 客流|—|
|**`cleaned\_metro\_month\_district.csv`**|52|**B 的 Q1 主表**（13 区 × 4 月）|—|
|`cleaned\_metro\_station\_month.csv`|1,196|站×月 备查（299 站 × 4 月）|—|
|`cleaned\_poi.csv`|1,339,912|POI 全量（241 MB）|— 超 100 MB 上限|
|**`cleaned\_poi\_sample.csv`**|13,399|1% 随机样本|`cleaned\_poi\_sample.csv`（2.41 MB）|
|`cleaned\_poi\_district\_industry.csv`|208|**C 的 Q2 主表**（16 区 × 13 类）|—|
|`cleaned\_poi\_by\_district.csv`|16|区级 POI 总数|—|
|**`cleaned\_green\_analysis\_wide.csv`**|16|**D 的 Q3 主表**（16 × 17）|—|

**加粗** = 由 `E\_handoff\_tables.py` 产出的分析宽表，是 B / C / D 直接使用的主表。
**仓库只放抽样样本**：全量（554 / 241 MB）与中间产物不入仓，理由见 `.gitignore`。
`air\_annual\_\*` 落在 `data/processed/`，见下表。

### data/processed/（中间产物层）

|文件|说明|
|-|-|
|`air\_2017\_long.csv`|2017 区×月 降尘量 + PM2.5（192 行）|
|`air\_2017\_q1\_may\_aug.csv`|2017 年 5–8 月窗口（64 行，B 直接用）|
|`air\_annual\_2024.csv` / `air\_annual\_2024\_2025.csv`|区年均 / 两年均值（各 16 行）|
|`air\_city\_monthly.csv`|Zenodo 全市月度（24 行，仅趋势参照）|
|`green\_resilience\_zonal.csv`|栅格分区统计原始结果|
|`green\_yearbook\_green.csv` / `green\_yearbook\_pop.csv`|年鉴绿地 / 人口清洗后|
|`metro\_station\_clean.csv`|站点表（含区名）|
|`metro\_daily\_totals.csv`|每日进/出站总量（299 站）+ 昆山站分量 + 全站配平校验列|
|`workday\_calendar\_clean.csv`|工作日历（拼写已修正）|

### data/metadata/（元数据层）

|文件|说明|
|-|-|
|`checksums.txt`|原始文件 SHA256 校验值（两批共 47 条）|
|`data\_volume\_report.md`|各源清洗前后行数/字段数变化与原因|
|`metro\_columns.csv`|**地铁表 25 个字段的中英对照 + 单位 + 含义 + 来源**（含 C/HBO/NHB 三分量定义）|

\---

## 五、tips

1. **区界不在项目里**
权威区界在 `<team-data>/上海市行政区划-乡镇级shp文件/`。项目内
`data/raw/districts/shanghai\_districts\_datav.json` 只是 DataV 临时副本，**不用于正式交付**。
2. **`timeslot` 是全局编号**
取值范围 0–12545，不是每天 0–101。日内时段 = `timeslot % 102`。
3. **两套绿地面积不可混算**
`遥感绿地面积\_公顷`（像元口径，全市约 26,114 公顷）与
`绿地面积(公顷)`（年鉴规划口径，全市 174,064 公顷）相差 6.67 倍，只可互证。
4. **POI 必须用 WGS84 做空间连接**
GCJ02 与 WGS84 在上海实测相差约 **483 m**（东西 +429 m、南北 −219 m），
远大于中心城区街道尺度，用 GCJ02 配区界会把点系统性错划到邻区。
5. **奉贤 / 金山 / 崇明无地铁站点**
2017 年未覆盖，区内客流记**缺失**，不得补 0，否则会拉低区域均值。
6. **`STL\_AR1` 负值不是"低韧性"**
负值表示模型不适用（约 14.4%），统计时剔除；`V2\_AR1` / `V2\_VAR` 则相反，越负韧性越强。
7. **运行 `E\_cleaning\_metro.py` 需要约 1 GB 内存 + 550 MB 磁盘**
全量 CSV 有 554 MB，如只需样本请加 `--no-full`。
8. **地铁配平差额是剔站造成的，不是数据缺陷**
原始 302 站逐日进站 = 出站（差值恒为 0）。剔除昆山 3 站（1114/1115/1116）后，
299 站汇总会出现 -4,359 \~ +2,355 的差 —— 加回昆山站残差即归零。脚本已把这层溯源写进校验日志。
9. **风速单位是 km/h，不是 m/s**
`wind\_speed\_10m` 沿用 Open-Meteo 默认单位 **km/h**（实测 0.72–33.99，约 0.2–9.4 m/s）。
日表列名为 `日最大风速\_公里每小时`；**不要再按 m/s 解释**，否则会把微风的量级误读成 5–6 级风。
10. **地铁 6 个分项字段含义见 B 的 `data\_sources.md`**
C = 通勤（Commuting）、HBO = 基于家-其他（Home-Based Other）、NHB = 非基于家（Non-Home-Based）。
全量验证分项加总**严格等于**总量，可放心使用。

