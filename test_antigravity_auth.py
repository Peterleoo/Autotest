import json
import base64
import requests
import uuid

def test_auth():
    cfg_path = r'F:\PM-product\data\desktop-home\gemini-oauth-bridge.json'
    with open(cfg_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)

    tokens = cfg.get('tokens', {})
    access_token = tokens.get('access_token')
    refresh_token = tokens.get('refresh_token')
    project = cfg.get('project', 'aicode-consumers')

    print('读取到账号:', cfg.get('email'))
    print('读取到项目:', project)

    client_id = base64.b64decode('MTA3MTAwNjA2MDU5MS10bWhzc2luMmgyMWxjcmUyMzV2dG9sb2poNGc0MDNlcC5hcHBzLmdvb2dsZXVzZXJjb250ZW50LmNvbQ==').decode()
    client_secret = base64.b64decode('R09DU1BYLUs1OEZXUjQ4NkxkTEoxbUxCOHNYQzR6NnFEQWY=').decode()

    # 显式使用本地 7897 代理
    proxies = {
        'http': 'http://127.0.0.1:7897',
        'https': 'http://127.0.0.1:7897'
    }

    print('正在通过代理 127.0.0.1:7897 刷新 Google OAuth Token...')
    try:
        refresh_resp = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token'
            },
            proxies=proxies,
            timeout=15
        )
        print('Token 刷新状态:', refresh_resp.status_code)
        if refresh_resp.status_code == 200:
            access_token = refresh_resp.json().get('access_token')
            print('✅ 成功刷新获取最新 Access Token！')
        else:
            print('刷新响应:', refresh_resp.text)
    except Exception as e:
        print('刷新 Token 异常:', e)

    url = 'https://daily-cloudcode-pa.sandbox.googleapis.com/v1internal:generateContent'
    envelope = {
        'model': 'gemini-2.5-flash',
        'project': project,
        'requestType': 'agent',
        'requestId': f'agent-{uuid.uuid4()}',
        'userAgent': 'antigravity',
        'request': {
            'contents': [
                {'role': 'user', 'parts': [{'text': '请回复一段简短 JSON: {"status": "antigravity_ok", "msg": "hello from google antigravity"}'}]}
            ]
        }
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token}',
        'User-Agent': 'antigravity/hub/2.24.0 darwin/arm64'
    }

    print('正在向 Google Antigravity 发起模型推理请求...')
    try:
        resp = requests.post(url, headers=headers, json=envelope, proxies=proxies, timeout=20)
        print('✅ Antigravity 上游响应状态码:', resp.status_code)
        print('✅ 响应内容:\n', resp.text[:600])
    except Exception as e:
        print('请求上游异常:', e)

if __name__ == '__main__':
    test_auth()
