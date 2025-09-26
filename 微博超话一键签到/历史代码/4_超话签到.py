1
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

with open('cookie/cookie.json', 'r') as f:
    cookies = json.load(f)
cookies = {
    "SUB": cookies['cookie_dict']['SUB'],
}


def get_supertopic_list():
    """获取关注的超话列表（支持完整分页）"""
    url = "https://m.weibo.cn/api/container/getIndex"
    
    # 存储所有页面的卡片数据
    all_cards = []
    page_count = 1
    
    # 初始参数（第一页）
    params = {
        "containerid": "100803_-_followsuper",
    }
    
    try:
        while True:
            print(f"正在获取第{page_count}页超话数据...")
            
            response = requests.get(url, headers=headers, cookies=cookies, params=params)
            
            if response.status_code != 200:
                print(f"获取第{page_count}页失败，状态码: {response.status_code}")
                break
            
            data = response.json()
            
            # 检查响应是否成功
            if data.get('ok') != 1:
                print(f"第{page_count}页获取失败: {data.get('msg', '未知错误')}")
                break
            
            # 获取当前页的cards数据
            if 'data' in data and 'cards' in data['data']:
                current_cards = data['data']['cards']
                all_cards.extend(current_cards)
                print(f"第{page_count}页获取成功，包含{len(current_cards)}个卡片")
            else:
                print(f"第{page_count}页没有cards数据")
                break
            
            # 检查是否有下一页 - 使用cardlistInfo中的since_id
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
            time.sleep(0.5)
    
    except Exception as e:
        print(f"获取超话列表失败: {e}")
        return None
    
    # 构造完整的响应数据
    if all_cards:
        complete_data = {
            'ok': 1,
            'data': {
                'cards': all_cards,
                'cardlistInfo': {
                    'total_pages': page_count,
                    'total_cards': len(all_cards)
                }
            }
        }
        print(f"总共获取了{page_count}页数据，包含{len(all_cards)}个卡片")
        
        # 可选：保存完整数据到文件
        try:
            output_filename = f"supertopic_complete_list_{int(time.time())}.json"
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(complete_data, f, ensure_ascii=False, indent=2)
            print(f"完整数据已保存到: {output_filename}")
        except Exception as e:
            print(f"保存文件失败: {e}")
        
        return complete_data
    else:
        print("没有获取到任何超话数据")
        return None


def auto_checkin_supertopics():
    """自动签到所有可签到的超话"""
    data = get_supertopic_list()

    if not data:
        print("获取超话列表失败")
        return

    print("=== 开始自动签到 ===\n")

    total_topics = 0
    checked_in_before = 0
    newly_checked_in = 0
    failed_checkin = 0

    if 'data' in data and 'cards' in data['data']:
        cards = data['data']['cards']

        # 查找包含超话信息的卡片
        for card in cards:
            if 'card_group' in card:
                for group_item in card['card_group']:
                    if 'title_sub' in group_item and 'buttons' in group_item:
                        total_topics += 1
                        topic_name = group_item['title_sub']

                        # 检查按钮状态
                        can_checkin = False
                        checkin_scheme = None

                        for button in group_item['buttons']:
                            if 'name' in button:
                                button_name = button['name']
                                if button_name == '签到':
                                    can_checkin = True
                                    checkin_scheme = button.get('scheme', '')
                                    break
                                elif button_name in ['已签', '已签到', '明日再来']:
                                    checked_in_before += 1
                                    print(f"✓ {topic_name} - 今日已签到")
                                    break

                        # 执行签到
                        if can_checkin and checkin_scheme:
                            success = perform_checkin(topic_name, checkin_scheme)
                            if success:
                                newly_checked_in += 1
                                print(f"✓ {topic_name} - 签到成功")
                            else:
                                failed_checkin += 1
                                print(f"✗ {topic_name} - 签到失败")

                            # 添加延迟避免请求过快
                            time.sleep(1)

    # 统计结果
    print(f"\n=== 签到完成统计 ===")
    print(f"总共关注超话: {total_topics}个")
    print(f"之前已签到: {checked_in_before}个")
    print(f"本次新签到: {newly_checked_in}个")
    print(f"签到失败: {failed_checkin}个")
    print(f"总签到完成率: {(checked_in_before + newly_checked_in) / total_topics * 100:.1f}%")


def perform_checkin(topic_name, scheme):
    """执行单个超话签到"""
    try:
        # 解析scheme获取完整的签到URL
        if scheme.startswith('/api/container/button'):
            # 构建完整URL
            full_url = f"https://m.weibo.cn{scheme}"
            print('scheme', scheme)
            print(f"签到URL: {full_url}")

            # 发送签到请求
            response = requests.get(full_url, headers=headers, cookies=cookies, timeout=10)

            if response.status_code == 200:
                try:
                    result = response.json()
                    # 检查签到结果
                    if result.get('ok') == 1:
                        # 进一步检查是否有错误信息
                        if 'data' in result:
                            data = result['data']
                            if isinstance(data, dict) and 'msg' in data:
                                msg = data['msg']
                                if '成功' in msg or '签到' in msg:
                                    return True
                                else:
                                    print(f"    签到消息: {msg}")
                                    return False
                        return True
                    else:
                        error_msg = result.get('msg', '未知错误')
                        print(f"    签到失败: {error_msg}")
                        return False
                except json.JSONDecodeError:
                    print(f"    响应解析失败: {response.text[:100]}")
                    return False
            else:
                print(f"    HTTP错误: {response.status_code}")
                return False
        else:
            print(f"    无效的签到链接格式")
            return False

    except requests.exceptions.Timeout:
        print(f"    请求超时")
        return False
    except requests.exceptions.ConnectionError:
        print(f"    网络连接错误")
        return False
    except Exception as e:
        print(f"    签到异常: {e}")
        return False


def simple_get_response():
    """简单获取响应数据（原始功能）"""
    data = get_supertopic_list()
    if data:
        print(data)
    return data


def analyze_supertopic_status():
    """分析超话签到状态"""
    data = get_supertopic_list()

    if not data:
        return

    print("=== 超话签到状态分析 ===\n")

    total_topics = 0
    checked_in = 0
    can_checkin = 0

    if 'data' in data and 'cards' in data['data']:
        cards = data['data']['cards']

        # 查找包含超话信息的卡片
        for card in cards:
            if 'card_group' in card:
                for group_item in card['card_group']:
                    if 'title_sub' in group_item and 'buttons' in group_item:
                        total_topics += 1
                        topic_name = group_item['title_sub']
                        desc1 = group_item.get('desc1', '')
                        desc2 = group_item.get('desc2', '')

                        # 分析按钮状态
                        button_status = "未知"
                        for button in group_item['buttons']:
                            if 'name' in button:
                                button_name = button['name']
                                if button_name == '签到':
                                    button_status = "可签到"
                                    can_checkin += 1
                                elif button_name == '已签到' or '已签' in button_name:
                                    button_status = "已签到"
                                    checked_in += 1
                                elif button_name == '明日再来':
                                    button_status = "今日已签到"
                                    checked_in += 1

                        # 从desc2分析签到状态
                        checkin_info = ""
                        if desc2:
                            if "签到了" in desc2:
                                checkin_info = "最近有签到记录"
                            elif "签到" in desc2:
                                checkin_info = "包含签到相关信息"

                        print(f"超话名称: {topic_name}")
                        print(f"等级信息: {desc1}")
                        print(f"按钮状态: {button_status}")
                        if checkin_info:
                            print(f"签到信息: {checkin_info}")
                        if desc2:
                            print(f"最新动态: {desc2[:100]}...")
                        print("-" * 50)

    # 统计信息
    print(f"\n=== 签到统计 ===")
    print(f"总共关注超话: {total_topics}个")
    print(f"今日已签到: {checked_in}个")
    print(f"可以签到: {can_checkin}个")
    if total_topics > 0:
        print(f"签到完成率: {checked_in / total_topics * 100:.1f}%")

    # 保存完整响应到文件
    try:
        with open('supertopic_status_response.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n完整响应已保存到 supertopic_status_response.json")
    except Exception as e:
        print(f"保存文件失败: {e}")


if __name__ == "__main__":
    print("微博超话签到工具")
    print("1. 自动签到所有可签到的超话")
    print("2. 分析超话签到状态")
    print("3. 获取原始响应数据")

    choice = input("\n请选择功能 (1/2/3，默认为1): ").strip()

    if choice == "2":
        analyze_supertopic_status()
    elif choice == "3":
        simple_get_response()
    else:
        # 默认执行自动签到
        auto_checkin_supertopics()
