# B · 上海地面道路指数 爬取失败说明（README）

> 对应脚本：[`B_get_data_failure.py`](B_get_data_failure.py)
> 目标数据集：上海市公共数据开放平台「地面道路指数」`data.sh.gov.cn` 数据集 id=2159 / 接口 66591
> 目标时间：2024-01-01 ~ 2026-01-01（想取 2024 全年历史数据）
> 结论先行：**反爬机制强 + 接口是「预览通道」有翻页上限**，拿不到 2024 历史明细；完整数据属**有条件开放**，需申请审批后走文件下载。

---

## 1. 目标与总体思路

- **目标**：抓取上海市「地面道路指数」2024 年全年数据，作为项目分析用的补充数据。
- **平台**：`data.sh.gov.cn`（上海市公共数据开放平台）。
- **思路两条腿走**：
  1. **浏览器路线**：用 Playwright 驱动 Edge 过瑞数反爬、登录拿会话，找接口/文件下载入口；
  2. **接口路线**：直接 POST 接口 `2159/66591`，用 offset/limit 翻页（数据按时间倒序），客户端按时间窗口过滤出 2024。

## 2. 失败原因（按重要性排序）

### 原因 1（核心）：接口是「预览通道」，offset 有翻页上限

实测 offset 爬到约 **69000** 时持续返回 `code=999999 "获取数据资源异常"`。用对照实验（冷却足够久后把大 offset 放第一个请求）确认：

| 请求 | 结果 |
|---|---|
| `offset=69000`（首个请求） | `999999 获取数据资源异常` |
| `offset=0`（对照） | `000000` 成功，返回 `*地面全路网` 聚合行 |
| `offset=69000`（复测） | `999999` |

→ **是翻页上限（约 1000~5000），不是限流**。未申请授权时，token 接口只是「预览」，只能翻到最近的数据，够不到 2024。

### 原因 2：反爬机制强（瑞数 Ruishu）

- 数据集**详情页**有瑞数反爬，直接 `requests` 拿不到接口元数据/下载入口，必须用真实浏览器（Playwright 驱动 Edge）过反爬、登录、保存会话后，才勉强能看到接口参数。
- 接口本身也有**限流**（请求过快返回 `999999`），脚本里靠 20~25 秒间隔 + 180 秒退避重试才不被打断——但这解决不了翻页上限。

### 原因 3：接口参数只有 3 个，没有日期范围 / 区域过滤

接口输入参数仅 `jhpt_update_time`（字符型，精确到秒的等值匹配）、`offset`、`limit` 三个，**没有时间范围、没有区域过滤字段**，所以只能靠 offset 翻页 + 客户端过滤，这条路又被翻页上限堵死。

### 原因 4：预览只返回聚合行，不返回逐路网明细

预览通道返回的是 `fstr_regionid="total"` / `fstr_regionname="*地面全路网"` 的聚合行，且 `jhpt_update_time` 查 2024 时间戳返回 `total=0`——即预览接口根本取不到历史明细。

## 3. 尝试过的脚本（已整理进 `B_get_data_failure.py`）

| 阶段 | 脚本作用 | 结果 |
|---|---|---|
| 阶段一 反爬绕过 | `login_save_state` / `dump_api_full` / `explore_download*` / `find_download` / `try_download` | 过了瑞数、拿到接口元数据，确认只有 3 个参数、无下载直链 |
| 阶段二 主爬虫 | `crawl_road_index`（offset 分页 + 退避 + 断点续传） | 爬到 offset≈69000 撞上翻页上限 |
| 阶段三 失败定位 | `probe_offset` / `probe_max` / `test_2024` / `wait_and_crawl` | 确认是预览通道翻页上限，非限流 |

> 原始脚本仍保留在项目根目录：`crawl_road_index.py`、`probe_offset.py`、`probe_max.py`、`test_2024.py`、`wait_and_crawl.py`、`login_save_state.py`、`explore_download.py`、`explore_download2.py`、`find_download.py`、`try_download.py`、`dump_api_full.py`、`inspect_interface.py`。

## 4. 结论与正确出路

1. **预览接口拿不到 2024 历史数据**，翻页/过滤都行不通，别再试 offset 翻页；
2. 该数据集是**有条件开放**：在平台 `data.sh.gov.cn` 数据集详情页提交申请（用途填「科学研究」即可，开放条件明确允许），审批通过后走**文件下载**（全量约 24 GB，481,186,153 行，time_range 2020-11-06 ~ 2025-09-11）或全量接口。

## 5. 项目最终是怎么解决的

本项目在放弃这条政府 API 爬取后（反爬强、预览通道拿不到历史数据），没有继续申请有条件开放，而是**整体改用 GitHub 上的开源项目 [MetroFlow](https://github.com/Ariza-Sun/MetroFlow)**（地铁客流数据集，GitHub + figshare，MIT License）作为数据来源，直接下载，合规、无反爬、无 token 问题。

## 附：关键依据

- 接口地址：`POST https://data.sh.gov.cn/interface/2159/66591`（header `content-type: application/json` + `token`，无需登录，但只是预览通道）
- 数据集详情页：`https://data.sh.gov.cn/view/detail/index.html?a=traffic&type=jk&id=2159`
- 实测日志：`probe_offset.log`（offset=0 成功 / offset=69000 返回 999999）
- 数据规模：约 24 GB，481,186,153 行，时间范围 2020-11-06 ~ 2025-09-11
