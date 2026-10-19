from bs4 import BeautifulSoup
import re

with open("pgyer_dom.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

for tag in soup.find_all(["a", "button", "div", "span"]):
    txt = tag.get_text(strip=True)
    if txt in ["安装", "下载", "免费下载", "下载安装"]:
        print("BUTTON TAG:", tag.name, tag.attrs, txt)

# 搜索所有 js 里的关键字
for m in re.finditer(r"(appKey|aKey|_api_key|buildKey|shortcutUrl|fileSize|appBuildURL)\s*[:=]\s*['\"]([^'\"]+)['\"]", html):
    print("MATCH:", m.group(1), "->", m.group(2))

# 搜索所有包含 download 或 install 的链接
for a in soup.find_all("a"):
    h = a.get("href", "")
    if any(k in h for k in ["download", "install", "apk", "pgyer"]):
        print("LINK:", a.get_text(strip=True), "->", h)
