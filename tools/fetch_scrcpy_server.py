# -*- coding: utf-8 -*-
"""
下载并校验投屏推流所需的 scrcpy-server（固定版本，SHA256 来自 GitHub Release 资产摘要）

用法：python tools/fetch_scrcpy_server.py
已存在且校验通过则跳过；校验失败会删除文件并报错。scrcpy 以 Apache-2.0 协议发布。
"""
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.scrcpy_stream import SCRCPY_VERSION, SERVER_LOCAL  # noqa: E402

EXPECTED_SHA256 = {
    "5.0.1": "764eb6f79811d5211fe9df341120882ba9994c7a61b897d7bf3fb662e53bc536",
}
URL = f"https://github.com/Genymobile/scrcpy/releases/download/v{SCRCPY_VERSION}/scrcpy-server-v{SCRCPY_VERSION}"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    expected = EXPECTED_SHA256.get(SCRCPY_VERSION)
    if not expected:
        print(f"未登记 scrcpy-server v{SCRCPY_VERSION} 的 SHA256，拒绝下载")
        return 1
    if SERVER_LOCAL.exists() and sha256_of(SERVER_LOCAL) == expected:
        print(f"已存在且校验通过: {SERVER_LOCAL}")
        return 0
    SERVER_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    print(f"下载 {URL}")
    with urllib.request.urlopen(URL, timeout=60) as resp:
        SERVER_LOCAL.write_bytes(resp.read())
    actual = sha256_of(SERVER_LOCAL)
    if actual != expected:
        SERVER_LOCAL.unlink()
        print(f"SHA256 校验失败，已删除下载文件：期望 {expected}，实际 {actual}")
        return 1
    print(f"下载并校验通过: {SERVER_LOCAL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
