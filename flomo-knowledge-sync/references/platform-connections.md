# flomo MCP 平台连接参考

官方服务地址：`https://flomoapp.com/mcp`

传输协议：Streamable HTTP

## 通用原则

- 优先 OAuth 自动授权。
- 只有平台不支持 OAuth 时才使用个人 Token。
- Token 只填写到平台的安全凭据设置，不写入对话或项目文件。
- 连接后用`memo_search`做最小只读验证，不创建测试笔记。
- 平台界面和命令可能更新；若当前平台已有原生“添加 MCP/连接器”能力，以该能力的实际参数为准。

## Claude.ai / Claude 桌面端

进入 Customize → Connectors → Add custom connector，名称填`flomo`，Remote MCP server URL 填官方地址，然后完成 OAuth。

## Claude Code

```sh
claude mcp add --transport http flomo https://flomoapp.com/mcp
```

随后用`/mcp`检查状态并完成授权。

## ChatGPT

进入 Settings → Apps → Advanced settings，开启 Developer mode；在 Apps 中添加自定义 MCP，填写官方地址并完成 OAuth。每次新对话可能需要手动启用 flomo。

## Codex CLI

```sh
codex mcp add flomo --url https://flomoapp.com/mcp
```

随后在 MCP 设置中确认 flomo 已启用并完成授权。

## Cursor 与兼容 JSON 配置的平台

```json
{
  "mcpServers": {
    "flomo": {
      "type": "http",
      "url": "https://flomoapp.com/mcp"
    }
  }
}
```

部分客户端把`type`写作`streamableHttp`，或使用`transport: streamable-http`。不要同时堆叠互相冲突的字段。

## 无配置权限的 Agent

如果当前 Agent 不能查看或修改平台连接器：

1. 说明未发现`memo_search`，所以不能确认已连接。
2. 给出与当前平台对应的最短步骤。
3. 等用户完成授权并重新启用工具。
4. 再次探测，成功后才继续读取知识库和同步。
