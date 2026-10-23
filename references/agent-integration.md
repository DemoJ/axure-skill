# 不同 Agent 的接入

本包遵循 [Agent Skills 开放格式](https://agentskills.io/specification)：`SKILL.md` 使用通用 frontmatter，附带 scripts、references 和 examples。标准 skill 目录为 `axure-skill`，与 `name: axure-skill` 一致。

指令没有预设宿主工具名、专用 SDK、MCP 客户端、自动注入变量或统一 slash 命令。运行时使用宿主已有的文件读写和终端/进程能力。`agents/openai.yaml` 是可选展示元数据，其他宿主可忽略；删除该文件不影响 CLI。

## 原生支持 Agent Skills 的宿主

仓库根目录就是完整的 `axure-skill`，README 与 SKILL.md 位于同一层，无需进入内层 skill 目录。可用根目录的 `scripts/install_skill.py` 安装，也可将整个目录放进宿主支持的 skills 位置。以下路径中的 `~` 表示用户主目录，项目级路径相对于要使用该 skill 的工程。

| 宿主 | 项目级示例 | 用户级示例 | 依据 |
|---|---|---|---|
| Claude Code | `.claude/skills/axure-skill` | `~/.claude/skills/axure-skill` | [官方 skills 文档](https://code.claude.com/docs/en/skills) |
| Cursor | `.cursor/skills/axure-skill` 或 `.agents/skills/axure-skill` | `~/.cursor/skills/axure-skill` 或 `~/.agents/skills/axure-skill` | [官方 Agent Skills 文档](https://cursor.com/docs/context/skills) |
| OpenCode | `.opencode/skills/axure-skill` 或 `.agents/skills/axure-skill` | `~/.config/opencode/skills/axure-skill` 或 `~/.agents/skills/axure-skill` | [官方 skills 文档](https://opencode.ai/docs/skills/) |
| Codex | 使用宿主配置的 skill 目录 | `~/.codex/skills/axure-skill`；自定义 CODEX_HOME 时为其 `skills/axure-skill` | 开发环境验证过相同文件布局与 CLI；自动发现由宿主负责 |
| 其他支持该格式的 Agent | 按其宿主说明选择目录 | 按其宿主说明选择目录 | 格式通用不代表自动发现目录相同 |

安装方式核对日期：2026-10-23。宿主可能改变自动发现、权限或刷新方式，应以其当前版本说明为准。上表前三项为官方文档支持的目录，不代表已经在这些 Agent 应用内逐一实测；本项目验证的是同一安装负载和 CLI 的运行。

同一 skill 放到多个会被同时扫描的位置，可能产生重复发现；为每个宿主选择一个位置即可。加载后的自然语言请求可以相同；显式调用方式由宿主决定，例如有的使用 `/axure-skill`，有的使用 `$axure-skill`，不要把其中一种当作通用协议。

## OpenCode 中的常规绘制

使用加载时返回的 skill 根目录调用 CLI，不需要为普通页面先阅读桥接源码或扫描整个缓存。样式参数用 `styles --property OUTER_SHADOW` 等命令查询，常用写法见 spec 的外观速查。`create` 已包含原生回读校验；成功后先给出 RP 路径，HTML 测试可在同一计划中保存多张截图。

Playwright/Chromium 只在运行 HTML 检查时需要，先用 `runtime_test.cjs --doctor` 检查现有安装；缺少官方 API 时跳过可选 `verify`。CLI 的 `elapsed_seconds` 只计本地执行，宿主显示的整轮耗时还包含模型等待、生成和结果检查。更新 skill 后，新会话重新加载；进行中的会话应重新读取已更新的 SKILL.md，避免继续遵从先前注入的旧说明。

## 没有 skill 加载器，但有文件和命令工具的 Agent

不需要转换成厂商专有配置。把本目录放在任意可访问的位置，给 Agent 以下指令，并替换真实路径：

> 读取 `D:/AgentSkills/axure-skill/SKILL.md` 并使用该工作流制作 Axure 原型。所有 scripts、references、examples 路径相对于此文件所在目录解析。使用本机 Windows 的文件及终端工具执行 Python CLI，先运行 doctor。根据需求写 JSON spec，生成可编辑 RP 并导出 HTML；按需执行交互检查。不要用桌面鼠标键盘自动化替代这些接口。

宿主可将这段路径提示写进自己的项目指令，但不要默认向用户的 CLAUDE.md、AGENTS.md、rules 或全局配置中追加内容。

在工具框架中封装时，使用参数列表启动进程，避免将用户输入拼进 shell 命令：

```python
import json
import subprocess
from pathlib import Path

skill_root = Path(r'D:\AgentSkills\axure-skill')
result = subprocess.run(
    ['python', str(skill_root / 'scripts/axure_skill.py'), 'doctor'],
    capture_output=True, text=True, encoding='utf-8',
)
if result.returncode:
    raise RuntimeError(result.stderr)
report = json.loads(result.stdout)
if not report.get('ok'):
    raise RuntimeError(report)
```

生成/编辑/导出等子命令同样使用参数列表，并检查退出码和 JSON。不需要使用 OpenAI、Anthropic 或其他模型 SDK。

## 仅有云端容器或没有执行工具的 Agent

可以读取技能并生成 spec，但不能直接读取用户电脑上的 Axure 安装或调用其序列化器。完整执行需要能访问该 Windows 环境的终端、远程执行连接或其他由用户配置的执行器。把 skill 同步到云端不会自动同步安装的软件或赋予本机访问权限。

因此本项目的通用性是**宿主无关的技能格式与 CLI 接口**，运行平台仍是 Windows / Axure RP 9.0.0.3744。当前包不包含远程服务、MCP server、远程认证或端口开放功能。
