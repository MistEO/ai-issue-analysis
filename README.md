# ai-issue-analysis

一个通用的 GitHub action，在 Issue 打开或被评论时自动调用 AI coding agent（Claude / Codex / Copilot）进行分析，并把分析过程和最终结论持续回写到同一条评论里。

实战效果展示：

- [Bot 自动分析回复 ISSUE: 加载时间过长导致拜访好友失败](https://github.com/MaaEnd/MaaEnd/issues/1361#issuecomment-4071450863)
- [Bot 响应 @ 进行分析回复 ISSUE: 换班时会把训练室干员换下](https://github.com/MaaAssistantArknights/MaaAssistantArknights/issues/15963#issuecomment-4067281056)

## 支持的 Agent

| Agent | 认证方式 |
|-------|---------|
| `claude` | Anthropic API Key |
| `codex` | OpenAI API Key（需支持 Responses API，不是 Chat Completions） |
| `copilot` | GitHub PAT（需 Copilot Pro，在 [PAT 设置](https://github.com/settings/personal-access-tokens) 勾选 Copilot 权限） |

## 快速接入

1. 获取对应 agent 的 API Key / Base URL

    - **Claude**: 通过您的 AI 提供商获取 API Key 和 API Base URL
    - **Codex**: 通过您的 AI 提供商获取 API Key 和 API Base URL *（需支持 Responses API）*
    - **Copilot**: 前往 [GitHub PAT](https://github.com/settings/personal-access-tokens) 新增 token，勾选所有 Copilot 权限，过期时间设为一年以内

2. 在仓库 Settings → Secrets → Actions 添加 secret

    - `API_KEY`: 上一步获取的 API Key
    - `API_BASE_URL`: 上一步获取的 API Base URL *（Copilot 忽略该步骤）*

3. 把下面两个文件拷贝到你的仓库里

    - [`.github/workflows/ai-issue-analysis.yml`](.github/workflows/ai-issue-analysis.yml)
    - [`.claude/skills/generic-issue-log-analysis/SKILL.md`](.claude/skills/generic-issue-log-analysis/SKILL.md)（推荐根据项目实际情况修改调整，以提升分析质量）

4. 修改 workflow 中的关键参数

    - `agent`: 选择 `copilot` / `claude` / `codex`
    - `model`: 填入要使用的模型名

5. 新提个 issue 测试下能否正常运行，或者在已有 issue 里 `@github-actions`

> [!TIP]
>
> 如果你的项目有固定的日志包命名、关键日志路径、附件目录、模块映射或上游依赖，建议在通用版 `SKILL.md` 基础上微调，分析质量会更高。最佳实践参考：
> - [MaaEnd](https://github.com/MaaEnd/MaaEnd/blob/v2/.claude/skills/maaend-issue-log-analysis/SKILL.md)
> - [MaaAssistantArknights](https://github.com/MaaAssistantArknights/MaaAssistantArknights/blob/dev-v2/.claude/skills/maa-issue-log-analysis/SKILL.md)

## Workflow 示例

### Claude

```yaml
- uses: MistEO/ai-issue-analysis@main
  with:
    agent: claude
    api-key: ${{ secrets.API_KEY }}
    api-base-url: ${{ secrets.API_BASE_URL }}
    model: claude-sonnet-5
    reasoning-effort: xhigh
    github-token: ${{ secrets.GITHUB_TOKEN }}
    bot-name: "@github-actions"
```

### Codex

```yaml
- uses: MistEO/ai-issue-analysis@main
  with:
    agent: codex
    api-key: ${{ secrets.API_KEY }}
    api-base-url: ${{ secrets.API_BASE_URL }}
    model: gpt-5.6-terra
    reasoning-effort: xhigh
    github-token: ${{ secrets.GITHUB_TOKEN }}
    bot-name: "@github-actions"
```

### Copilot

```yaml
- uses: MistEO/ai-issue-analysis@main
  with:
    agent: copilot
    api-key: ${{ secrets.API_KEY }}
    model: gpt-5.4
    reasoning-effort: xhigh
    github-token: ${{ secrets.GITHUB_TOKEN }}
    bot-name: "@github-actions"
```

### 多 Key 轮换

`api-key` 支持传入多个 key（每行一个），action 会随机选择一个使用：

```yaml
api-key: |
  ${{ secrets.API_KEY_1 }}
  ${{ secrets.API_KEY_2 }}
  ${{ secrets.API_KEY_3 }}
```

## 输入说明

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `agent` | ✅ | — | AI agent：`copilot` / `claude` / `codex` |
| `api-key` | ✅ | — | Agent 认证密钥，支持多个（每行一个，随机选取） |
| `github-token` | ✅ | — | 用于创建和更新 Issue 评论 |
| `api-base-url` | | `""` | 自定义 API 端点，建议通过 `secrets.API_BASE_URL` 传入 |
| `model` | | `""` | 模型名 |
| `agent-package` | | `""` | 自定义 npm 包名，留空使用 agent 默认值 |
| `reasoning-effort` | | `xhigh` | 思考/推理等级。Claude: low/medium/high/xhigh/max；Codex: low/medium/high/xhigh/max/ultra；Copilot: low/medium/high/xhigh（max/ultra→xhigh）。空字符串则不设置 |
| `agent-extra-args` | | `""` | 额外 CLI 参数 |
| `issue-number` | | `""` | Issue 编号，通常自动推断 |
| `bot-name` | | `""` | 从评论正文中剥离的 bot mention |
| `initial-comment-body` | | 见 action.yml | 开始分析时的评论正文 |
| `action-link-text` | | `GitHub Action 运行记录` | 评论中的运行链接文字 |
| `details-summary` | | `点击此处展开分析过程` | 折叠块标题 |
| `prompt-template` | | 见 action.yml | 基础提示词模板 |
| `comment-prompt-template` | | 见 action.yml | 评论补充要求模板 |
| `stream-update-interval-seconds` | | `30` | 流式更新间隔（秒） |
| `answer-file` | | `answer.md` | Agent 写入最终结论的文件路径 |
| `checkout-repository` | | `true` | 是否自动 checkout |
| `process-error-message` | | 见 action.yml | 分析过程错误的回退消息 |
| `result-error-message` | | 见 action.yml | 结论缺失时的回退消息 |
| `extra-comment-content` | | `""` | 追加到每次评论末尾的额外内容 |

### 模板变量

- `{{issue_number}}` — Issue 编号
- `{{answer_file}}` — 结论文件路径
- `{{comment_body}}` — 触发评论的正文（去除 bot mention 后）
- `{{repository}}` — 仓库全名（owner/repo）
- `{{event_name}}` — 触发事件名

## 输出说明

| 输出 | 说明 |
|------|------|
| `issue-number` | 实际解析出的 Issue 编号 |
| `comment-id` | 创建并持续更新的评论 ID |
| `comment-url` | 评论 URL |
| `analysis-prompt` | 最终传给 agent 的 prompt |
| `agent-output` | 完整执行日志（含启动参数、prompt、agent 输出） |
| `final-conclusion` | Agent 写入的最终结论 |

> `analysis-prompt`、`agent-output`、`final-conclusion` 过长时会截断；完整内容从 artifacts 获取。

## 上传产物

- `agent-output-issue-<N>-comment-<ID>` — 完整执行日志
- `final-conclusion-issue-<N>-comment-<ID>` — 最终结论

## Skill 配合

- action 负责 GitHub Actions 编排、评论更新、agent CLI 调用和 prompt 拼接，不内置项目领域知识
- 建议配套 `.claude/skills/` 下的 issue 分析 skill（通用版已包含在本仓库）
- Skill 一般覆盖：读取 issue 正文和评论 → 定位并下载日志附件 → 建立时间线 → 回溯代码和文档做归因
- 最佳实践参考：[MaaEnd](https://github.com/MaaEnd/MaaEnd/blob/v2/.claude/skills/maaend-issue-log-analysis/SKILL.md)、[MaaAssistantArknights](https://github.com/MaaAssistantArknights/MaaAssistantArknights/blob/dev-v2/.claude/skills/maa-issue-log-analysis/SKILL.md)

## 行为说明

- action 内部自动 checkout 调用方仓库（可通过 `checkout-repository: false` 关闭）
- 自动安装对应 agent 的 CLI
- Claude 和 Codex 会自动处理 `.claude` / `.codex` skill 目录的互联（symlink）
- 先创建一条评论，然后在分析过程中持续流式更新
- 最终评论包含结论 + 完整分析过程折叠块 + Actions 运行链接
- 上传 agent 输出和最终结论两个 artifacts
