import time
import re
import json
import requests
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By

def fetch_and_download_pgyer(url: str, output_path: Path):
    print(f"[*] 正在通过 Edge 访问蒲公英内测页面: {url} ...")
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    driver = webdriver.Edge(options=options)

    try:
        driver.get(url)
        time.sleep(3)
        print(f"[*] 页面标题: {driver.title}")

        source = driver.page_source
        cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
        user_agent = driver.execute_script("return navigator.userAgent;")

        # 从页面提取关键变量
        # 常见字段: _api_key, appKey, aKey, appBuildVersion 等
        akey_match = re.search(r'["\']aKey["\']\s*:\s*["\']([a-zA-Z0-9]+)["\']', source)
        app_key_match = re.search(r'["\']appKey["\']\s*:\s*["\']([a-zA-Z0-9]+)["\']', source)
        
        akey = akey_match.group(1) if akey_match else ""
        app_key = app_key_match.group(1) if app_key_match else ""
        print(f"[*] 提取参数: aKey={akey}, appKey={app_key}")

        # 尝试通过接口获取直链
        download_url = None

        # 方式 1: 蒲公英标准下载接口 /app/install /app/getInstallUrl
        api_headers = {
            "User-Agent": user_agent,
            "Referer": url,
            "X-Requested-With": "XMLHttpRequest"
        }

        # 尝试点击安装按钮，捕捉网络跳转
        install_btn = None
        for sel in ["#install_btn", ".btn-install", "a.install", "button"]:
            btns = driver.find_elements(By.CSS_SELECTOR, sel)
            for b in btns:
                if "安装" in b.text or "下载" in b.text:
                    install_btn = b
                    break
            if install_btn:
                break

        if install_btn:
            print(f"[*] 找到安装按钮: {install_btn.text}，触发点击...")
            install_btn.click()
            time.sleep(3)

        # 检查是否有下载链接注入
        for link in driver.find_elements(By.TAG_NAME, "a"):
            href = link.get_attribute("href") or ""
            if ".apk" in href.lower() or "download" in href.lower() or "app/install" in href.lower():
                download_url = href
                print(f"[*] 找到候选下载链接: {download_url}")
                break

        # 方式 2: 如果前端未直接跳转，直接请求蒲公英 app/install/<aKey>
        if not download_url and akey:
            test_url = f"https://www.pgyer.com/app/install/{akey}"
            print(f"[*] 尝试蒲公英直链下载地址: {test_url}")
            download_url = test_url

        if not download_url:
            print("[-] 未能自动提取到直链，检查页面内容...")
            return False

        print(f"[*] 开始下载 APK 目标文件 -> {output_path} ...")
        resp = requests.get(download_url, headers=api_headers, cookies=cookies, stream=True, allow_redirects=True, timeout=60)
        
        # 检查是否为 apk 流
        content_type = resp.headers.get("Content-Type", "")
        print(f"[*] HTTP Status: {resp.status_code}, Content-Type: {content_type}, Final URL: {resp.url}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        total_size = int(resp.headers.get("content-length", 0))
        downloaded = 0

        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 64):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = int(downloaded / total_size * 100)
                        print(f"\r下载进度: {percent}% ({downloaded // 1024} KB / {total_size // 1024} KB)", end="")

        print(f"\n[+] 下载完成！保存至: {output_path} (文件大小: {output_path.stat().st_size} 字节)")
        return True

    finally:
        driver.quit()

if __name__ == "__main__":
    target_apk = Path(r"f:\Autotest\apps\xianghe_workbench.apk")
    fetch_and_download_pgyer("https://www.pgyer.com/o1Ss", target_apk)
