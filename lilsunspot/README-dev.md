# lilsunspot Day2 开发说明

产品名：`lilsunspot`
中文昵称：`小黑子`
daemon：`lilsunspotd`

## Day2 当前能力

- `lilsunspotd` 默认只监听 `127.0.0.1:8765`。
- `/health` 无需 token，其他业务 API 均要求 `X-Lilsunspot-Token`。
- token 自动生成到 `%LOCALAPPDATA%/Lilsunspot/data/runtime-token.json`。
- 用户数据目录为 `%LOCALAPPDATA%/Lilsunspot/data`。
- Hermes 兼容目录为 `%LOCALAPPDATA%/Lilsunspot/data/hermes_home`。
- Provider registry 来自 `lilsunspot/resources/provider_registry.yaml`。
- 支持 provider 列表、详情、key URL、格式初检、mockable 联网测试、保存和 current 状态读取。
- `/providers/save` 只写入 lilsunspot 的 `hermes_home/.env` 与 `hermes_home/config.yaml`，不读取、不迁移、不污染用户 `~/.hermes/.env`。
- 日志和 API 响应会脱敏 API key。
- desktop 是 Day2 开发骨架：Health、Providers、Runtime Info、Doctor、Provider 保存表单。

## 启动 daemon

从仓库根目录运行：

```powershell
python -m lilsunspot.daemon.app
```

也可以直接用 uvicorn：

```powershell
uvicorn lilsunspot.daemon.app:app --host 127.0.0.1 --port 8765
```

## 获取 runtime token

```powershell
Get-Content "$env:LOCALAPPDATA\Lilsunspot\data\runtime-token.json"
```

只复制 JSON 里的 `token` 值。不要把真实 API Key 或完整 token 写入日志、prompt、截图、测试输出或提交记录。

## 调用 /providers

```powershell
$token = (Get-Content "$env:LOCALAPPDATA\Lilsunspot\data\runtime-token.json" | ConvertFrom-Json).token
Invoke-RestMethod "http://127.0.0.1:8765/providers" -Headers @{"X-Lilsunspot-Token"=$token}
```

无 token 或错误 token 会返回 403。

## 调用 /providers/test

该接口会用 `httpx` 做最小 provider 连接测试，不保存 key。自动化测试里必须 mock 网络请求。

```powershell
$body = @{
  provider = "deepseek"
  model = "deepseek-chat"
  api_key = "<your-api-key>"
} | ConvertTo-Json
Invoke-RestMethod "http://127.0.0.1:8765/providers/test" `
  -Method Post `
  -ContentType "application/json" `
  -Headers @{"X-Lilsunspot-Token"=$token} `
  -Body $body
```

## 调用 /providers/save

```powershell
$body = @{
  provider = "deepseek"
  model = "deepseek-chat"
  api_key = "<your-api-key>"
} | ConvertTo-Json
Invoke-RestMethod "http://127.0.0.1:8765/providers/save" `
  -Method Post `
  -ContentType "application/json" `
  -Headers @{"X-Lilsunspot-Token"=$token} `
  -Body $body
```

成功后只返回 provider、model、`env_written` 和 `config_written`，不会返回完整 key。

## 查看 hermes_home/.env

```powershell
Get-Content "$env:LOCALAPPDATA\Lilsunspot\data\hermes_home\.env"
Get-Content "$env:LOCALAPPDATA\Lilsunspot\data\hermes_home\config.yaml"
```

这些文件可能包含真实 API Key。只在本机查看，不要提交。

## 运行 pytest

```powershell
python -m pytest lilsunspot/tests
```

测试通过 `LILSUNSPOT_DATA_DIR` 使用临时目录，不依赖真实 API Key，也不会读取 `~/.hermes/.env`。

## 启动 desktop

```powershell
cd lilsunspot/desktop
npm install
npm run dev
```

另开一个终端启动 daemon，然后在页面粘贴 runtime token。构建检查：

```powershell
npm run build
```

## 不要提交 API Key

- 不要把真实 API Key 写入仓库、issue、PR、日志、prompt 或诊断包。
- provider 联网测试只作为手动可选项。
- 自动化测试必须使用 fake 值和 mock 网络。
