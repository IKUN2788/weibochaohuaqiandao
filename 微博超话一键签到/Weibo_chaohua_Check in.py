#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微博超话一键签到工具 - 完整版界面工具
整合登录和签到功能的GUI应用
作者：小庄-Python办公
"""


import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import requests
import json
import os
import time
import threading
from datetime import datetime
from PIL import Image, ImageTk
import io
import base64

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

class WeiboSupertopicApp:
    def __init__(self, root):
        self.root = root
        self.root.title("微博超话一键签到工具")
        self.root.geometry("1200x800")
        self.root.resizable(True, True)
        
        # 初始化变量
        self.session = requests.Session()
        self.driver = None
        self.login_success = False
        self.cookies = {}
        self.cookie_file = os.path.join("cookie", "cookie.json")
        self.qr_check_thread = None
        self.qr_check_running = False
        self.checkin_thread = None
        self.checkin_running = False
        self.analyzing_running = False
        
        # 签到统计变量
        self.total_topics = 0
        self.checked_in_before = 0
        self.newly_checked_in = 0
        self.failed_checkin = 0
        
        # 设置请求头
        self.headers = {
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
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        self.setup_ui()
        self.load_existing_cookies()
        
        # 检查selenium是否可用
        if not SELENIUM_AVAILABLE:
            self.log_message("警告: 未安装selenium，将使用简化登录模式")
    
    def setup_ui(self):
        """设置用户界面"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # 标题
        title_label = ttk.Label(main_frame, text="微博超话一键签到工具", font=("Arial", 18, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # 左侧控制面板
        control_frame = ttk.LabelFrame(main_frame, text="控制面板", padding="10")
        control_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        # 登录相关按钮
        login_section = ttk.LabelFrame(control_frame, text="登录管理", padding="5")
        login_section.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.login_btn = ttk.Button(login_section, text="获取登录二维码", command=self.get_qr_code)
        self.login_btn.grid(row=0, column=0, pady=2, sticky=(tk.W, tk.E))
        
        self.stop_btn = ttk.Button(login_section, text="停止监控", command=self.stop_qr_check, state="disabled")
        self.stop_btn.grid(row=1, column=0, pady=2, sticky=(tk.W, tk.E))
        
        self.check_btn = ttk.Button(login_section, text="手动检查登录", command=self.manual_check_login, state="disabled")
        self.check_btn.grid(row=2, column=0, pady=2, sticky=(tk.W, tk.E))
        
        self.clear_cookies_btn = ttk.Button(login_section, text="清除Cookies", command=self.clear_cookies)
        self.clear_cookies_btn.grid(row=3, column=0, pady=2, sticky=(tk.W, tk.E))
        
        # 签到相关按钮
        checkin_section = ttk.LabelFrame(control_frame, text="签到管理", padding="5")
        checkin_section.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.auto_checkin_btn = ttk.Button(checkin_section, text="一键自动签到", command=self.start_auto_checkin)
        self.auto_checkin_btn.grid(row=0, column=0, pady=2, sticky=(tk.W, tk.E))
        
        self.analyze_btn = ttk.Button(checkin_section, text="分析签到状态", command=self.analyze_supertopic_status)
        self.analyze_btn.grid(row=1, column=0, pady=2, sticky=(tk.W, tk.E))
        
        self.stop_checkin_btn = ttk.Button(checkin_section, text="停止签到", command=self.stop_checkin, state="disabled")
        self.stop_checkin_btn.grid(row=2, column=0, pady=2, sticky=(tk.W, tk.E))
        
        # 状态显示
        status_section = ttk.LabelFrame(control_frame, text="状态信息", padding="5")
        status_section.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.login_status_label = ttk.Label(status_section, text="登录状态: 未登录", foreground="red")
        self.login_status_label.grid(row=0, column=0, pady=2)
        
        self.checkin_status_label = ttk.Label(status_section, text="签到状态: 待开始", foreground="blue")
        self.checkin_status_label.grid(row=1, column=0, pady=2)
        
        # 统计信息
        stats_section = ttk.LabelFrame(control_frame, text="签到统计", padding="5")
        stats_section.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.stats_text = tk.Text(stats_section, height=6, width=25, font=("Consolas", 9))
        self.stats_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.update_stats_display()
        
        # 进度条
        self.progress = ttk.Progressbar(control_frame, mode='indeterminate')
        self.progress.grid(row=4, column=0, pady=5, sticky=(tk.W, tk.E))
        
        # 右侧显示区域
        display_frame = ttk.LabelFrame(main_frame, text="显示区域", padding="10")
        display_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        display_frame.columnconfigure(0, weight=1)
        display_frame.rowconfigure(0, weight=1)
        
        # 创建Notebook用于切换显示内容
        self.notebook = ttk.Notebook(display_frame)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 二维码显示页面
        qr_frame = ttk.Frame(self.notebook)
        self.notebook.add(qr_frame, text="登录二维码")
        
        self.qr_label = ttk.Label(qr_frame, text="点击'获取登录二维码'开始\\n\\n如果没有安装selenium，\\n请手动在浏览器中打开登录页面", 
                                 anchor="center", justify="center")
        self.qr_label.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        qr_frame.columnconfigure(0, weight=1)
        qr_frame.rowconfigure(0, weight=1)
        
        # 超话列表显示页面
        topics_frame = ttk.Frame(self.notebook)
        self.notebook.add(topics_frame, text="超话列表")
        
        # 创建Treeview显示超话信息
        columns = ("name", "status", "level", "action")
        self.topics_tree = ttk.Treeview(topics_frame, columns=columns, show="headings", height=15)
        
        self.topics_tree.heading("name", text="超话名称")
        self.topics_tree.heading("status", text="签到状态")
        self.topics_tree.heading("level", text="等级信息")
        self.topics_tree.heading("action", text="操作结果")
        
        self.topics_tree.column("name", width=200)
        self.topics_tree.column("status", width=100, anchor="center")
        self.topics_tree.column("level", width=150, anchor="center")
        self.topics_tree.column("action", width=100, anchor="center")
        
        # 添加滚动条
        topics_scrollbar = ttk.Scrollbar(topics_frame, orient="vertical", command=self.topics_tree.yview)
        self.topics_tree.configure(yscrollcommand=topics_scrollbar.set)
        
        self.topics_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        topics_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        topics_frame.columnconfigure(0, weight=1)
        topics_frame.rowconfigure(0, weight=1)
        
        # 底部日志区域
        log_frame = ttk.LabelFrame(main_frame, text="日志信息", padding="10")
        log_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, width=100)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置控制面板按钮宽度
        control_frame.columnconfigure(0, weight=1)
        login_section.columnconfigure(0, weight=1)
        checkin_section.columnconfigure(0, weight=1)
        status_section.columnconfigure(0, weight=1)
        stats_section.columnconfigure(0, weight=1)
    
    def log_message(self, message):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def update_stats_display(self):
        """更新统计信息显示"""
        stats_text = f"""总超话数量: {self.total_topics}
已签到数量: {self.checked_in_before}
新签到数量: {self.newly_checked_in}
签到失败数量: {self.failed_checkin}
签到完成率: {((self.checked_in_before + self.newly_checked_in) / max(self.total_topics, 1) * 100):.1f}%"""
        
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.insert(1.0, stats_text)
    
    def load_existing_cookies(self):
        """加载现有的cookies"""
        try:
            if os.path.exists(self.cookie_file):
                with open(self.cookie_file, 'r', encoding='utf-8') as f:
                    cookie_data = json.load(f)
                    if 'cookie_dict' in cookie_data:
                        self.cookies = cookie_data['cookie_dict']
                        self.session.cookies.update(self.cookies)
                        self.log_message("已加载现有cookies")
                        self.login_status_label.config(text="登录状态: 已加载cookies", foreground="orange")
                        # 验证cookies是否有效
                        threading.Thread(target=self.verify_cookies, daemon=True).start()
        except Exception as e:
            self.log_message(f"加载cookies失败: {str(e)}")
    
    def verify_cookies(self):
        """验证cookies是否有效"""
        try:
            test_url = "https://m.weibo.cn/api/config"
            response = self.session.get(test_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'login' in data['data'] and data['data']['login']:
                    self.login_success = True
                    self.root.after(0, lambda: self.login_status_label.config(text="登录状态: 登录有效", foreground="green"))
                    self.root.after(0, lambda: self.log_message("Cookies验证成功，已登录"))
                else:
                    self.root.after(0, lambda: self.log_message("Cookies已过期，需要重新登录"))
            else:
                self.root.after(0, lambda: self.log_message("验证cookies失败，可能需要重新登录"))
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda: self.log_message(f"验证cookies出错: {error_msg}"))
    
    def get_qr_code(self):
        """获取登录二维码"""
        self.log_message("正在获取登录二维码...")
        self.login_btn.config(state="disabled")
        self.progress.start()
        self.notebook.select(0)  # 切换到二维码页面
        
        # 在新线程中执行，避免阻塞UI
        threading.Thread(target=self._fetch_qr_code, daemon=True).start()
    
    def _fetch_qr_code(self):
        """在后台线程中获取二维码"""
        try:
            if SELENIUM_AVAILABLE:
                self._fetch_qr_with_selenium()
            else:
                self._fetch_qr_without_selenium()
                
        except Exception as e:
            self.root.after(0, lambda: self.log_message(f"获取二维码失败: {str(e)}"))
        finally:
            self.root.after(0, lambda: self.progress.stop())
            self.root.after(0, lambda: self.login_btn.config(state="normal"))
    
    def _fetch_qr_with_selenium(self):
        """使用Selenium获取二维码"""
        try:
            self.root.after(0, lambda: self.log_message("正在启动浏览器..."))
            
            # 配置Chrome选项
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            
            # 启动浏览器
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # 访问登录页面
            login_url = "https://passport.weibo.com/sso/signin?entry=wapsso&source=wapssowb&url=https%3A%2F%2Fm.weibo.cn%2Fp%2Ftabbar%3Fcontainerid%3D100803_-_recentvisit"
            self.root.after(0, lambda: self.log_message("正在访问登录页面..."))
            self.driver.get(login_url)
            
            # 等待页面加载
            time.sleep(3)
            
            # 查找二维码元素
            try:
                qr_selectors = [
                    "img[src*='qr']",
                    ".qrcode img",
                    "#qrcode img", 
                    "img[alt*='二维码']",
                    "img[alt*='QR']",
                    ".W_login_qrcode img"
                ]
                
                qr_element = None
                for selector in qr_selectors:
                    try:
                        qr_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if qr_element:
                            break
                    except:
                        continue
                
                if qr_element:
                    qr_src = qr_element.get_attribute('src')
                    if qr_src:
                        self.root.after(0, lambda: self._display_qr_from_url(qr_src))
                        self.root.after(0, lambda: self.log_message("成功获取二维码，请扫码登录"))
                        self._start_login_monitoring()
                    else:
                        self.root.after(0, lambda: self.log_message("未找到二维码图片源"))
                else:
                    self.root.after(0, lambda: self.log_message("未找到二维码元素，可能页面结构已变化"))
                    self._show_manual_login_info()
                    
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"查找二维码失败: {str(e)}"))
                self._show_manual_login_info()
                
        except Exception as e:
            self.root.after(0, lambda: self.log_message(f"启动浏览器失败: {str(e)}"))
            self._fetch_qr_without_selenium()
    
    def _fetch_qr_without_selenium(self):
        """不使用Selenium的简化模式"""
        self.root.after(0, lambda: self.log_message("使用简化模式，请手动登录"))
        self._show_manual_login_info()
    
    def _show_manual_login_info(self):
        """显示手动登录信息"""
        login_url = "https://passport.weibo.com/sso/signin?entry=wapsso&source=wapssowb&url=https%3A%2F%2Fm.weibo.cn%2Fp%2Ftabbar%3Fcontainerid%3D100803_-_recentvisit"
        info_text = f"请在浏览器中打开以下链接进行登录:\\n\\n{login_url}\\n\\n登录完成后，点击'手动检查登录'按钮"
        
        self.root.after(0, lambda: self.qr_label.config(text=info_text))
        self.root.after(0, lambda: self.check_btn.config(state="normal"))
        self.root.after(0, lambda: self.log_message("请在浏览器中完成登录"))
    
    def _display_qr_from_url(self, qr_url):
        """从URL显示二维码"""
        try:
            if qr_url.startswith('data:image'):
                header, data = qr_url.split(',', 1)
                image_data = base64.b64decode(data)
                image = Image.open(io.BytesIO(image_data))
            else:
                response = requests.get(qr_url, timeout=10)
                image = Image.open(io.BytesIO(response.content))
            
            # 调整图片大小
            image = image.resize((300, 300), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            
            self.qr_label.config(image=photo, text="")
            self.qr_label.image = photo
            
        except Exception as e:
            self.log_message(f"显示二维码失败: {str(e)}")
            self._show_manual_login_info()
    
    def _start_login_monitoring(self):
        """开始监控登录状态"""
        self.qr_check_running = True
        self.stop_btn.config(state="normal")
        self.qr_check_thread = threading.Thread(target=self._monitor_login, daemon=True)
        self.qr_check_thread.start()
    
    def _monitor_login(self):
        """监控登录状态"""
        check_count = 0
        max_checks = 60
        
        while self.qr_check_running and check_count < max_checks:
            try:
                if self.driver:
                    current_url = self.driver.current_url
                    if 'm.weibo.cn' in current_url and 'passport.weibo.com' not in current_url:
                        cookies = self.driver.get_cookies()
                        self.cookies = {cookie['name']: cookie['value'] for cookie in cookies}
                        self.session.cookies.update(self.cookies)
                        self.login_success = True
                        self.root.after(0, self._update_login_success)
                        self.save_cookies()
                        break
                
                check_count += 1
                time.sleep(5)
                
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"监控登录状态出错: {str(e)}"))
                break
        
        if check_count >= max_checks:
            self.root.after(0, lambda: self.log_message("登录监控超时，请手动检查"))
        
        self.qr_check_running = False
        self.root.after(0, lambda: self.stop_btn.config(state="disabled"))
        
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
            except:
                pass
    
    def stop_qr_check(self):
        """停止二维码检查"""
        self.qr_check_running = False
        self.stop_btn.config(state="disabled")
        self.log_message("已停止登录监控")
        
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
            except:
                pass
    
    def manual_check_login(self):
        """手动检查登录状态"""
        self.log_message("正在手动检查登录状态...")
        self.check_btn.config(state="disabled")
        threading.Thread(target=self._manual_check, daemon=True).start()
    
    def _manual_check(self):
        """手动检查登录"""
        try:
            test_url = "https://m.weibo.cn/api/config"
            response = self.session.get(test_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'login' in data['data'] and data['data']['login']:
                    self.login_success = True
                    self.cookies = dict(self.session.cookies)
                    self.root.after(0, self._update_login_success)
                    self.save_cookies()
                else:
                    self.root.after(0, lambda: self.log_message("尚未登录，请完成登录后重试"))
            else:
                self.root.after(0, lambda: self.log_message(f"检查登录状态失败: {response.status_code}"))
                
        except Exception as e:
            self.root.after(0, lambda: self.log_message(f"检查登录状态出错: {str(e)}"))
        finally:
            self.root.after(0, lambda: self.check_btn.config(state="normal"))
    
    def _update_login_success(self):
        """更新登录成功状态"""
        self.login_status_label.config(text="登录状态: 登录成功", foreground="green")
        self.check_btn.config(state="disabled")
        self.log_message("登录成功！")
    
    def save_cookies(self):
        """保存cookies到文件"""
        try:
            os.makedirs(os.path.dirname(self.cookie_file), exist_ok=True)
            
            cookie_data = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "cookie_string": "; ".join([f"{k}={v}" for k, v in self.cookies.items()]),
                "cookie_dict": self.cookies,
                "detailed_cookies": [
                    {
                        "name": name,
                        "value": value,
                        "domain": "weibo.com",
                        "path": "/",
                        "secure": True,
                        "httponly": False
                    }
                    for name, value in self.cookies.items()
                ]
            }
            
            with open(self.cookie_file, 'w', encoding='utf-8') as f:
                json.dump(cookie_data, f, indent=2, ensure_ascii=False)
            
            self.log_message("Cookies已保存到本地文件")
            
        except Exception as e:
            self.log_message(f"保存cookies失败: {str(e)}")
    
    def clear_cookies(self):
        """清除cookies"""
        try:
            self.cookies = {}
            self.session.cookies.clear()
            self.login_success = False
            
            if os.path.exists(self.cookie_file):
                os.remove(self.cookie_file)
            
            self.login_status_label.config(text="登录状态: 未登录", foreground="red")
            self.log_message("已清除所有cookies")
            
        except Exception as e:
            self.log_message(f"清除cookies失败: {str(e)}")
    
    def start_auto_checkin(self):
        """开始自动签到"""
        if not self.login_success:
            messagebox.showwarning("警告", "请先登录后再进行签到操作！")
            return
        
        self.checkin_running = True
        self.auto_checkin_btn.config(state="disabled")
        self.stop_checkin_btn.config(state="normal")
        self.checkin_status_label.config(text="签到状态: 正在签到", foreground="orange")
        self.progress.start()
        self.notebook.select(1)  # 切换到超话列表页面
        
        # 清空之前的数据
        for item in self.topics_tree.get_children():
            self.topics_tree.delete(item)
        
        # 重置统计
        self.total_topics = 0
        self.checked_in_before = 0
        self.newly_checked_in = 0
        self.failed_checkin = 0
        self.update_stats_display()
        
        self.checkin_thread = threading.Thread(target=self._auto_checkin_worker, daemon=True)
        self.checkin_thread.start()
    
    def _auto_checkin_worker(self):
        """自动签到工作线程"""
        try:
            self.root.after(0, lambda: self.log_message("=== 开始自动签到 ==="))
            
            # 获取超话列表
            data = self.get_supertopic_list()
            
            if not data:
                self.root.after(0, lambda: self.log_message("获取超话列表失败"))
                return
            
            if 'data' in data and 'cards' in data['data']:
                cards = data['data']['cards']
                
                # 处理每个超话
                for card in cards:
                    if not self.checkin_running:
                        break
                        
                    if 'card_group' in card:
                        for group_item in card['card_group']:
                            if not self.checkin_running:
                                break
                                
                            if 'title_sub' in group_item and 'buttons' in group_item:
                                self.total_topics += 1
                                topic_name = group_item['title_sub']
                                desc1 = group_item.get('desc1', '')
                                
                                # 检查按钮状态
                                can_checkin = False
                                checkin_scheme = None
                                button_status = "未知"
                                
                                for button in group_item['buttons']:
                                    if 'name' in button:
                                        button_name = button['name']
                                        if button_name == '签到':
                                            can_checkin = True
                                            checkin_scheme = button.get('scheme', '')
                                            button_status = "可签到"
                                            break
                                        elif button_name in ['已签', '已签到', '明日再来']:
                                            self.checked_in_before += 1
                                            button_status = "已签到"
                                            self.root.after(0, lambda name=topic_name: self.log_message(f"✓ {name} - 今日已签到"))
                                            break
                                
                                # 添加到树形视图
                                action_result = ""
                                if can_checkin and checkin_scheme:
                                    # 执行签到
                                    success = self.perform_checkin(topic_name, checkin_scheme)
                                    if success:
                                        self.newly_checked_in += 1
                                        action_result = "签到成功"
                                        self.root.after(0, lambda name=topic_name: self.log_message(f"✓ {name} - 签到成功"))
                                    else:
                                        self.failed_checkin += 1
                                        action_result = "签到失败"
                                        self.root.after(0, lambda name=topic_name: self.log_message(f"✗ {name} - 签到失败"))
                                    
                                    # 添加延迟
                                    time.sleep(1)
                                elif button_status == "已签到":
                                    action_result = "已签到"
                                else:
                                    action_result = "无需签到"
                                
                                # 更新UI
                                self.root.after(0, lambda name=topic_name, status=button_status, level=desc1, result=action_result: 
                                               self.topics_tree.insert("", "end", values=(name, status, level, result)))
                                self.root.after(0, self.update_stats_display)
            
            # 完成签到
            self.root.after(0, self._checkin_completed)
            
        except Exception as e:
            self.root.after(0, lambda: self.log_message(f"自动签到出错: {str(e)}"))
        finally:
            self.checkin_running = False
            self.root.after(0, lambda: self.progress.stop())
            self.root.after(0, lambda: self.auto_checkin_btn.config(state="normal"))
            self.root.after(0, lambda: self.stop_checkin_btn.config(state="disabled"))
    
    def _checkin_completed(self):
        """签到完成"""
        self.checkin_status_label.config(text="签到状态: 签到完成", foreground="green")
        completion_rate = (self.checked_in_before + self.newly_checked_in) / max(self.total_topics, 1) * 100
        
        self.log_message("=== 签到完成统计 ===")
        self.log_message(f"总共关注超话: {self.total_topics}个")
        self.log_message(f"之前已签到: {self.checked_in_before}个")
        self.log_message(f"本次新签到: {self.newly_checked_in}个")
        self.log_message(f"签到失败: {self.failed_checkin}个")
        self.log_message(f"总签到完成率: {completion_rate:.1f}%")
        
        messagebox.showinfo("签到完成", f"签到完成！\\n总超话: {self.total_topics}个\\n新签到: {self.newly_checked_in}个\\n完成率: {completion_rate:.1f}%")
    
    def stop_checkin(self):
        """停止签到"""
        self.checkin_running = False
        self.stop_checkin_btn.config(state="disabled")
        self.checkin_status_label.config(text="签到状态: 已停止", foreground="red")
        self.log_message("用户停止了签到操作")
    
    def get_supertopic_list(self):
        """获取关注的超话列表（支持完整分页）"""
        url = "https://m.weibo.cn/api/container/getIndex"
        
        # 准备cookies
        if 'SUB' in self.cookies:
            cookies = {"SUB": self.cookies['SUB']}
        else:
            self.root.after(0, lambda: self.log_message("未找到有效的SUB cookie"))
            return None
        
        all_cards = []
        page_count = 1
        
        params = {
            "containerid": "100803_-_followsuper",
        }
        
        try:
            while True:
                # 检查是否需要停止（支持签到和分析两种模式）
                if not (self.checkin_running or self.analyzing_running):
                    break
                    
                self.root.after(0, lambda p=page_count: self.log_message(f"正在获取第{p}页超话数据..."))
                
                response = requests.get(url, headers=self.headers, cookies=cookies, params=params, timeout=10)
                
                if response.status_code != 200:
                    self.root.after(0, lambda p=page_count, code=response.status_code: 
                                   self.log_message(f"获取第{p}页失败，状态码: {code}"))
                    break
                
                data = response.json()
                
                if data.get('ok') != 1:
                    self.root.after(0, lambda p=page_count, msg=data.get('msg', '未知错误'): 
                                   self.log_message(f"第{p}页获取失败: {msg}"))
                    break
                
                if 'data' in data and 'cards' in data['data']:
                    current_cards = data['data']['cards']
                    all_cards.extend(current_cards)
                    self.root.after(0, lambda p=page_count, count=len(current_cards): 
                                   self.log_message(f"第{p}页获取成功，包含{count}个卡片"))
                else:
                    self.root.after(0, lambda p=page_count: self.log_message(f"第{p}页没有cards数据"))
                    break
                
                # 检查是否有下一页
                cardlist_info = data.get('data', {}).get('cardlistInfo', {})
                since_id = cardlist_info.get('since_id')
                
                if not since_id:
                    self.root.after(0, lambda: self.log_message("since_id为空，已到达最后一页"))
                    break
                
                params = {
                    "containerid": "100803_-_followsuper",
                    "since_id": since_id,
                }
                
                page_count += 1
                time.sleep(0.5)
        
        except Exception as e:
            self.root.after(0, lambda: self.log_message(f"获取超话列表失败: {e}"))
            return None
        
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
            self.root.after(0, lambda p=page_count, count=len(all_cards): 
                           self.log_message(f"总共获取了{p}页数据，包含{count}个卡片"))
            return complete_data
        else:
            self.root.after(0, lambda: self.log_message("没有获取到任何超话数据"))
            return None
    
    def perform_checkin(self, topic_name, scheme):
        """执行单个超话签到"""
        try:
            if scheme.startswith('/api/container/button'):
                full_url = f"https://m.weibo.cn{scheme}"
                
                # 准备cookies
                if 'SUB' in self.cookies:
                    cookies = {"SUB": self.cookies['SUB']}
                else:
                    return False
                
                response = requests.get(full_url, headers=self.headers, cookies=cookies, timeout=10)
                
                if response.status_code == 200:
                    try:
                        result = response.json()
                        if result.get('ok') == 1:
                            if 'data' in result:
                                data = result['data']
                                if isinstance(data, dict) and 'msg' in data:
                                    msg = data['msg']
                                    if '成功' in msg or '签到' in msg:
                                        return True
                                    else:
                                        return False
                            return True
                        else:
                            return False
                    except json.JSONDecodeError:
                        return False
                else:
                    return False
            else:
                return False
                
        except Exception:
            return False
    
    def analyze_supertopic_status(self):
        """分析超话签到状态"""
        if not self.login_success:
            messagebox.showwarning("警告", "请先登录后再进行分析操作！")
            return
        
        self.analyzing_running = True
        self.log_message("开始分析超话签到状态...")
        self.analyze_btn.config(state="disabled")
        self.progress.start()
        self.notebook.select(1)  # 切换到超话列表页面
        
        # 清空之前的数据
        for item in self.topics_tree.get_children():
            self.topics_tree.delete(item)
        
        threading.Thread(target=self._analyze_worker, daemon=True).start()
    
    def _analyze_worker(self):
        """分析工作线程"""
        try:
            data = self.get_supertopic_list()
            
            if not data:
                self.root.after(0, lambda: self.log_message("获取超话列表失败"))
                return
            
            self.root.after(0, lambda: self.log_message("=== 超话签到状态分析 ==="))
            
            total_topics = 0
            checked_in = 0
            can_checkin = 0
            
            if 'data' in data and 'cards' in data['data']:
                cards = data['data']['cards']
                
                for card in cards:
                    if not self.analyzing_running:
                        break
                        
                    if 'card_group' in card:
                        for group_item in card['card_group']:
                            if not self.analyzing_running:
                                break
                                
                            if 'title_sub' in group_item and 'buttons' in group_item:
                                total_topics += 1
                                topic_name = group_item['title_sub']
                                desc1 = group_item.get('desc1', '')
                                
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
                                
                                # 添加到树形视图
                                self.root.after(0, lambda name=topic_name, status=button_status, level=desc1: 
                                               self.topics_tree.insert("", "end", values=(name, status, level, "分析完成")))
            
            # 更新统计
            self.total_topics = total_topics
            self.checked_in_before = checked_in
            self.newly_checked_in = 0
            self.failed_checkin = 0
            self.root.after(0, self.update_stats_display)
            
            # 显示分析结果
            completion_rate = checked_in / max(total_topics, 1) * 100
            self.root.after(0, lambda: self.log_message(f"总共关注超话: {total_topics}个"))
            self.root.after(0, lambda: self.log_message(f"今日已签到: {checked_in}个"))
            self.root.after(0, lambda: self.log_message(f"可以签到: {can_checkin}个"))
            self.root.after(0, lambda: self.log_message(f"签到完成率: {completion_rate:.1f}%"))
            
        except Exception as e:
            self.root.after(0, lambda: self.log_message(f"分析超话状态出错: {str(e)}"))
        finally:
            self.analyzing_running = False
            self.root.after(0, lambda: self.progress.stop())
            self.root.after(0, lambda: self.analyze_btn.config(state="normal"))
    
    def __del__(self):
        """析构函数，确保浏览器被关闭"""
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
            except:
                pass

def main():
    """主函数"""
    root = tk.Tk()
    app = WeiboSupertopicApp(root)
    
    # 确保程序退出时关闭浏览器
    def on_closing():
        if hasattr(app, 'qr_check_running'):
            app.qr_check_running = False
        if hasattr(app, 'checkin_running'):
            app.checkin_running = False
        if hasattr(app, 'driver') and app.driver:
            try:
                app.driver.quit()
            except:
                pass
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
