# -*- coding: utf-8 -*-
"""
B · 上海地面道路指数 爬取失败记录（整理版）

目标数据集: 上海市公共数据开放平台「地面道路指数」
            data.sh.gov.cn 数据集 id=2159 / 接口 2159/66591
目标时间  : 2024-01-01 ~ 2026-01-01（想取 2024 全年历史数据）
失败结论  : 反爬机制强 + 接口是「预览通道」有翻页上限（offset≈1000~5000），
            且只返回聚合行（fstr_regionid=total / *地面全路网），
            拿不到 2024 历史明细；完整数据属「有条件开放」，需申请审批后走文件下载。

本文件把当时（10/21-22）分散在多个脚本里的尝试整理成一份，按阶段分三部分：
  阶段一  反爬绕过 —— Playwright 过瑞数 + 登录拿会话，找接口/下载入口
  阶段二  主爬虫   —— offset/limit 分页（数据按时间倒序）+ 退避重试 + 断点续传
  阶段三  失败定位 —— 探测翻页上限 + 2024 时间戳验证，确认「预览通道」限制

详细失败原因与正确出路见 README_B_failure_crawler.md。
（原始的各脚本仍保留在项目根目录：crawl_road_index.py / probe_offset.py 等。）

项目最终出路：放弃该政府 API 爬取，改用 GitHub 开源项目 MetroFlow（MIT License）。
"""

import sys
import json
import time
import datetime
import os
import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ============================================================
# 通用配置
# ============================================================
URL = "https://data.sh.gov.cn/interface/2159/66591"
TOKEN = "3bc8f672e38ceae625c669bbd4eb2feb"   # 预览 token（未申请有条件开放，只是预览通道）
HEADERS = {"content-type": "application/json", "token": TOKEN}

DETAIL_PAGE = "https://data.sh.gov.cn/view/detail/index.html?a=traffic&type=jk&id=2159"
META_API = "https://data.sh.gov.cn/zq/api/data_set/2159/"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


# ============================================================
# 阶段一：反爬绕过 —— Playwright 过瑞数 + 登录拿会话
#
# 详情页有瑞数(Ruishu)反爬，直接 requests 拿不到接口元数据。
# 思路：真实浏览器(Edge)过反爬 → 登录 → 保存会话 → 用页面上下文
# fetch 数据集元数据，找接口的全部输入参数 / 文件下载入口。
# ============================================================
def stage1_login_save_state(state_file="login_state.json"):
    """打开登录页让用户手动登录，成功后把会话状态存到本地。"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="msedge", headless=False,
            args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=UA, viewport={"width": 1400, "height": 900})
        page = ctx.new_page()
        page.goto("https://data.sh.gov.cn/view/login/index.html",
                  wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)

        print(">>> 请在浏览器窗口完成登录（脚本最多等 15 分钟）<<<")
        deadline = time.time() + 15 * 60
        logged_in = False
        while time.time() < deadline:
            info = page.evaluate("""() => {
                const t = (document.body && document.body.innerText) || '';
                const url = location.href;
                return {hasUser: /退出|个人中心|我的|账号|欢迎/.test(t),
                        stillLogin: /login|register/.test(url)};
            }""")
            if info["hasUser"] and not info["stillLogin"]:
                logged_in = True
                break
            time.sleep(3)

        ctx.storage_state(path=state_file)
        print("会话已保存" if logged_in else "未确认登录，状态可能无效")
        browser.close()


def stage1_dump_interface_meta(state_file="login_state.json", out="dataset_2159_full.json"):
    """过瑞数打开详情页，用页面上下文 fetch 数据集元数据，找全部输入参数。"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="msedge", headless=False,
            args=["--disable-blink-features=AutomationControlled"])
        kw = {"user_agent": UA, "viewport": {"width": 1400, "height": 900}}
        if os.path.exists(state_file):
            kw["storage_state"] = state_file
        ctx = browser.new_context(**kw)
        page = ctx.new_page()
        print("打开详情页(过瑞数)...", flush=True)
        page.goto(DETAIL_PAGE, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(10000)

        resp = page.evaluate("(u) => fetch(u).then(r => r.text())", META_API)
        with open(out, "w", encoding="utf-8") as f:
            f.write(resp)

        # 从这里确认：接口只有 3 个输入参数 jhpt_update_time / offset / limit，
        # 且没有日期范围、没有区域过滤字段（这是后来翻页方案走不通的前提）。
        d = json.loads(resp)
        api = d.get("data", {}).get("api", [])
        for a in api:
            print(json.dumps(a, ensure_ascii=False, indent=2)[:2000], flush=True)
        browser.close()


# ============================================================
# 阶段二：主爬虫 —— offset/limit 分页
#
# 接口参数只有 3 个：jhpt_update_time(精确到秒等值匹配) / offset / limit，
# 没有日期范围、没有区域过滤。只能靠 offset 翻页（数据按 living_time 倒序）
# + 客户端按时间窗口过滤出 2024 数据。
# ============================================================
LIMIT = 100
SLEEP = 25.0        # 正常请求间隔（实测 20s 稳定，15s 以下会触发限流）
BACKOFF = 180.0     # 触发限流(999999)后的退避时间
MAX_RETRY = 12

UTC_OFFSET = datetime.timedelta(hours=8)
START_BJ = datetime.datetime(2024, 1, 1, 0, 0, 0)
END_BJ = datetime.datetime(2025, 1, 1, 0, 0, 0)
START_UTC = (START_BJ - UTC_OFFSET).replace(tzinfo=datetime.timezone.utc)
END_UTC = (END_BJ - UTC_OFFSET).replace(tzinfo=datetime.timezone.utc)


def parse_dt(s):
    """解析 '2026-06-04T15:50:00.000+00:00' 为 aware datetime(UTC)"""
    if not s:
        return None
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.datetime.fromisoformat(s)
    except Exception:
        return None


def fetch(offset):
    """请求一页；code != 000000 视为失败。"""
    r = requests.post(URL, headers=HEADERS, json={"offset": offset, "limit": LIMIT}, timeout=30)
    r.raise_for_status()
    d = r.json()
    if d.get("code") != "000000":
        raise RuntimeError(f"code={d.get('code')} message={d.get('message')}")
    inner = d.get("data")
    if isinstance(inner, str):
        inner = json.loads(inner)
    if not isinstance(inner, dict):
        return []
    return inner.get("data") or []


def fetch_retry(offset):
    """带退避重试的 fetch"""
    last = None
    for i in range(MAX_RETRY):
        try:
            return fetch(offset)
        except Exception as e:
            last = e
            wait = BACKOFF if "999999" in str(e) else 15.0
            print(f"[重试 {i + 1}/{MAX_RETRY}] offset={offset} {str(e)[:60]} 等 {wait:.0f}s", flush=True)
            time.sleep(wait)
    raise last


def stage2_crawl(output="上海地面道路指数_2024.csv"):
    """offset 从 69000 往前翻，按 living_time 落在 [2024, 2025) 过滤写 CSV。"""
    offset = 69000           # 硬编码起始（约 2025-01-01 边界之前；数据约 139 条/天）
    collected = 0
    empty_pages = 0
    with open(output, "a", encoding="utf-8-sig", newline="") as f:
        while True:
            rows = fetch_retry(offset)   # ← 关键失败点：offset 过大时这里持续抛 999999
            if not rows:
                empty_pages += 1
                if empty_pages >= 3:
                    print("连续多页为空，判定到数据末尾", flush=True)
                    break
                offset += LIMIT
                time.sleep(SLEEP)
                continue
            empty_pages = 0
            stop = False
            for rec in rows:
                lt = parse_dt(rec.get("living_time"))
                if lt is None:
                    continue
                if lt < START_UTC:
                    stop = True
                    break
                if lt < END_UTC:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    collected += 1
            if stop:
                print("已越过 2024 起点，结束", flush=True)
                break
            offset += LIMIT
            time.sleep(SLEEP)
    print(f"累计 {collected} 条", flush=True)


# ============================================================
# 阶段三：失败定位 —— 探测翻页上限 + 2024 时间戳验证
#
# 现象：offset 爬到约 69000 时持续返回 code=999999。
# 用「冷却足够久后，把大 offset 放第一个请求」做对照实验：
#   大 offset 作为首个请求仍 999999、而 offset=0 能成功
#   → 说明是「翻页上限」，不是限流。
# ============================================================
def probe_one(offset, limit=100):
    r = requests.post(URL, headers=HEADERS, json={"offset": offset, "limit": limit}, timeout=40)
    d = r.json()
    data = d.get("data")
    if isinstance(data, str):
        data = json.loads(data)
    rows = data.get("data") if isinstance(data, dict) else None
    n = len(rows) if isinstance(rows, list) else 0
    t0 = rows[0].get("living_time") if n else None
    t1 = rows[-1].get("living_time") if n else None
    print(f"offset={offset:>6} code={d.get('code')} msg={d.get('message')} "
          f"rows={n} 首={t0} 末={t1}", flush=True)
    return d.get("code")


def stage3_probe_pagination_limit():
    """对照实验。实测结果（probe_offset.log）：

      offset=69000 limit=100 -> code=999999 "获取数据资源异常"（首个请求也 999999）
      offset=0     limit=1   -> code=000000 成功，返回 *地面全路网 聚合行
      offset=69000 limit=100 -> code=999999（复测仍失败）

    结论：offset 有翻页上限（约 1000~5000），不是限流。
    """
    for off in [69000, 50000, 20000, 10000, 5000, 1000, 0]:
        probe_one(off)
        time.sleep(20)


def stage3_test_2024_timestamp():
    """验证 jhpt_update_time 能否直接点到 2024 数据（结论：不能）。"""
    for ts in ["2024-01-01 00:00:00", "2024-06-01 12:00:00", "2024-06-01"]:
        r = requests.post(URL, headers=HEADERS,
                          json={"jhpt_update_time": ts, "offset": 0, "limit": 10}, timeout=40)
        d = r.json()
        data = d.get("data")
        if isinstance(data, str):
            data = json.loads(data)
        total = data.get("total") if isinstance(data, dict) else None
        print(f"jhpt_update_time={ts!r} code={d.get('code')} total={total}", flush=True)
        # 实测：2024 时间戳 total=0，即预览通道拿不到历史数据。


if __name__ == "__main__":
    # 三个阶段的入口（需哪个开哪个）：
    # stage1_login_save_state()
    # stage1_dump_interface_meta()
    # stage2_crawl()
    # stage3_probe_pagination_limit()
    # stage3_test_2024_timestamp()
    print("本文件是失败记录整理版，入口已注释，见 README_B_failure_crawler.md。")
