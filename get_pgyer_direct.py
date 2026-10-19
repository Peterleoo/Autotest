import os
import re
import sys
import time
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.edge.options import Options

def get_apk(shortcut: str = "9JQn"):
    url = f"https://www.pgyer.com/{shortcut}"
    print(f"[*] 访问蒲公英分发页: {url}")
    
    options = Options()
    options.add_argument("--headless=new")
    driver = webdriver.Edge(options=options)
    
    try:
        driver.get(url)
        time.sleep(3)
        print(f"[*] 标题: {driver.title}")

        html = driver.page_source
        cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
        ua = driver.execute_script("return navigator.userAgent;")
        
        soup = BeautifulSoup(html, "html.parser")
        
        # 寻找安装按钮
        btn = soup.find(id="down_load") or soup.find(class_=re.compile(r"down_load|install"))
        build_path = None
        if btn and btn.get("href"):
            build_path = btn["href"]
            print(f"[*] 找到构建路径: {build_path}")

        # 寻找 aKey
        akey_match = re.search(r"['\"]?aKey['\"]?\s*[:=]\s*['\"]([a-zA-Z0-9]+)['\"]", html)
        akey = akey_match.group(1) if akey_match else ""
        if not akey and build_path:
            parts = build_path.strip("/").split("/")
            if parts:
                akey = parts[-1]
        print(f"[*] aKey: {akey}")

        # 如果没有直接找到，抓取页面所有的 appBuild 链接
        if not akey:
            for a in soup.find_all("a"):
                href = a.get("href", "")
                if "/app/build/" in href:
                    akey = href.split("/")[-1]
                    break

        if not akey:
            print("[-] 未能解析出 aKey")
            return

        # 蒲公英请求下载直链的标准接口
        # 接口: POST https://www.pgyer.com/app/installUpdate/{aKey}
        headers = {
            "User-Agent": ua,
            "Referer": url,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
        }
        
        api_url = f"https://www.pgyer.com/app/installUpdate/{akey}"
        print(f"[*] 请求蒲公英下载直链生成接口: {api_url}")
        resp = requests.post(api_url, headers=headers, cookies=cookies, data={"aKey": akey})
        print(f"[*] API Status: {resp.status_code}")
        
        direct_url = None
        try:
            data = resp.json()
            print("[*] API Response:", data)
            if data.get("code") == 0 and "data" in data:
                direct_url = data["data"].get("downloadURL") or data["data"].get("url")
        except Exception:
            print("[*] Response Text snippet:", resp.text[:300])

        if not direct_url:
            # 备用方案：请求 https://www.pgyer.com/app/install/{akey}
            test_url = f"https://www.pgyer.com/app/install/{akey}"
            print(f"[*] 尝试备用跳转地址: {test_url}")
            r2 = requests.get(test_url, headers=headers, cookies=cookies, allow_redirects=False)
            if r2.status_code in [301, 302] and "Location" in r2.headers:
                direct_url = r2.headers["Location"]
                print(f"[+] 成功捕获重定向直链: {direct_url}")

        if direct_url:
            print(f"[+] 获取到真实 APK 下载直链！\n{direct_url}")
            output_file = Path(r"f:\Autotest\apps\xianghe_zhaofang.apk")
            print(f"[*] 开始流式下载到: {output_file} ...")
            r_download = requests.get(direct_url, stream=True, timeout=120)
            total = int(r_download.headers.get("content-length", 0))
            done = 0
            with open(output_file, "wb") as f:
                for chunk in r_download.iter_content(chunk_size=1024*128):
                    if chunk:
                        f.write(chunk)
                        done += len(chunk)
                        if total > 0:
                            sys.stdout.write(f"\r进度: {int(done/total*100)}% ({done//(1024*1024)}MB / {total//(1024*1024)}MB)")
                            sys.stdout.flush()
            print(f"\n[🎉] 下载完成！文件大小: {output_file.stat().st_size // (1024*1024)} MB")
        else:
            print("[-] 未能获取到下载直链，可能需要密码或验证码。")

    finally:
        driver.quit()

if __name__ == "__main__":
    get_apk("9JQn")
