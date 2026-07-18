# 内置同步脚本

`flomo_sync.py`负责 flomo 同步的本地、确定性部分，不直接连接 MCP，也不保存任何凭据。

## 能力

- 默认 dry-run，输出新增、更新、跳过和删除标记计划。
- 按 memo ID 去重，单批最多 50 条。
- 拒绝写入被截断的 memo。
- 新增一条 memo 一个 Markdown。
- 来源更新时只替换来源属性和“原始内容”章节。
- 本地文件缺失时保留历史 ID，并标记为已删除。
- 来源明确删除时只标记，不物理删除本地文件。
- 同时重建 Markdown 索引的 YAML、统计和人工核对表。

## 输入

UTF-8 JSON 文件，支持两种顶层格式：

```json
{"memos": [{"id": "...", "content": "...", "created_at": "...", "updated_at": "..."}]}
```

或直接使用 memo 数组。字段与 flomo MCP 的`memo_search`/`memo_batch_get`返回保持一致。

## 安全用法

先 dry-run：

```sh
python3 scripts/flomo_sync.py --vault /path/to/vault --input /tmp/memos.json
```

审查计划后再执行：

```sh
python3 scripts/flomo_sync.py --vault /path/to/vault --input /tmp/memos.json --apply
```

恢复本地已删除笔记需要用户明确授权，并传入`--restore-deleted --apply`。脚本不负责 MCP 连接、OAuth 和 Token 管理，也不会向 flomo 写入内容。
