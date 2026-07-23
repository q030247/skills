# 浮墨同步索引模板

根据目标知识库规范补齐或调整 frontmatter。`items`是机器读取的唯一同步台账，正文表格用于人工核对，两者必须同步更新。

```markdown
---
title: 浮墨同步索引
summary: 记录浮墨笔记的新增、更新和删除状态，用于增量同步、去重和保持本地删除。
tags: [浮墨, 同步, 去重]
type: system
status: active
status_label: 活跃 / Active
source: flomo
created: YYYY-MM-DD
updated: YYYY-MM-DD
ai_generated: true
index_version: 1
identity_key: memo_id
last_successful_sync_at:
sync_policy:
  existing_id: skip
  missing_local_file: keep_deleted
  source_updated: update_source_section
  source_deleted: mark_only
  restore: explicit_only
items: []
---

# 浮墨同步索引

此文件是浮墨来源文件夹内的唯一同步状态台账。

## 同步策略

- 一条 memo 对应一个 Markdown 文件。
- 已登记且未更新的 ID：跳过，不重复创建。
- flomo 内容已更新：保留旧版原文，再更新来源属性和“原始内容”区域。
- flomo 内容已删除：保留本地文件，在索引标记来源删除。
- 本地文件被删除：保留历史 ID，不自动恢复。
- 新笔记：正文和附件成功落盘后才能登记。
- 失败项：记录在同步报告中，不写成已同步。

## 状态统计

| 状态 | 数量 |
|---|---:|
| 新增 | 0 |
| 更新 | 0 |
| 已删除 | 0 |

## 已同步笔记

| 创建时间 | flomo ID | 本地笔记 | 同步动作 | 删除标记 |
|---|---|---|---|---|

## 维护说明

- `sync_action`只使用`added`、`updated`或`deleted`。
- 不删除历史 ID；本地文件缺失时保留索引并标记已删除。
- 不直接修改`memo_id`。
```

单条`items`记录格式：

```yaml
- memo_id: stable-source-id
  source_url: https://v.flomoapp.com/mine/?memo_id=stable-source-id
  source_created_at: YYYY-MM-DDTHH:mm:ss+08:00
  source_updated_at: YYYY-MM-DDTHH:mm:ss+08:00
  local_path: relative/path/to/note.md
  local_state: present
  local_state_label: 存在 / Present
  source_state: present
  source_state_label: 存在 / Present
  sync_status: synced
  sync_status_label: 已同步 / Synced
  sync_action: added
  sync_action_label: 新增 / Added
  is_deleted: false
  deleted_at:
  moved_at:
  destination_type:
  revision_count: 0
  synced_at: YYYY-MM-DDTHH:mm:ss+08:00
  attachments: []
```
