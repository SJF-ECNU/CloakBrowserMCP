# CloakBrowser MCP 服务设计

日期：2026-06-22

## 背景

目标是在独立仓库 `/Users/shjf/Documents/CloakBrowserMCP` 中实现一个 MCP server，让 agent 能在 Linux 无真实屏幕的环境里使用 CloakBrowser 浏览器。上游 CloakBrowser 源码已通过 graphify 调查，克隆位置为 `/Users/shjf/.graphify/repos/CloakHQ/CloakBrowser`，调查时提交为 `29679a7`。

上游提供两条可用接入边界：

1. Python API：`cloakbrowser.launch_context_async()`、`launch_async()`、`launch_persistent_context_async()`，可直接获得 Playwright Browser 或 BrowserContext。
2. CDP 服务：`cloakserve` 可在一个端口上提供 `/json/version`、`/json/list` 和 WebSocket 代理，并按 `fingerprint` seed 管理独立 Chrome 进程。

第一版不修改上游 CloakBrowser，只在本仓库实现 MCP 服务。

## 目标

构建一个 Linux 无屏幕优先的 CloakBrowser MCP server，使 agent 可以启动浏览器会话、导航网页、交互页面、读取页面状态、截图、执行简单 JavaScript，并可靠关闭资源。

## 非目标

第一版不实现以下能力：

- CAPTCHA 自动求解。
- 代理池、账号池、任务队列或调度系统。
- 完整 Playwright API 映射。
- 浏览器录制回放。
- 多 agent 协作调度。
- 上游 CloakBrowser 源码改造。

这些能力以后可以在现有边界上增量扩展。

## 运行环境

MCP 服务以 Linux server/container 为主要目标，不假设存在真实显示器。

支持三种显示模式：

1. `headless`：默认模式。使用 `headless=True`，不要求 `$DISPLAY`，资源占用最低。
2. `virtual`：Linux 无真实屏幕但需要 headed 行为时使用。通过 Xvfb 或等价虚拟显示运行 `headless=False`。
3. `cdp`：连接已有 `cloakserve` 或其他 CDP endpoint。显示模式由外部服务决定。

`headless=false` 不作为隐式默认值。只有用户显式选择 `virtual` 或 `cdp` 时，服务才进入需要虚拟显示或外部 CDP 的路径。

## 架构

MCP 服务分为四个小边界：

1. `BrowserManager`
   - 管理 session id 到浏览器会话的映射。
   - 负责创建、查找、关闭 session。
   - 负责确保异常时清理 BrowserContext、Browser 和 Playwright 连接。

2. `BrowserSession`
   - 封装单个页面操作。
   - 保存当前 Playwright page、context、backend 类型和启动参数摘要。
   - 对 MCP 工具暴露统一方法，例如 `navigate()`、`click()`、`type_text()`、`screenshot()`。

3. `DirectBackend`
   - 默认后端。
   - 使用 `cloakbrowser.launch_context_async()` 启动 context。
   - 在 `headless` 模式下传 `headless=True`。
   - 在 `virtual` 模式下确保存在 Xvfb 提供的 `$DISPLAY`，然后传 `headless=False`。

4. `CdpBackend`
   - 连接已有 CDP endpoint。
   - 使用 Playwright `chromium.connect_over_cdp()`。
   - 支持把 `cdp_url` 与 `fingerprint` 组合成 `cloakserve` URL，例如 `http://127.0.0.1:9222?fingerprint=seed1`。
   - 第一版不负责长期托管 `cloakserve` 进程，只负责连接已有服务。后续可增加 `cloakserve` 生命周期管理。

## MCP 工具

第一版只暴露必要工具面：

1. `browser_start`
   - 输入：`display_mode`、`backend`、`headless`、`proxy`、`locale`、`timezone`、`humanize`、`profile_dir`、`cdp_url`、`fingerprint`。
   - 输出：`session_id`、`backend`、`display_mode`。
   - 默认：`backend="direct"`、`display_mode="headless"`。

2. `browser_navigate`
   - 输入：`session_id`、`url`、`wait_until`。
   - 输出：最终 URL、页面标题。

3. `browser_click`
   - 输入：`session_id`、`selector`。
   - 输出：操作成功状态。

4. `browser_type`
   - 输入：`session_id`、`selector`、`text`。
   - 输出：操作成功状态。

5. `browser_evaluate`
   - 输入：`session_id`、`script`。
   - 输出：JSON 可序列化结果。

6. `browser_snapshot`
   - 输入：`session_id`。
   - 输出：标题、URL、可见文本摘要。

7. `browser_screenshot`
   - 输入：`session_id`、`full_page`。
   - 输出：截图文件路径或 base64 数据。第一版优先返回文件路径，避免 MCP 响应过大。

8. `browser_close`
   - 输入：`session_id`。
   - 输出：关闭状态。

## 数据流

`browser_start` 先由 `BrowserManager` 校验参数，再根据 `backend` 创建后端：

- `direct + headless`：调用 CloakBrowser async context API，创建 page，注册 session。
- `direct + virtual`：检查或启动 Xvfb，设置 `$DISPLAY`，用 headed context 创建 page，注册 session。
- `cdp`：拼接 CDP URL，连接远端 browser，获取或创建 context/page，注册 session。

后续页面操作工具只通过 `BrowserManager.get(session_id)` 取得 `BrowserSession`，不直接接触后端实现。

`browser_close` 必须释放当前 page/context/browser/CDP 连接。进程收到取消或关闭信号时，`BrowserManager` 关闭所有已知 session。

## 错误处理

错误信息需要对 agent 可行动：

- session 不存在：返回 `SessionNotFound`，提示可用 session 或要求重新 `browser_start`。
- Linux 无屏幕且请求 `virtual`：如果 Xvfb 不可用，返回 `VirtualDisplayUnavailable`，说明需要安装或使用带 Xvfb 的镜像。
- CDP 连接失败：返回 `CdpConnectionFailed`，包含目标 endpoint 和连接阶段。
- 页面选择器超时：返回 `ElementNotFound` 或 `ActionTimeout`，包含 selector。
- 截图失败：返回 `ScreenshotFailed`，包含 session id 和页面 URL。

不吞掉异常，不把所有错误统一成通用失败。

## 配置

第一版配置保持最小：

- `CLOAK_MCP_SCREENSHOT_DIR`：截图输出目录，默认使用系统临时目录下的 `cloakbrowser-mcp`。
- `CLOAK_MCP_DEFAULT_DISPLAY_MODE`：默认 `headless`。
- `CLOAK_MCP_DEFAULT_CDP_URL`：默认 CDP endpoint，用于 `backend="cdp"` 时省略工具参数。
- `CLOAKBROWSER_LICENSE_KEY`：透传给 CloakBrowser Pro。

代理、locale、timezone、humanize、fingerprint 通过 `browser_start` 入参传递，不做全局复杂配置。

## 测试策略

测试分三层：

1. 单元测试
   - `BrowserManager` session 创建、查找、关闭。
   - `browser_start` 参数校验。
   - `display_mode` 到后端启动参数的映射。
   - `cdp_url` 与 `fingerprint` 的拼接规则。

2. 后端 fake 测试
   - 使用 fake Playwright 对象验证 `navigate/click/type/evaluate/screenshot/close` 调用顺序。
   - 不下载真实 CloakBrowser binary。

3. Linux smoke 测试
   - `headless` 模式打开 `https://example.com`，读取标题、文本、截图、关闭。
   - `virtual` 模式在安装 Xvfb 的环境中执行同样流程。
   - `cdp` 模式连接已有 `cloakserve`，执行同样流程。该测试可由环境变量显式开启。

## 成功标准

第一版完成时应满足：

1. MCP stdio server 能在 Linux 无 `$DISPLAY` 环境中启动。
2. 默认 `browser_start` 使用 `headless`，不要求真实屏幕。
3. `direct + headless` 能访问 `https://example.com`，读取标题/文本，截图并关闭。
4. `direct + virtual` 在 Xvfb 可用时能以 headed 方式完成同样流程。
5. `cdp` 能连接已有 `cloakserve` endpoint，并完成导航、读取、截图、关闭。
6. 测试覆盖后端选择、session 生命周期和错误路径。

## 设计取舍

采用混合模式，但第一版以 `DirectBackend` 为主。原因是直接调用 CloakBrowser async API 能最快提供 agent 可用的浏览器工具，同时减少外部服务依赖。

`CdpBackend` 保留在第一版内，是因为 CloakBrowser 已经有 `cloakserve`，它适合多 seed、多身份和容器部署。但第一版只连接已有 endpoint，不管理 `cloakserve` 进程，避免生命周期管理过早扩大范围。

虚拟屏幕作为正式模式支持，但不作为默认值。默认 headless 能覆盖普通 agent 浏览任务；遇到反爬或检测站点需要更接近真实桌面行为时，用户显式选择 `virtual`。

## 自检

- 无未完成内容。
- 设计聚焦 MCP 服务第一版，没有扩大到浏览器平台。
- 三种显示/后端路径与成功标准一致。
- 错误边界具体且可测试。
- 上游 CloakBrowser 保持只读参考，不纳入本仓库实现范围。
