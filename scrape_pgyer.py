import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

options = Options()
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

print("正在启动浏览器访问蒲公英下载页面...")
driver = webdriver.Chrome(options=options)
try:
    driver.get("https://www.pgyer.com/o1Ss")
    time.sleep(4)
    print("当前页面标题:", driver.title)
    print("当前页面 URL:", driver.current_url)

    # 寻找下载按钮或链接
    links = driver.find_elements(By.TAG_NAME, "a")
    for a in links:
        href = a.get_attribute("href") or ""
        text = a.text
        if "download" in href.lower() or "install" in href.lower() or "安装" in text or "下载" in text:
            print(f"找到下载链接: text='{text}', href='{href}'")

    # 打印页面中的 app 信息
    page_text = driver.find_element(By.TAG_NAME, "body").text
    print("\n页面文本信息摘要:\n", page_text[:500])

    # 抓取页面源码中可能的 appKey 或下载 url
    source = driver.page_source
    import re
    app_keys = re.findall(r'appKey["\']?\s*:\s*["\']([a-zA-Z0-9]+)["\']', source)
    print("找到 appKey:", set(app_keys))
finally:
    driver.quit()
