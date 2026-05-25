# Lilsunspot Desktop

Day1 desktop shell for `lilsunspot` / `小黑子`.

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

Open the Vite URL and click `Health 检查`.

## Protected APIs

`/providers`, `/runtime/info`, and `/doctor/run` require `X-Lilsunspot-Token`.
Day1 does not auto-read `runtime-token.json`; paste the token into the field.

## Build

```powershell
npm run build
```

This verifies the React/Vite frontend. Tauri packaging uses:

```powershell
npm run tauri:build
```

Rust is required for Tauri packaging.
