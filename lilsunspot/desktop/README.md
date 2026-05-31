# Lilsunspot Desktop

React + Tauri desktop skeleton for `lilsunspot` / `小黑子`.

## Start

From `lilsunspot/desktop`:

```powershell
npm install
npm run dev
```

In another terminal, start the daemon from the repository root:

```powershell
python -m lilsunspot.daemon.app
```

The app expects `lilsunspotd` at `http://127.0.0.1:8765`.

## Pages

- 首页
- Provider
- Chat
- Mode
- Weixin
- Safety
- Doctor

These pages are placeholders. Provider checks and chat do not call real model services.

## Protected APIs

`/health` is public. All other daemon APIs require `X-Lilsunspot-Token`.

Tauri command `read_runtime_token` tries to read `runtime-token.json` from the lilsunspot data directory. Browser dev mode can still use manual token entry.

## Build

```powershell
npm run build
```

Tauri packaging remains a future task:

```powershell
npm run tauri:build
```
