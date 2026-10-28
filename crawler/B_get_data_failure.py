import requests
import json
import time
import datetime
import os
import pandas as pd

# ================= 配置区 =================
URL = "https://data.sh.gov.cn/interface/2153/74739?eWocP5eA=0.lLTmAlqWkDf3BaUudYAst4siGvn1gHjvbstJDfjno2RxJoCb2kQsP_8YnL2hQnrHjgAJz0YBnq8_4LtQAIUZIFDhE1F3Mc_lhfQeAn5jNMAhVTnhYCOxa"
TOKEN = "bb161423eea955449b482f35ea958abf"

headers = {
    "token": TOKEN,
    "Content-Type": "application/json"
}

# 1. 车站列表 (先测试几个，记得去 Excel 里复制完整格式)
STATION_LIST = [
    "1836:昌邑路",
    "247:陆家嘴",
    "123:人民广场",
    "1701:虹桥火车站"
]

# 2. 日期范围 (⚠️ 已修改为 2023 年测试，确认能抓到后，您可以再尝试改成其他年份)
START_DATE = datetime.date(2023, 10, 1)
END_DATE = datetime.date(2023, 10, 5)

OUTPUT_FILE = "shanghai_metro_test.csv"


# ==========================================


def get_date_range(start, end):
    current = start
    while current <= end:
        yield current.strftime("%Y%m%d")
        current += datetime.timedelta(days=1)


def crawl_station_data(station_name):
    station_data = []
    total_days = (END_DATE - START_DATE).days + 1
    current_day_index = 0

    for date_str in get_date_range(START_DATE, END_DATE):
        current_day_index += 1
        print(f"\r  [{current_day_index}/{total_days}] 查询: {date_str} ...", end="", flush=True)

        offset = 0
        limit = 100

        while True:
            payload = {
                "transactiondate": date_str,
                "staname": station_name,
                "offset": offset,
                "limit": limit
            }

            # 👇 新增：增加重试机制，防止网络被掐断
            max_retries = 3
            success = False
            for attempt in range(max_retries):
                try:
                    response = requests.post(URL, headers=headers, json=payload, timeout=15)

                    # 如果被防火墙拦截，会返回非200状态码
                    if response.status_code != 200:
                        time.sleep(3)
                        continue

                    data = response.json()
                    success = True
                    break  # 请求成功，跳出重试循环

                except requests.exceptions.RequestException as e:
                    print(f"\n    [网络波动] 第 {attempt + 1} 次重试...")
                    time.sleep(2)  # 休息2秒后重试

            # 如果3次重试都失败了，跳过这一页
            if not success:
                print(f"\n    [跳过] 日期 {date_str} 请求失败。")
                break

            # 如果接口报错（非000000），跳出当前页循环
            if data.get("code") != "000000":
                break

            inner_data_str = data.get("data")
            if not inner_data_str:
                break

            inner_data = json.loads(inner_data_str)
            records = inner_data.get("data", [])

            if not records:
                break

            print(f"\n    🎉 发现数据！日期:{date_str}, 数量:{len(records)}条")
            station_data.extend(records)

            if len(records) < limit:
                break

            offset += limit
            time.sleep(1.5)  # 👈 核心修改：延长休息时间，避免被封

    print()
    return station_data


# ================= 主程序 =================
if __name__ == "__main__":
    print(f"开始测试爬取，共 {len(STATION_LIST)} 个车站。")

    # 为了干净，每次测试删掉旧文件 (如果是正式全量爬取，请注释掉这行)
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)

    for station in STATION_LIST:
        print(f"\n>>> 正在抓取: {station}")
        records = crawl_station_data(station)

        if records:
            print(f"   ✅ 成功获取 {len(records)} 条数据，保存中...")
            df = pd.DataFrame(records)
            header = not os.path.exists(OUTPUT_FILE)
            df.to_csv(OUTPUT_FILE, mode='a', header=header, index=False, encoding='utf-8-sig')
        else:
            print("   ⚠️ 未发现任何数据。")

    print("\n🎉 测试结束！如果这次成功，请继续添加车站和扩大日期范围。")

