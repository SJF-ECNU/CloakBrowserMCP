# CloakBrowser MCP v2 Browser Capabilities 设计

日期：2026-06-23

## 背景

当前 MCP 服务已经完成第一版能力：启动 CloakBrowser session、导航、点击、输入、执行 JavaScript、读取文本快照、截图和关闭。实现边界是 `ToolHandlers -> BrowserManager -> BrowserSession`，其中 `BrowserSession` 持有 Playwright `page` 和 `context`。

下一步目标是优先包装 CloakBrowser 和底层 browser 已有能力，而不是先实现搜索引擎、任务规划或网页理解这类上层策略。v2 继续保持薄封装：MCP 工具只把 agent 需要的浏览器原语暴露出来，不复制完整 Playwright API。

## 假设

- 现有 8 个工具保持兼容，名称、入参和返回结构不做破坏性修改。
- 默认运行模式仍是 Linux headless；虚拟屏幕和 CDP 继续作为显式模式。
- `browser_start` 可以增加可选参数，但不能要求用户提供额外配置才能使用默认流程。
- 新工具优先覆盖 agent 常见网页操作，不做复杂任务策略。
- v2 的测试以 fake Playwright 单元测试为主，真实浏览器 smoke 只验证关键路径。

## 目标

v2 提供三层能力：

1. 启动和身份配置
   - 包装 CloakBrowser 已有 `launch_context_async()` / `launch_persistent_context_async()` 参数。
   - 让 agent 能配置 user agent、viewport、color scheme、geoip、human preset、扩展、额外启动参数和 context 状态。

2. 页面操作原语
   - 包装 Playwright `page` 上常用的等待、键盘、鼠标、表单、滚动和导航能力。
   - 让 agent 不必用 `browser_evaluate` 手写 JavaScript 完成普通页面操作。

3. Context/session 状态管理
   - 包装 cookies、storage state 和多页面管理。
   - 让 agent 能复用登录状态、管理 tab，并在长任务中切换页面。

## 非目标

v2 不实现以下内容：

- 搜索引擎内置配置或搜索策略工具。
- CAPTCHA 自动求解。
- 代理池、账号池或任务调度。
- 完整 Playwright API 映射。
- 网络请求拦截、HAR、trace、复杂下载监听。
- 自动网页理解、DOM 规划或视觉定位。

这些可以作为后续版本叠加在 v2 原语之上。

## 启动配置设计

扩展 `StartOptions` 和 `browser_start`，增加下列可选字段：

- `user_agent: str | None`
- `viewport: dict[str, int] | None`
- `no_viewport: bool`
- `color_scheme: "light" | "dark" | "no-preference" | None`
- `geoip: bool`
- `stealth_args: bool`
- `args: list[str] | None`
- `extension_paths: list[str] | None`
- `human_preset: str`
- `human_config: dict | None`
- `storage_state: str | dict | None`
- `extra_http_headers: dict[str, str] | None`
- `permissions: list[str] | None`

`DirectBackend` 将这些字段透传给 CloakBrowser：

- 非持久 profile 使用 `launch_context_async(...)`。
- 持久 profile 使用 `launch_persistent_context_async(profile_dir, ...)`。
- `storage_state`、`extra_http_headers`、`permissions` 作为 context kwargs 透传。
- `viewport` 只在用户传入时透传；`no_viewport=True` 时向 CloakBrowser 传 `viewport=None`，明确关闭 viewport emulation。这样避免 MCP 入参无法稳定区分“未传 viewport”和“显式传 null”的问题。
- `args`、`extension_paths`、`stealth_args`、`geoip`、`human_preset`、`human_config` 作为 CloakBrowser 启动参数透传。

CDP 模式不重新启动浏览器，因此只接受和当前 page/context 操作相关的工具。`browser_start(backend="cdp")` 会忽略 direct-only 启动字段，返回结果中包含 warning，避免用户误以为参数已经改变远端浏览器身份。

## 页面操作工具

新增工具：

1. `browser_wait_for_selector`
   - 输入：`session_id`、`selector`、`state`、`timeout_ms`
   - 输出：操作成功状态。

2. `browser_press`
   - 输入：`session_id`、`selector`、`key`
   - 输出：操作成功状态。

3. `browser_hover`
   - 输入：`session_id`、`selector`
   - 输出：操作成功状态。

4. `browser_select_option`
   - 输入：`session_id`、`selector`、`value`
   - 输出：选择后的值或操作成功状态。

5. `browser_get_text`
   - 输入：`session_id`、`selector | None`
   - 输出：`text`。未传 selector 时读取 `document.body.innerText`。

6. `browser_get_attribute`
   - 输入：`session_id`、`selector`、`name`
   - 输出：`value`。

7. `browser_get_links`
   - 输入：`session_id`、`selector | None`、`limit`
   - 输出：链接数组，每项包含 `text` 和 `href`。

8. `browser_scroll`
   - 输入：`session_id`、`delta_x`、`delta_y`
   - 输出：操作成功状态。

9. `browser_reload`
   - 输入：`session_id`、`wait_until`
   - 输出：当前 URL 和 title。

10. `browser_go_back`
    - 输入：`session_id`、`wait_until`
    - 输出：当前 URL 和 title；无历史记录时返回明确 message。

11. `browser_go_forward`
    - 输入：`session_id`、`wait_until`
    - 输出：当前 URL 和 title；无前进记录时返回明确 message。

这些工具都在 `BrowserSession` 上实现，`ToolHandlers` 只负责转发和把 dataclass 结果转成 dict。

## Context 和 Session 状态工具

新增工具：

1. `browser_get_cookies`
   - 输入：`session_id`、`urls | None`
   - 输出：cookies 数组。

2. `browser_set_cookies`
   - 输入：`session_id`、`cookies`
   - 输出：操作成功状态。

3. `browser_clear_cookies`
   - 输入：`session_id`
   - 输出：操作成功状态。

4. `browser_get_storage_state`
   - 输入：`session_id`
   - 输出：JSON storage state。

5. `browser_save_storage_state`
   - 输入：`session_id`、`path`
   - 输出：文件路径。

6. `browser_new_page`
   - 输入：`session_id`、`url | None`、`switch: bool`
   - 输出：`page_id`、`url`、`title`。

7. `browser_list_pages`
   - 输入：`session_id`
   - 输出：pages 数组，每项包含 `page_id`、`url`、`title`、`is_active`。

8. `browser_switch_page`
   - 输入：`session_id`、`page_id`
   - 输出：当前 page 信息。

9. `browser_close_page`
   - 输入：`session_id`、`page_id | None`
   - 输出：操作成功状态。关闭 active page 后自动切到剩余页面；如果没有页面则新建空白页。

`BrowserSession` 负责维护 `page_id -> page` 映射。初始页面注册为第一个 page。页面关闭时清理映射，active page 始终保持可用。

## 下载能力边界

v2 不做下载监听队列和网络事件系统。只在后续版本考虑：

- `browser_expect_download`
- `browser_list_downloads`
- `browser_clear_downloads`

原因是 Playwright 下载通常需要围绕触发动作建立 expect block，这会影响现有 click/type 工具形态。先完成页面和 context 原语更稳。

## 错误处理

新增错误仍保持可行动：

- selector 等待或操作超时：沿用 `ElementNotFound`，消息包含 selector 和动作。
- page id 不存在：新增或复用明确异常，消息包含可用 page id。
- storage state 写入失败：返回包含目标 path 的错误。
- direct-only 启动字段用于 CDP：不失败，返回 warning。
- 参数类型不合法：尽早在 `StartOptions.from_values()` 或工具方法中抛出 `ValueError`。

不把浏览器异常吞成通用失败；保持原始异常链，方便调试。

## 测试策略

1. 单元测试
   - `StartOptions` 解析新增字段。
   - `DirectBackend` 透传新增 CloakBrowser 参数。
   - `BrowserSession` 页面工具调用 fake page 的对应方法。
   - `BrowserSession` context 工具调用 fake context 的对应方法。
   - 多页面映射、切换和关闭逻辑。

2. MCP 工具测试
   - `create_server()` 注册旧 8 个工具和 v2 新工具。
   - read-only 工具设置 `readOnlyHint=True`：`browser_get_text`、`browser_get_attribute`、`browser_get_links`、`browser_get_cookies`、`browser_get_storage_state`、`browser_list_pages`。
   - 会改变浏览器状态的工具不标记 read-only。

3. smoke 测试
   - 默认测试仍不下载真实 CloakBrowser binary。
   - 已有环境变量控制的 headless/virtual/CDP smoke 保持可选。
   - 可在 headless smoke 中补一个轻量路径：导航到静态页面，验证 `get_text`、`get_links`、`reload`。

## 成功标准

- 现有 8 个工具继续可用。
- 新增工具完成 fake 单元测试覆盖。
- `uv run --no-editable pytest -q` 通过。
- `uv run --no-editable python -m cloakbrowser_mcp.server` 或 console script 能正常启动。
- Claude Code 重新加载 MCP 后能看到新增工具。
- README 更新工具列表和关键示例。

## 实现顺序

1. 扩展 models：新增启动字段和必要结果 dataclass。
2. 扩展 DirectBackend 参数透传，保持 CDP 兼容。
3. 扩展 BrowserSession 页面原语。
4. 扩展 BrowserSession context/session 状态工具。
5. 注册 MCP 工具并补 read-only annotations。
6. 更新 README。
7. 运行完整测试并重新检查工具列表。

## 自检

- 没有引入搜索引擎或上层策略。
- 没有承诺完整 Playwright API。
- 下载和网络拦截已经明确延后。
- 设计保持现有架构边界，只扩展 `StartOptions`、`DirectBackend`、`BrowserSession` 和 `ToolHandlers`。
- 测试标准可执行，且不依赖真实浏览器作为默认路径。
