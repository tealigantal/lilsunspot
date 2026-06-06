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
python -m lilsunspot.daemon.launcher
```

The app auto-discovers `lilsunspotd` from the local `daemon-runtime.json` file and falls back to `http://127.0.0.1:8765`.

## Pages

- 首页
- Provider
- Chat
- Mode
- Weixin
- Safety
- Doctor

Provider checks and chat use the local daemon. Weixin real login/send and Doctor repair are still placeholder flows; Safety approvals have the minimum pending/history API but the desktop page still shows JSON.

## Protected APIs

`/health` is public. All other daemon APIs require `X-Lilsunspot-Token`.

Tauri command `discover_daemon` reads `daemon-runtime.json` and `runtime-token.json` from the lilsunspot data directory. Browser dev mode can still use manual token entry.

## Build

```powershell
npm run build
```

Tauri packaging uses a bundled `lilsunspotd` sidecar for Windows. From the repository root:

```powershell
pwsh scripts/build_lilsunspotd_sidecar.ps1
npm run tauri:build --prefix lilsunspot/desktop -- --bundles nsis
```

The NSIS installer is written under `src-tauri/target/release/bundle/nsis/`. Do not use `targets: all` for the Windows build path; MSI/WiX is not part of the current minimum installer loop.
