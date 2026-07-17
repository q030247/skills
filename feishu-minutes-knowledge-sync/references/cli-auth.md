# lark-cli 与 profile 认证参考

## 检查顺序

```sh
command -v lark-cli
lark-cli --version
lark-cli profile list
lark-cli auth status --profile <profile> --json --verify
```

不要通过读取 CLI 配置文件、缓存文件或 token 文件来判断认证；这些文件可能含敏感信息。只使用 CLI 的公开状态命令。

## 安装

当 `lark-cli` 不存在时，按用户约定执行：

```sh
npx @larksuite/cli@latest install
```

安装会下载软件并改变本机环境。若当前 AI 平台有审批机制，必须先走审批。安装后重新运行版本检查。

## profile 策略

- 输入中的 profile 是必填参数，不自动选第一个或当前默认值。
- 所有飞书命令显式携带 `--profile <profile>`，这比修改全局默认 profile 更适合多个 AI 平台共享同一台机器。
- profile 不存在时，可让用户从已有 profile 中选择，或在用户同意后按 `lark-cli profile add --help` 和 `lark-cli config init --help` 的当前输出创建。
- 只有用户明确说“把默认 profile 切换为 X”时才执行 `lark-cli profile use X`。

## 授权原则

- 妙记搜索仅支持 user 身份。
- 使用 `auth status --json --verify` 验证 token，不以本地缓存存在作为成功证据。
- 权限不足时优先按 CLI 错误中的 `permission_violations` 请求最小 scope。
- 认证 URL 视为不可修改字符串；同时展示原始链接和 CLI 生成的二维码。
- 授权分两轮进行，不能在用户尚未看到 URL 时阻塞等待。
- 不在 Markdown、日志、索引或报告中保存 access token、app secret、device code 或授权 URL 查询参数。

## 常见停止条件

- CLI 不存在且安装失败。
- 指定 profile 不存在，用户尚未选择创建或替代 profile。
- `verified` 不为真、用户身份不可用或 token 失效。
- 权限错误没有可安全自动补齐的最小 scope。
- 飞书返回无权读取某条妙记。

