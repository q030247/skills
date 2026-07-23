# 通用浮墨笔记模板

仅在知识库没有可用规范或相关模板时使用。若知识库规范要求其他字段、章节或日期格式，以知识库规范为准。

```markdown
---
title: 可检索标题
source: flomo
source_id: stable-memo-id
source_url: https://v.flomoapp.com/mine/?memo_id=stable-memo-id
source_created_at: YYYY-MM-DDTHH:mm:ssZ
source_updated_at: YYYY-MM-DDTHH:mm:ssZ
sync_status: synced
sync_status_label: 已同步 / Synced
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: []
capture_types: []
ai_processing_status: unprocessed
ai_processing_status_label: 未处理 / Unprocessed
article_extraction_status: not_applicable
article_extraction_status_label: 不适用 / Not applicable
---

# 可检索标题

## 原始内容

完整保留 flomo memo 的原始文字、标签、链接与媒体引用。

<!-- AI:START -->
## AI分流结果

- 内容类型：待处理
- 建议归属：待确认
- 关联项目：待确认
- 核心闪念：待处理
- 文章链接及访问状态：待处理
- 概念候选：待处理
- 待确认：

## 候选待办

暂无。识别到行动后使用`#候选待办`和稳定`candidate_id`，不得直接添加`#task`。
<!-- AI:END -->
```

## 更新边界

来源更新时先把旧“原始内容”保存到“来源更新历史”，再修改：

- `title`（仅当标题来自来源首行且本地未另行命名）
- `source_url`
- `source_updated_at`
- `updated`
- `tags`中来自 flomo 的标签
- `原始内容`章节

保留`capture_types`、`ai_processing_status`、`article_extraction_status`和AI标记区，以及模板以外已经存在的本地字段和章节。无法区分来源标签与本地标签时，不覆盖整个`tags`列表；合并并去重，同时在同步报告说明。
