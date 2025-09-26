import requests
import json
import time

# 微博请求头和cookies配置
headers = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Connection": "keep-alive",
    "MWeibo-Pwa": "1",
    "Referer": "https://m.weibo.cn/p/tabbar?containerid=100803_-_recentvisit&page_type=tabbar",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
}

# 读取cookies
with open('../cookie/cookie.json', 'r') as f:
    cookies = json.load(f)
cookies = {
    "SUB": cookies['cookie_dict']['SUB'],
}


def get_supertopic_list():
    """获取关注的超话列表"""
    url = "https://m.weibo.cn/api/container/getIndex"

    # 存储所有页面的结果
    all_pages_data = {}
    page_count = 1

    # 初始参数（第一页）
    params = {
        "containerid": "100803_-_followsuper",
    }

    try:
        while True:
            print(f"正在获取第{page_count}页数据...")

            response = requests.get(url, headers=headers, cookies=cookies, params=params)

            if response.status_code != 200:
                print(f"获取第{page_count}页失败，状态码: {response.status_code}")
                break

            data = response.json()

            # 保存当前页的数据
            all_pages_data[f"第{page_count}页"] = {
                "params": params.copy(),  # 使用copy避免引用问题
                "data": data
            }

            # 检查是否有下一页
            cardlist_info = data.get('data', {}).get('cardlistInfo', {})
            since_id = cardlist_info.get('since_id')

            print(f"第{page_count}页 since_id: {since_id}")

            # 如果since_id为空，表示没有更多页面
            if not since_id:
                print("since_id为空，已到达最后一页")
                break

            # 设置下一页参数
            params = {
                "containerid": "100803_-_followsuper",
                "since_id": since_id,
            }

            page_count += 1

            # 添加延迟避免请求过快
            time.sleep(1)

    except Exception as e:
        print(f"获取超话列表失败: {e}")

    # 将结果保存为JSON文件
    if all_pages_data:
        output_filename = f"supertopic_list_{int(time.time())}.json"
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(all_pages_data, f, ensure_ascii=False, indent=2)
        print(f"数据已保存到: {output_filename}")
        print(f"共获取 {len(all_pages_data)} 页数据")
    else:
        print("未获取到任何数据")

    return all_pages_data


# 执行函数
if __name__ == "__main__":
    result = get_supertopic_list()