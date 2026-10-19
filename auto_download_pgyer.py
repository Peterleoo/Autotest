import os
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By

def download_app(pgyer_url: str):
    apps_dir = Path(r"f:\Autotest\apps")
    apps_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] 启动 Edge 自动化下载: {pgyer_url}")
    options = Options()
    # 配置自动静默下载到 f:\Autotest\apps 目录
    prefs = {
        "download.default_directory": str(apps_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": False,
        "safebrowsing.disable_download_protection": True
    }
    options.add_experimental_option("prefs", prefs)
    # 不使用无头模式以保证下载行为正常，或使用 headless
    options.add_argument("--headless=new")

    driver = webdriver.Edge(options=options)
    try:
        driver.get(pgyer_url)
        time.sleep(3)
        print(f"[*] 页面标题: {driver.title}")

        # 查找安装按钮并点击
        clicked = False
        for sel in ["#down_load", "#install_btn", ".btn-u", "a", "button"]:
            elements = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in elements:
                text = el.text.strip()
                if text in ["安装", "下载", "免费下载", "下载安装"]:
                    print(f"[*] 找到并点击下载按钮: <{el.tag_name}> {text}")
                    driver.execute_script("arguments[0].click();", el)
                    clicked = True
                    break
            if clicked:
                break

        if not clicked:
            print("[-] 未直接找到安装按钮，尝试直接导航到下载链接...")
            # 查找所有 a 标签
            for a in driver.find_elements(By.TAG_NAME, "a"):
                href = a.get_attribute("href") or ""
                if "/app/build/" in href or "download" in href:
                    print(f"[*] 直接访问下载连接: {href}")
                    driver.get(href)
                    break

        # 等待下载完成 (监控 apps 目录下的 .crdownload 或 .apk)
        print("[*] 正在等待下载完成...")
        timeout = 90
        start = time.time()
        apk_file = None

        while time.time() - start < timeout:
            time.sleep(2)
            files = list(apps_dir.glob("*"))
            # 检查是否有正在下载的临时文件
            crdownload = list(apps_dir.glob("*.crdownload"))
            apk_files = [f for f in apps_dir.glob("*.apk") if f.stat().st_size > 1024 * 1024]
            
            if crdownload:
                print(f"[*] 正在下载中... 临时文件: {crdownload[0].name}")
                continue
            
            if apk_files:
                apk_file = apk_files[-1]
                print(f"[+] 发现下载完成的 APK: {apk_file.name} (大小: {apk_file.stat().st_size // (1024*1024)} MB)")
                break

        if apk_file:
            print(f"[🎉] APK 下载成功！最终路径: {apk_file}")
            return apk_file
        else:
            print("[-] 下载等待超时，检查当前目录文件:", [f.name for f in apps_dir.glob("*")])
            return None

    finally:
        driver.quit()

if __name__ == "__main__":
    download_app("https://www.pgyer.com/9JQn")
