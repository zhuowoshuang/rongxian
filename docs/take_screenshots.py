"""自动截取系统页面截图"""
import os
from playwright.sync_api import sync_playwright

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

BASE_URL = "http://localhost:3000"

def take_screenshots():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            color_scheme="dark"
        )
        page = context.new_page()

        # 登录
        print("正在登录...")
        page.goto(f"{BASE_URL}")
        page.wait_for_timeout(2000)

        # 填写登录表单
        page.fill('input[placeholder*="用户名"], input[type="text"]', "admin")
        page.fill('input[type="password"]', "admin")
        page.click('button[type="submit"]')
        page.wait_for_timeout(3000)

        # 截取各个页面
        pages_to_capture = [
            ("dashboard", "/dashboard", "策略总览"),
            ("signals", "/signals", "信号中心"),
            ("stock-detail", "/stocks/000001", "股票分析"),
            ("pools", "/pools", "股票池"),
            ("backtest", "/backtest", "回测中心"),
            ("reports", "/reports", "报告中心"),
        ]

        for filename, path, name in pages_to_capture:
            print(f"正在截取: {name}...")
            page.goto(f"{BASE_URL}{path}")
            page.wait_for_timeout(3000)

            # 滚动页面以加载所有内容
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(500)

            # 截图
            filepath = os.path.join(SCREENSHOTS_DIR, f"{filename}.png")
            page.screenshot(path=filepath, full_page=True)
            print(f"  已保存: {filepath}")

        browser.close()
        print("\n截图完成！")

if __name__ == "__main__":
    take_screenshots()
