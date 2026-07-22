---
name: feishu-minutes-knowledge-sync
description: 将飞书妙记通过 lark-cli 增量同步到本地 Obsidian 或 Markdown 知识库，并在每次同步时把已由用户批准的飞书候选待办转换为唯一正式任务。只要用户提到“同步飞书妙记”“把妙记拉到 Obsidian/本地知识库”“建立妙记索引”“按指定 profile 同步会议纪要和逐字稿”或“转换已批准的飞书候选待办”，就应使用本技能；负责验证 CLI、profile 和用户授权，维护互相双链的智能纪要与原始逐字稿、索引和报告，并在零新增同步时仍执行本地候选转换；不负责生成候选或内容提炼。
compatibility: 需要 Python 3、Node.js/npx、可读写的本地项目目录，以及能访问飞书的 lark-cli；输入必须包含 profile，首次认证需要用户在浏览器完成授权。
---

# 飞书妙记知识库同步

把飞书妙记视为外部源数据，把本地 Markdown 知识库视为目标。先确认 CLI、profile 和知识库，再读取妙记。任何 AI 平台都通过本地文件与 `lark-cli` 完成，不依赖平台专属连接器。

重复且容易出错的同步步骤已内化到 `scripts/sync_minutes.py`。AI 负责读取目标知识库规范、确认路径和授权；脚本负责分页、去重、双文件生成、双链校验、索引和报告。除非脚本明确不支持目标知识库要求，不要重新手写一套同步逻辑。

## 输入契约

开始前从用户输入或当前任务上下文取得：

- `profile`：必填，lark-cli 配置名称。
- `selected_folder`：可选，当前 AI 平台已经选定的工作区或项目文件夹；存在时优先作为知识库。
- `knowledge_base`：可选，用户输入的知识库路径；仅在当前没有选定文件夹时使用。
- `default_folder`：可选，前两者都没有时使用；默认是当前执行目录下的 `feishu-minutes-knowledge-base/`。
- `start` / `end`：可选，同步时间范围；首次未指定时默认最近 30 天，单次范围最长 1 个月。
- `scope`：可选，`owned`、`participated` 或 `all-related`；默认 `all-related`，即“我拥有的”和“我参与的”两次查询取并集。
- `skip_local_validation_prefix`：可选，不允许自动化读取的知识库相对目录前缀；索引继续参与去重，但不检查对应文件。

缺少 `profile` 时暂停并询问，不猜测或自动选用其他 profile。缺少知识库时按“定位知识库”处理。

## 安全边界

- 只在用户明确要求同步时访问飞书；验证连接只做只读检查。
- 不输出、保存或转发 appSecret、accessToken、device_code、Cookie 等凭据。
- 妙记、客户、公司和个人内容只写入用户授权的本地目录，不发送到其他服务。
- 同步只新增和去重。既有来源 ID 不重复创建；来源更新默认不覆盖本地文件，而是在报告中列为待确认，除非知识库规范明确允许更新 AI 来源区域。
- 不删除、移动或自动归类同步结果。`local_state: deleted` / `pair_state: deleted` 是永久墓碑，继续参与去重且永不自动恢复或重新同步。
- 每条妙记必须生成两个 Markdown：智能纪要与原始逐字稿。两者都成功写入后，才把该 token 登记为同步成功。
- 新同步的原始逐字稿必须以`transcript_review_status: pending_review`进入人工校订闸门；同步技能不得替用户改成可提取状态，也不得改写原始文字记录。
- 只转换已经勾选、具有稳定 `feishu-...` 候选 ID、目标唯一且通过幂等检查的候选待办；不根据语义猜测批准状态、目标位置或负责人。
- 批量上限服从知识库规范；没有规范时每批最多 50 条。超过上限先展示范围、数量和风险，取得确认后分批执行。

## 1. 检查或安装 lark-cli

1. 用当前平台的本地命令能力检查 `lark-cli` 是否在 PATH，例如 `command -v lark-cli`，再运行 `lark-cli --version`。
2. 已安装则记录版本并继续，不因为存在更新提示中断同步。
3. 未安装时，告知用户将安装官方飞书 CLI，然后执行：

   ```sh
   npx @larksuite/cli@latest install
   ```

4. 当前平台要求外部下载或安装审批时，先取得该平台的明确批准。安装失败时停止，不用未经说明的替代包或脚本。
5. 安装后重新检查 PATH 与版本；仍不可用时报告环境问题并停止。

## 2. 验证指定 profile 与用户授权

始终显式传入 `--profile <profile>`，避免改变其他 AI 平台或终端的全局 profile。不要仅为了同步执行 `profile use`；只有用户明确要求切换默认 profile 时才切换。

1. 运行 `lark-cli profile list`，确认输入的 profile 存在。不存在时列出可用 profile 名称，让用户选择已有 profile，或明确同意后按 CLI 引导创建新 profile。
2. 对指定 profile 运行：

   ```sh
   lark-cli auth status --profile <profile> --json --verify
   ```

3. 只有 `verified` 和用户身份状态表明确有效时，才视为已连接。记录用户名或 open_id 用于人工确认，但不要写入妙记正文。
4. 未登录、token 失效或缺少妙记读取权限时，采用 split-flow：

   ```sh
   lark-cli auth login --profile <profile> --scope "minutes:minutes.search:read" --no-wait --json
   ```

   按错误提示补充最小必要 scope；不要直接请求全部权限。把返回的授权 URL 原样交给用户，并用 `lark-cli auth qrcode` 生成二维码。当前轮到此暂停。用户回复已完成授权后，重新发起授权流程取得新的 device code，再由 Agent 完成 CLI 指示的认证收尾，最后重新运行 `auth status --verify`。
5. 不把“profile 存在”当作“已授权”，也不把 bot 身份当作用户身份。妙记搜索与详情使用 `--as user`。

认证与 profile 的平台无关细节见[CLI 与认证参考](references/cli-auth.md)。

## 3. 定位知识库

严格按以下优先级选择，不把低优先级路径覆盖到高优先级路径：

1. 当前 AI 平台已选定的工作区、项目或文件夹，作为 `selected_folder`。
2. 当前没有选定文件夹时，使用用户输入的 `knowledge_base`。
3. 用户也没有输入时，使用 `default_folder`；默认创建当前执行目录下的 `feishu-minutes-knowledge-base/`。

AI 平台仅打开了某个文件、不代表其父目录已被选为工作区；必须以平台实际提供的工作区或项目根目录为准。脚本在输出和报告中记录 `selected-folder`、`user-input` 或 `default-folder`，便于核对路径来源。

路径必须在当前平台允许读写的范围内。相对路径以项目根目录解析，并在执行前回显最终绝对路径。

## 4. 渐进读取知识库规范

1. 读取根目录 Agent 指令和运行手册。
2. 读取它们指向的 schema、术语表、目标目录 README、主页或索引。
3. 只在规则目录、模板目录、索引目录和候选目标目录搜索“飞书妙记、妙记、minutes、同步索引、逐字稿、会议纪要”；不默认扫描归档或正文全集。
4. 提取目标目录、必填属性、文件命名、模板、索引位置、报告位置、批次上限、安全规则和 AI 可写边界。
5. 冲突优先级：用户本轮要求 > 更接近目标目录的指令 > 知识库根规则 > 本技能默认值。

规范存在时完全遵守。规范不存在时，将同步结果放在用户已指定的知识库/项目文件夹下的 `feishu-minutes/`，索引放在同目录，报告放在 `feishu-minutes/reports/`。不要顺便创建整套知识库规范。

### 知识库适配原则

技能不内置开发者、制作者或某台机器上的知识库名称、用户名、绝对路径、组织名称、业务分类和固定目录。每次执行都从目标项目的规则文件与用户输入动态取得这些信息。

若目标规范定义了收件箱、AI 报告区、归档排除目录或 `meeting` / `transcript` 类型，则按规范映射。若没有定义，才使用本技能的通用回退目录与模板。不得根据会议内容猜测组织归属。

## 5. 读取或创建 Markdown 索引

1. 优先使用规范指定的索引；其次在目标目录查找正文明确声明为飞书妙记同步索引的 Markdown。
2. 脚本使用 Markdown 中由注释标记包围的 JSON 状态区作为唯一机器台账，并自动生成用于人工核对的表格。若 token 重复、路径冲突、状态区损坏或旧索引没有受管标记，停止写入并标记待确认，不自动修复历史。
3. 没有索引时，按[索引模板](references/index-template.md)创建。索引也必须满足知识库必填属性。
4. 唯一键使用 `minute_token`，URL 只用于追溯。索引永不删除历史 token。
5. 本地任一配对文件缺失时标记 `local_state: partial` 或 `missing`；已登记为 `deleted` 的来源包永久跳过，不提供自动恢复开关。
6. 索引只保存知识库相对路径。遇到其他设备留下的绝对路径时，使用 `--legacy-root <旧设备知识库根目录>` 转换为相对路径；转换后不再保存旧设备根目录。

## 6. 调用内置同步脚本

先从知识库规则解析目标目录、索引、报告、类型、状态与禁止读取的目录，然后从知识库根目录运行：

```sh
python3 <skill-dir>/scripts/sync_minutes.py doctor --profile <profile>

python3 <skill-dir>/scripts/sync_minutes.py sync \
  --profile <profile> \
  --selected-folder <current-selected-folder> \
  --knowledge-base <user-input-path-if-no-selected-folder> \
  --default-folder feishu-minutes-knowledge-base \
  --target-dir <relative-target-dir> \
  --index-path <relative-index-path> \
  --report-path <relative-report-path> \
  --end YYYY-MM-DD \
  --overlap-days 2 \
  --scope all-related \
  --batch-limit 50 \
  --skip-local-validation-prefix <relative-excluded-dir> \
  --summary-type meeting \
  --transcript-type transcript \
  --status raw
```

只传实际存在的高优先级参数：有 `--selected-folder` 时可以省略 `--knowledge-base`；两者都没有时才使用 `--default-folder`。所有索引路径和目录参数使用知识库相对路径；当前设备解析后的绝对根目录只用于本次运行，不写入同步索引。脚本只依赖 Python 标准库，不安装额外 Python 包。

`doctor` 返回非零时，按其 JSON 结果处理 CLI 缺失或授权问题，不继续同步。`sync` 的退出码：`0` 完成、`2` 前置条件失败、`3` 候选超过批次上限需确认、`4` 部分失败。退出码 `3` 后先向用户展示数量；获得确认后追加 `--confirm-batch`，脚本仍只处理第一批，不会突破 `--batch-limit`。

## 7. 脚本执行的增量规则

1. 读取索引中的 token、两个本地路径、来源更新时间和状态。
2. 使用 `lark-cli minutes +search --profile <profile> --as user --format json` 搜索。必须至少给时间、关键词、owner 或 participant 条件。
3. 默认 `all-related` 时分别查询 `--owner-ids me` 与 `--participant-ids me`，再按 token 取并集；不要把两个过滤器塞进一次请求中猜测语义。
4. 单次时间范围最长 1 个月。更长范围拆为多个不重叠月窗。日期型 `--end` 包含当天整天。
5. 遍历 `has_more` / `page_token`。累计候选超过知识库批次上限时停止并请求确认。
6. token 已登记且两文件存在：比较来源更新时间；无变化则跳过，较新则只写“来源更新待确认”，不覆盖本地内容。
7. token 已登记且本地标记删除：永久跳过，不下载详情、不恢复、不反复报告为新内容。
8. 旧记录缺少来源时间时，只回填索引元数据，不覆盖本地纪要；搜索结果缺少旧 token 不能证明来源已删除。

## 8. 脚本同步一条妙记的两个文件

对每个新 token 单独执行，失败不影响其他 token，但不能登记为完整成功：

1. 脚本获取全部必要产物：

   ```sh
   lark-cli minutes +detail --profile <profile> --as user \
     --minute-tokens <token> --summary --todo --chapter --keyword --transcript \
     --output-dir ./<project-relative-temp-dir> --format json
   ```

   CLI 文件参数只使用工作目录下的相对路径。读取返回 JSON 中的标题、`note_id`、智能总结、待办、章节、关键词和 `transcript_file`。
2. 文件名先清洗非法路径字符，再使用同一稳定基名：
   - 智能纪要：`YYYY-MM-DD-主题-智能纪要.md`
   - 原始逐字稿：`YYYY-MM-DD-主题-原始逐字稿.md`
   - 标题或日期无法确认时使用 token 短码，并在报告标记待确认。
3. 按[笔记模板](references/note-templates.md)生成两个 Markdown。智能纪要原样保存飞书产出的 summary、todos、chapters、keywords，不把 Agent 的补充推断混入来源内容。逐字稿完整保存 `transcript_file` 内容，不自行总结或改写。
4. 两文件都写入稳定来源字段：`source_id`、`source_group_id`、`content_role`、`minute_token`、`source_url`（若有）、`source_created_at`、`source_updated_at`、`note_id`（若有）、`profile_name`、`sync_status`。
   - 智能纪要额外预留 `capture_types`、`ai_processing_status`、`article_extraction_status` 和 `<!-- AI:START -->` / `<!-- AI:END -->` 受控区，供每日处理幂等写入分类与衍生结果。同步不得覆盖用户或每日处理已经更新的受控状态。
   - 原始逐字稿额外写入`transcript_review_status: pending_review`、空的`transcript_text_source`和空的`corrected_transcript`。
   - 这些字段是知识库的人工校订状态，不属于飞书来源正文。后续同步不得覆盖用户已经修改的状态或校订稿链接。
5. 智能纪要正文链接 `[[原始逐字稿文件名]]`；逐字稿正文链接 `[[智能纪要文件名]]`。使用不含 `.md` 的 Obsidian 双向链接。
6. 先以临时文件准备两篇笔记，验证 YAML、必填字段、文件名和双链；再写入最终位置。若任一文件失败，删除本次尚未正式登记的临时文件，保留失败信息，不留下单边成功假象。
7. 两篇都成功后才追加索引记录，`sync_status: synced`、`pair_state: complete`。不要把逐字稿临时 `.txt` 当作知识库最终产物。

## 9. 转换已批准候选待办

这一步是每次同步的固定本地闭环阶段。即使飞书搜索结果为零新增，也必须在已确定的知识库中执行；外部同步失败时，只要知识库位置、规范和候选目标仍可安全解析，也应独立完成本地转换并如实报告两部分状态。

1. 只在知识库规则允许的范围查找 `candidate_id: feishu-...`：包括智能纪要的 AI 受控区，以及每日处理写入的 AI 衍生卡。不要扫描原始逐字稿正文。
2. 候选同时满足以下条件才可转换：复选框已经勾选；存在稳定 `candidate_id`；没有 `#已转正式任务`、`promoted_to` 或其他成功标记；“建议正式位置”能解析为唯一、可写且符合知识库任务路由的文件；目标中不存在相同 `candidate_id` 或同一来源的正式任务。
3. 按知识库正式格式在唯一目标写入任务，例如 `- [ ] #task #领域标签 具体行动`，并在任务的缩进行保存 `candidate_id` 与来源双链，保证可追溯和幂等。
4. 先写入正式任务并验证目标中恰好存在一份，再回写候选：保留已勾选状态，追加 `#已转正式任务`、`promoted_to: [[目标文件]]` 和 `promoted_at: YYYY-MM-DDTHH:mm:ss+时区`。任一步失败都不得伪造成功标记。
5. 目标不唯一、文件不可写、格式不合规或疑似重复时不转换，列为待确认。合同、财务、合规、客户触达、经营决策和生产系统任务即使已勾选，也必须满足知识库要求的额外人工确认。
6. 重复运行只审计既有转换，不重复创建正式任务。每日处理负责生成候选；本同步技能不得顺便提炼妙记或生成新候选。

## 10. 更新索引与执行报告

索引机器台账与正文人工核对表必须一致；脚本每次运行都从 JSON 状态区完整重建人工表格，包括 `deleted` 状态。每条记录至少包含 token、来源 URL、两个知识库相对路径、来源时间、同步时间、配对状态和本地/来源状态。

每次执行都生成报告，至少包括：

- 执行时间、profile 名称、已验证的用户身份、查询范围、目标目录和唯一键
- 新增、跳过、部分失败、失败、待确认数量
- 已批准候选、转换成功、已存在、转换失败和待确认数量，以及每个成功任务的目标双链
- 每条新增妙记的智能纪要与逐字稿双链
- 授权、分页、未覆盖范围、内容分级和失败原因
- 安全检查：是否覆盖、移动、删除或对外发送数据

报告是 AI 衍生内容，遵循知识库的 AI 标识规则。报告不得包含 token 凭据或完整敏感正文。

## 完成检查

- `lark-cli` 的安装与版本有真实命令证据。
- 指定 profile 存在，且用户身份通过 `auth status --verify`。
- 知识库路径已明确，并已读取适用规范、目标目录说明和索引。
- 每个成功 token 恰好对应一篇智能纪要和一篇原始逐字稿，且双链互指。
- 两篇笔记均满足必填属性、命名与保密要求，原始逐字稿未被改写。
- 新增原始逐字稿处于`pending_review`，没有被同步任务自动放行进行知识提取。
- 零新增同步也完成了飞书候选转换检查；每个成功转换的候选与正式任务双向可追溯，且重复运行不重复创建。
- 索引无重复 token，失败或本地删除项没有伪装成成功。
- 报告数量与实际文件及索引一致，并列出待确认项。
