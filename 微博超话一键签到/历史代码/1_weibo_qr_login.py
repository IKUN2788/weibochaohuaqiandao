#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微博二维码登录工具 - 使用Selenium获取真实二维码
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
import re
from urllib.parse import urljoin, urlparse
import base64

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

class WeiboQRLoginApp:
    def __init__(self, root):
        self.root = root
        self.root.title("微博二维码登录工具")
        self.root.geometry("900x700")
        self.root.resizable(True, True)
        
        # 初始化变量
        self.session = requests.Session()
        self.driver = None
        self.qr_code_image = None
        self.login_success = False
        self.cookies = {}
        self.cookie_file = os.path.join("cookie", "cookie.json")
        self.qr_check_thread = None
        self.qr_check_running = False
        
        # 设置请求头
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
            self.log_message("警告: 未安装selenium，将使用简化模式")
    
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
        title_label = ttk.Label(main_frame, text="微博二维码登录工具", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # 左侧控制面板
        control_frame = ttk.LabelFrame(main_frame, text="控制面板", padding="10")
        control_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        # 登录按钮
        self.login_btn = ttk.Button(control_frame, text="获取登录二维码", command=self.get_qr_code)
        self.login_btn.grid(row=0, column=0, pady=5, sticky=(tk.W, tk.E))
        
        # 停止监控按钮
        self.stop_btn = ttk.Button(control_frame, text="停止监控", command=self.stop_qr_check, state="disabled")
        self.stop_btn.grid(row=1, column=0, pady=5, sticky=(tk.W, tk.E))
        
        # 手动检查按钮
        self.check_btn = ttk.Button(control_frame, text="手动检查登录", command=self.manual_check_login, state="disabled")
        self.check_btn.grid(row=2, column=0, pady=5, sticky=(tk.W, tk.E))
        
        # 获取超话按钮已移除
        
        # 清除cookies按钮
        self.clear_cookies_btn = ttk.Button(control_frame, text="清除Cookies", command=self.clear_cookies)
        self.clear_cookies_btn.grid(row=4, column=0, pady=5, sticky=(tk.W, tk.E))
        
        # 状态标签
        self.status_label = ttk.Label(control_frame, text="状态: 未登录", foreground="red")
        self.status_label.grid(row=5, column=0, pady=10)
        
        # 进度条
        self.progress = ttk.Progressbar(control_frame, mode='indeterminate')
        self.progress.grid(row=6, column=0, pady=5, sticky=(tk.W, tk.E))
        
        # 右侧二维码显示区域
        qr_frame = ttk.LabelFrame(main_frame, text="登录二维码", padding="10")
        qr_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.qr_label = ttk.Label(qr_frame, text="点击'获取登录二维码'开始\\n\\n如果没有安装selenium，\\n请手动在浏览器中打开登录页面", 
                                 anchor="center", justify="center")
        self.qr_label.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        qr_frame.columnconfigure(0, weight=1)
        qr_frame.rowconfigure(0, weight=1)
        
        # 底部日志区域
        log_frame = ttk.LabelFrame(main_frame, text="日志信息", padding="10")
        log_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, width=80)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置控制面板按钮宽度
        control_frame.columnconfigure(0, weight=1)
    
    def log_message(self, message):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
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
                        self.status_label.config(text="状态: 已加载cookies", foreground="orange")
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
                    self.root.after(0, lambda: self.status_label.config(text="状态: 登录有效", foreground="green"))
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
            chrome_options.add_argument('--headless')  # 无头模式
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
                # 尝试多种可能的二维码选择器
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
                    # 获取二维码图片
                    qr_src = qr_element.get_attribute('src')
                    if qr_src:
                        self.root.after(0, lambda: self._display_qr_from_url(qr_src))
                        self.root.after(0, lambda: self.log_message("成功获取二维码，请扫码登录"))
                        
                        # 开始监控登录状态
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
                # Base64编码的图片
                header, data = qr_url.split(',', 1)
                image_data = base64.b64decode(data)
                image = Image.open(io.BytesIO(image_data))
            else:
                # 网络图片
                response = requests.get(qr_url, timeout=10)
                image = Image.open(io.BytesIO(response.content))
            
            # 调整图片大小
            image = image.resize((250, 250), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            
            self.qr_label.config(image=photo, text="")
            self.qr_label.image = photo  # 保持引用
            
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
        max_checks = 60  # 最多检查60次（5分钟）
        
        while self.qr_check_running and check_count < max_checks:
            try:
                if self.driver:
                    # 检查当前URL是否已跳转
                    current_url = self.driver.current_url
                    if 'm.weibo.cn' in current_url and 'passport.weibo.com' not in current_url:
                        # 登录成功，获取cookies
                        cookies = self.driver.get_cookies()
                        self.cookies = {cookie['name']: cookie['value'] for cookie in cookies}
                        
                        # 更新session cookies
                        self.session.cookies.update(self.cookies)
                        
                        self.login_success = True
                        self.root.after(0, self._update_login_success)
                        self.save_cookies()
                        break
                
                check_count += 1
                time.sleep(5)  # 每5秒检查一次
                
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"监控登录状态出错: {str(e)}"))
                break
        
        if check_count >= max_checks:
            self.root.after(0, lambda: self.log_message("登录监控超时，请手动检查"))
        
        self.qr_check_running = False
        self.root.after(0, lambda: self.stop_btn.config(state="disabled"))
        
        # 关闭浏览器
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
            # 尝试访问需要登录的页面
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
        self.status_label.config(text="状态: 登录成功", foreground="green")
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
            
            self.status_label.config(text="状态: 未登录", foreground="red")
            self.log_message("已清除所有cookies")
            
        except Exception as e:
            self.log_message(f"清除cookies失败: {str(e)}")
    
    # 获取超话功能已移除
    
    # _fetch_super_topics 方法已移除
    
    # _process_super_topics 方法已移除
    
    # _display_topics 方法已移除
    
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
    app = WeiboQRLoginApp(root)
    
    # 确保程序退出时关闭浏览器
    def on_closing():
        if hasattr(app, 'qr_check_running'):
            app.qr_check_running = False
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