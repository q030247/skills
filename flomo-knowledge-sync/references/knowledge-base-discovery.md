# 知识库发现规则

## 目标

用最少读取确定知识库位置和写入规则，避免扫描整个项目或误读归档、隐私正文。

## 发现顺序

1. 确定项目根目录和当前工作目录。
2. 读取根目录中存在的指令文件：`AGENTS.md`、`CLAUDE.md`、`AI-RUNBOOK.md`、`README.md`。
3. 从这些文件提取知识库/vault 路径、目录路由和开始前必须读取的文件。
4. 只读取被明确指向的 schema、glossary、目标目录 README、主页或索引。
5. 从规则中提取模板目录；未声明时检查`templates/`、`template/`、`模板/`、`90-模板/`、`.obsidian/templates/`。先查看候选文件名和属性，再读取可能相关的模板正文。
6. 在规则目录、模板目录与候选目标目录中搜索`浮墨|flomo|memo|随手记|收件箱|同步索引`，不默认进入归档目录。
7. 汇总成以下执行参数：

```yaml
knowledge_base_root:
target_notes_dir:
attachments_dir:
index_path:
report_path:
required_frontmatter: []
template_candidates: []
selected_template:
filename_pattern:
batch_limit: 50
source_update_policy: replace_source_section_only
archive_dirs: []
safety_policy:
inbox_lifecycle:
```

## 未指定知识库

未找到可靠的知识库声明时，不要默认选择目录。请用户从以下方式中选择：

1. 提供已有本地知识库路径。
2. 使用当前 AI 工具所在的工作目录。

提问时展示当前工作目录的规范化绝对路径，并说明若选择它，技能会在该目录内继续查找规范和模板；若两者都没有，才创建通用的`flomo-notes/`结构。用户确认前不要调用`memo_search`或创建同步文件。

用户选择当前工作目录只代表授权它作为本次知识库根目录，不代表其中所有 Markdown 都可以扫描；仍然遵守渐进读取和归档排除规则。

## 相关模板判断

按以下强度判断模板是否相关：

1. 规范明确指定给 flomo 或外部输入使用。
2. 模板名称或说明明确包含“浮墨”“flomo”“memo”。
3. 模板明确适用于“收件箱”“外部采集”“随手记”，且字段能保存来源 ID、来源 URL、创建时间和原始内容。

普通会议、项目、日报、人物或资源模板不是浮墨同步模板。模板缺少稳定 ID 等同步必需字段时可以补充，但不得删除模板原有字段。

## 无规范回退

若用户已经明确指定知识库文件夹，但其中没有规则，先判断是否存在相关模板：

- 有相关模板：按模板组织，一条 memo 一个 Markdown，并补充同步必需字段。
- 无相关模板：采用以下通用结构。

- 目标目录：`flomo-notes/`
- 附件目录：`flomo-notes/attachments/`
- 索引：`flomo-notes/flomo-sync-index.md`
- 报告：`flomo-notes/YYYY-MM-DD-flomo-sync-report.md`
- 文件名：`YYYY-MM-DD-HHmm-title.md`
- 组织：一条 memo 一个 Markdown 文件
- 更新：保留旧版原文后更新来源属性和“原始内容”区域，保留本地整理内容
- 归档：同步技能不执行；统一交给`close-confirmed-inbox`审批、迁移并更新索引路径
- 删除：来源删除只在索引标记并保留本地文件
- 首次同步：最近 3 个自然月
- 批次：最多 50 篇

创建这些文件前先简要告知用户即将采用回退结构，但不因缺少规范而反复追问格式偏好。
