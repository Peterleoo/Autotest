import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);

const { ProxyAgent, fetch: undiciFetch } = require('F:/PM-product/.cache/node/corepack/v1/pnpm/11.7.0/dist/node_modules/undici');
const proxyUri = 'http://127.0.0.1:7897';
const proxyAgent = new ProxyAgent({ uri: proxyUri });
const smartFetch = (url, init = {}) => undiciFetch(url, { ...init, dispatcher: proxyAgent });

// 读取凭证
const cfg = JSON.parse(readFileSync('F:/PM-product/data/desktop-home/gemini-oauth-bridge.json', 'utf8'));
console.log('读取到账号:', cfg.email);
console.log('读取到项目:', cfg.project);

const clientId = Buffer.from('MTA3MTAwNjA2MDU5MS10bWhzc2luMmgyMWxjcmUyMzV2dG9sb2poNGc0MDNlcC5hcHBzLmdvb2dsZXVzZXJjb250ZW50LmNvbQ==', 'base64').toString('utf8');
const clientSecret = Buffer.from('R09DU1BYLUs1OEZXUjQ4NkxkTEoxbUxCOHNYQzR6NnFEQWY=', 'base64').toString('utf8');

console.log('正在刷新 Google OAuth Token...');
const refreshRes = await smartFetch('https://oauth2.googleapis.com/token', {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: new URLSearchParams({
    client_id: clientId,
    client_secret: clientSecret,
    refresh_token: cfg.tokens.refresh_token,
    grant_type: 'refresh_token'
  }).toString()
});

console.log('刷新状态:', refreshRes.status);
const tokData = await refreshRes.json();
const token = tokData.access_token;
console.log('成功获取 Fresh Token! 前20位:', token ? token.slice(0, 20) : 'None');

// 调用 Google Antigravity Code Assist 上游端点
console.log('正在向 Google Antigravity 发起推理...');
const url = 'https://cloudcode-pa.googleapis.com/v1internal:generateContent';
const envelope = {
  model: 'gemini-3.8-flash-high',
  project: cfg.project || 'aicode-consumers',
  requestType: 'agent',
  requestId: 'agent-' + crypto.randomUUID(),
  userAgent: 'antigravity',
  request: {
    contents: [
      { role: 'user', parts: [{ text: '请输出简短纯JSON: {"status":"antigravity_ok"}' }] }
    ]
  }
};

const resp = await smartFetch(url, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
    'User-Agent': 'antigravity/hub/2.24.0 darwin/arm64'
  },
  body: JSON.stringify(envelope)
});

console.log('Google Antigravity 响应状态码:', resp.status);
const resText = await resp.text();
console.log('响应内容:\n', resText.slice(0, 600));
