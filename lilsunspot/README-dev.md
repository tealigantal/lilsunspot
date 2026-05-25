# lilsunspot Day1 开发说明

产品名：`lilsunspot`
中文昵称：`小黑子`

## 当前 Day1 能力

- 新增 `lilsunspotd` FastAPI 本地 daemon。
- 默认本地地址为 `http://127.0.0.1:8765`。
- 初始化用户数据目录：`%LOCALAPPDATA%/Lilsunspot/data`。
- 初始化 Hermes 兼容目录：`%LOCALAPPDATA%/Lilsunspot/data/hermes_home`。
- 初始化日志目录：`%LOCALAPPDATA%/Lilsunspot/data/logs`。
- 首次启动或首次访问时创建 `runtime-token.json`。
- `/health` 无需 token，受保护接口需要 `X-Lilsunspot-Token`。
- `/providers` 从 `resources/provider_registry.yaml` 返回 provider 列表。
- `/providers/save` 可把 provider/model/API key 写入 lilsunspot 的 `hermes_home`，不读取或写入 `~/.hermes/.env`。
- `/doctor/run` 返回本地目录、resources、provider registry、token 和 daemon 可达性检查结果。
- 新增 Tauri 2 + React + TypeScript 桌面空壳。

## 启动 daemon

从仓库根目录运行：

```powershell
python -m lilsunspot.daemon.app
```

或：

```powershell
uvicorn lilsunspot.daemon.app:app --host 127.0.0.1 --port 8765
```

## 调用 /health

```powershell
curl http://127.0.0.1:8765/health
```

期望返回：

```json
{"ok":true}
```

## 读取 token

Windows 默认位置：

```powershell
Get-Content "$env:LOCALAPPDATA\Lilsunspot\data\runtime-token.json"
```

不要把 token 写入日志、prompt、测试输出或提交记录。

## 调用 /providers

PowerShell 示例：

```powershell
$token = (Get-Content "$env:LOCALAPPDATA\Lilsunspot\data\runtime-token.json" | ConvertFrom-Json).token
Invoke-RestMethod "http://127.0.0.1:8765/providers" -Headers @{"X-Lilsunspot-Token"=$token}
```

## 启动 desktop

```powershell
cd lilsunspot/desktop
npm install
npm run dev
```

另开一个终端启动 daemon，然后在页面点击 `Health 检查`。受保护接口 Day1 需要手动从 `runtime-token.json` 粘贴 token。

## 运行验收

从仓库根目录运行基础验收：

```powershell
python -c "import yaml, pathlib; [print(p, 'OK') for p in ['lilsunspot/resources/provider_registry.yaml','lilsunspot/resources/default_mode_profiles.yaml','lilsunspot/resources/default_safety_policy.yaml'] if yaml.safe_load(pathlib.Path(p).read_text(encoding='utf-8')) is not None]"
python -c "from lilsunspot.daemon.app import app; print('daemon app import OK', app)"
```

验证 `/health`、token 保护和 doctor：

```powershell
python -c "import importlib,json,os,tempfile; from pathlib import Path; from fastapi.testclient import TestClient; td=tempfile.mkdtemp(prefix='lilsunspot-smoke-'); os.environ['LILSUNSPOT_DATA_DIR']=str(Path(td)/'data'); import lilsunspot.daemon.config_paths as config_paths; import lilsunspot.daemon.auth as auth; import lilsunspot.daemon.app as app_module; importlib.reload(config_paths); importlib.reload(auth); app_module=importlib.reload(app_module); client=TestClient(app_module.app); print('/health', client.get('/health').status_code, client.get('/health').json()); print('/providers no token', client.get('/providers').status_code); token=json.loads(config_paths.get_runtime_paths().token_file.read_text(encoding='utf-8'))['token']; print('/providers token', client.get('/providers', headers={auth.TOKEN_HEADER: token}).status_code); print('/doctor token', client.get('/doctor/run', headers={auth.TOKEN_HEADER: token}).status_code)"
```

测试优先使用仓库包装脚本：

```powershell
bash scripts/run_tests.sh lilsunspot/tests -q
```

如果当前 Windows/本地环境缺少 pytest 插件，或包装脚本因 shell 环境不可用而无法运行，可用本地 fallback：

```powershell
python -m pytest -o addopts='' --basetemp "$env:TEMP\lilsunspot-pytest-basetemp" lilsunspot/tests -q
```

桌面端构建：

```powershell
cd lilsunspot/desktop
npm install
npm run build
```

## 还没做

- 未做首启向导。
- 未做聊天页。
- 未做 provider 真实联网测试。
- 未做微信扫码登录和私聊接入 UI。
- 未做安装包。
- 未做自动读取 runtime token。
- 未做完整安全审批 UI。
