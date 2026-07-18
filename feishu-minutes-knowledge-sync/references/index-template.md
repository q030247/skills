# 飞书妙记同步索引模板

根据目标知识库规范调整字段。由 `scripts/sync_minutes.py` 维护的 JSON 状态区是机器同步台账，正文表格用于人工核对；不要手工编辑状态区。

```markdown
---
title: 飞书妙记同步索引
summary: 记录飞书妙记与本地智能纪要、原始逐字稿的对应关系，用于增量同步、去重和保留删除状态。
tags: [飞书妙记, 同步, 索引]
type: system
status: active
source: feishu-minutes
created: YYYY-MM-DD
updated: YYYY-MM-DD
confidentiality: 待目标知识库规范确定
ai_generated: true
index_version: 2
identity_key: minute_token
profile_name: PROFILE
---

# 飞书妙记同步索引

## 同步策略

- 一个 minute token 对应一篇智能纪要和一篇原始逐字稿。
- 两篇笔记都成功落盘后才登记为完整同步。
- 已登记 token 不重复创建；本地删除默认不恢复。
- 来源缺失不能直接推断来源已删除。

<!-- FEISHU_MINUTES_SYNC_STATE:START -->
```json
{
  "index_version": 2,
  "identity_key": "minute_token",
  "last_successful_sync_at": null,
  "items": []
}
```
<!-- FEISHU_MINUTES_SYNC_STATE:END -->

## 已同步妙记

<!-- FEISHU_MINUTES_SYNC_TABLE:START -->
| 来源时间 | minute token | 智能纪要 | 原始逐字稿 | 配对状态 |
|---|---|---|---|---|
<!-- FEISHU_MINUTES_SYNC_TABLE:END -->
```

JSON 状态区中的单条记录格式：

```json
{
  "minute_token": "obcnxxxxxxxx",
  "source_url": "",
  "source_title": "",
  "source_created_at": "",
  "source_updated_at": "",
  "note_id": "",
  "summary_path": "TARGET_DIR/YYYY-MM-DD-主题-智能纪要.md",
  "transcript_path": "TARGET_DIR/YYYY-MM-DD-主题-原始逐字稿.md",
  "local_state": "present",
  "source_state": "present",
  "pair_state": "complete",
  "sync_status": "synced",
  "sync_action": "added",
  "profile_name": "PROFILE",
  "synced_at": "YYYY-MM-DDTHH:mm:ss+08:00"
}
```
