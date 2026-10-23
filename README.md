# axure-skill

在 Windows 后台生成和修改 **原生可编辑的 Axure RP9 原型**，通过数值控制布局与交互，不接管编辑器窗口，不占用桌面鼠标键盘。

An agent-independent skill following the Agent Skills format. Create and edit native Axure RP9 prototypes on Windows without desktop input automation. Supports page navigation, conditional interactions, nested dynamic panels, variables, repeaters, and native HTML export. **Only Axure RP 9.0.0.3744 is currently supported.**

这是遵循 [Agent Skills 开放格式](https://agentskills.io/specification) 的通用 skill，指令和运行接口不依赖任何 Agent 厂商。支持该格式的宿主可直接加载；有文件读取和终端能力的其他 Agent 也可读取 SKILL.md 并调用同一 Python CLI。没有常驻服务，不需要模型厂商 SDK 或 MCP。

## 能做什么

- 精确创建多页面、文字、形状、按钮、表单与常用控件。
- 写入原生页面跳转、条件分支、多动作事件、全局变量和表达式。
- 创建多状态及嵌套动态面板、切换状态、显隐与 Lightbox 弹窗。
- 创建中继器数据及 Item 绑定，执行筛选和排序。
- 设置位置、尺寸、透明度、旋转、聚焦、勾选、禁用与交互样式。
- 读取现有工程，修改面板内部控件和控件事件，另存为新 `.rp`。
- 调用 Axure 自身的 HTML 生成器，导出真实交互原型，阻止生成后自动打开浏览器。

开发环境已执行 26 步 HTML 运行检查，覆盖主交互示例、控件动作和已有工程修改；测试计划包含在 `examples/` 中。适配器仍未覆盖 Axure 全部功能，母版、Adaptive Views、自定义图片资源、完整 table/tree/menu 数据及团队工程等尚无完整高层接口。详见 [能力与验证范围](references/capabilities.md)。

## 环境要求

| 项目 | 要求 |
|---|---|
| 系统 | Windows；当前验证环境为 64 位 Windows |
| Axure | 自行安装 **Axure RP 9.0.0.3744**，其他 build、RP10/11 暂不支持 |
| Python | 已验证 Python 3.12；生成 RP/HTML 无第三方 Python 依赖 |
| 编译与辅助进程 | Windows .NET Framework 4 C# 编译器、Windows PowerShell；辅助程序自动编译为 x86 |
| 官方只读 API | 可选；独立核验、PNG 渲染和基础 smoke test 需要 RP9 的 `Axure.Document.dll` |
| HTML 运行检查 | 可选；Node.js 20+、Playwright 与 Chromium |

`doctor` 对 `AxureRP9.exe` 做精确 SHA256 检查，避免将私有类型映射误用到其他版本。项目不包含 Axure 安装程序、官方 DLL、默认控件库或其提取缓存，也不绕过 Axure 许可证。

## 安装到你的 Agent

仓库根目录 **`axure-skill/` 本身就是完整的 skill**，`README.md` 与 `SKILL.md` 直接放在根目录，没有额外的 `skills/` 包装层。各宿主共用相同指令、脚本、示例和能力。

在仓库根目录打开 PowerShell，使用不依赖任何 Agent SDK 的通用安装脚本，并明确选择宿主扫描的目标目录。例如，安装到支持共享 `.agents/skills` 目录的宿主：

```powershell
python .\scripts\install_skill.py --target "$env:USERPROFILE\.agents\skills\axure-skill"
```

也可按自己使用的宿主选择目录，**不需要全部安装**：

```powershell
# Claude Code 的个人 skills 目录
python .\scripts\install_skill.py --target "$env:USERPROFILE\.claude\skills\axure-skill"

# Cursor 的个人 skills 目录
python .\scripts\install_skill.py --target "$env:USERPROFILE\.cursor\skills\axure-skill"

# OpenCode：安装到你的目标工程中，替换工程路径
python .\scripts\install_skill.py --target 'D:\MyProject\.opencode\skills\axure-skill'

# 任意宿主的自定义路径：只列出文件，不执行复制
python .\scripts\install_skill.py --target 'D:\AgentSkills\axure-skill' --dry-run
```

安装脚本只复制可分发的 skill 源文件，拒绝覆盖已有目标，不复制缓存、预编译程序、第三方组件或生成工程，也不更改宿主配置。目标目录必须叫 `axure-skill`。CLI、示例和文档均可从其他工作目录调用，不要求在特定 Agent 内运行。

Claude Code、Cursor、OpenCode、Codex 的目录说明、官方文档链接、普通 Agent 的接入模板和执行条件见 [Agent 接入说明](references/agent-integration.md)。`agents/openai.yaml` 只是可选展示元数据，不是核心依赖。

加载后可以用自然语言请求：

> 使用 axure-skill 做一个订单管理原型，包含列表页和详情页、状态切换、条件弹窗，以及中继器筛选排序，保存为可编辑 RP 文件并导出 HTML 验证。

没有 skill 加载器的 Agent，可以直接读取根目录的 `SKILL.md` 并执行其中的 CLI。**跨 Agent 不等于跨运行环境**：完整生成仍需要能访问 Axure 安装和目标文件的 Windows 执行器。仅有云端 Linux 容器或没有命令工具的聊天 Agent，不能直接操作用户本地 Axure。

## 直接使用 CLI

也可以不安装 skill，直接在仓库根目录的同一个 PowerShell 会话中运行：

```powershell
$skill = $PWD.Path
python "$skill\scripts\axure_skill.py" doctor

# Axure 位于其他安装目录时，可设置环境变量：
# $env:AXURE9_DIR = 'D:\Apps\Axure RP 9'
# 或在子命令之前加 --axure-dir 'D:\Apps\Axure RP 9'

# 生成复杂交互示例；首次运行会从自己的 Axure 安装中生成本地缓存
python "$skill\scripts\axure_skill.py" create --spec "$skill\examples\advanced.json" --output .\outputs\advanced.rp

# 导出真实 HTML，不启动浏览器，不上传到云端
python "$skill\scripts\axure_skill.py" export-html .\outputs\advanced.rp --output .\outputs\advanced-html

# 读取页面、嵌套面板、控件、变量及中继器数据
python "$skill\scripts\axure_skill.py" inspect .\outputs\advanced.rp

# 修改面板内文字与现有控件事件，保留源文件
python "$skill\scripts\axure_skill.py" edit --input .\outputs\advanced.rp --patch "$skill\examples\advanced.edit.json" --output .\outputs\advanced-edited.rp
```

`.rp` 可以在 Axure 中继续编辑。HTML 输出目录应完整保留，入口是 `start.html`；无头运行检查会自行启动临时本机 HTTP 服务。生成工程及伴随文件不覆盖已有结果，HTML 输出目录必须是新目录；重复运行请更换名称。

## 官方核验和预览

从 [Axure 官方 API 页面](https://www.axure.com/axure-rp-api/) 获取 **RP9** 只读 API，将其中 `Axure.Document.dll` 放到：

```text
.cache/public-api/Axure.Document.dll
```

这里的 `.cache` 相对于 `axure-skill/` 根目录；源码运行和安装后的布局相同。该目录已被 Git 忽略，第三方组件不随仓库分发。官方 API 获取路径与已验证 DLL 的 SHA256 见 [依赖配置](references/setup.md)。

```powershell
python "$skill\scripts\axure_skill.py" doctor
python "$skill\scripts\axure_skill.py" verify .\outputs\advanced.rp --render-dir .\outputs\native-preview
python "$skill\scripts\smoke_test.py"
```

**RP9 官方 API 的整页 PNG 在已验证环境中会漏画动态面板内容。** 顶层面板的独立状态 PNG 可以显示该状态；复杂原型应检查实际 HTML 的浏览器截图及交互，不能只看官方整页 PNG。

## 可选：复现真实交互检查

此部分只对 HTML 运行测试需要，不是生成 RP/HTML 的前置条件。在实际 skill 根目录安装本地测试依赖；以下命令接续上面的 `$skill` 变量：

```powershell
Push-Location $skill
npm install
npx playwright install chromium
Pop-Location

node "$skill\scripts\runtime_test.cjs" .\outputs\advanced-html "$skill\examples\advanced.test.json" .\outputs\advanced.png
```

测试使用无头浏览器 DOM 交互，不移动桌面鼠标，不向 Windows 桌面发送键盘输入。临时 HTTP 服务仅监听 `127.0.0.1`，结束后关闭。stdout 输出 JSON 报告，stderr 显示当前步骤；任何断言或页面脚本错误都会导致非零退出。

其他两组测试：

```powershell
python "$skill\scripts\axure_skill.py" create --spec "$skill\examples\controls.json" --output .\outputs\controls.rp
python "$skill\scripts\axure_skill.py" export-html .\outputs\controls.rp --output .\outputs\controls-html
node "$skill\scripts\runtime_test.cjs" .\outputs\controls-html "$skill\examples\controls.test.json"

python "$skill\scripts\axure_skill.py" export-html .\outputs\advanced-edited.rp --output .\outputs\advanced-edited-html
node "$skill\scripts\runtime_test.cjs" .\outputs\advanced-edited-html "$skill\examples\advanced.edit.test.json"
```

测试计划分别为 16、7、3 步，必须与对应 spec/patch 一起使用。如需使用已有 Chromium，可通过 `AXURE_TEST_BROWSER` 指定其完整路径。

## 项目结构

```text
axure-skill/
├── README.md                          安装与使用说明
├── SKILL.md                           通用 Agent Skills 入口
├── LICENSE                            MIT
├── package.json                       可选 Playwright 测试依赖
├── scripts/                           CLI、安装器、原生桥接与验证脚本
├── examples/                          原型 spec、patch 和测试计划
├── references/                        格式、接入、依赖、能力和研究说明
├── agents/openai.yaml                 可选宿主展示元数据
├── tests/test_install_skill.py         安装、隔离与文件筛选检查
├── .gitignore
└── .gitattributes
```

运行时会在实际 skill 目录生成 `.cache/`、编译后的辅助程序，并在指定工作区生成输出文件。这些内容不属于源码分发文件；提交前可用 `git status --short` 检查。不要提交 Axure 自身组件、提取的控件库、私有工程、反编译资料或本机环境信息。

## 开发与适配

在源码仓库根目录运行通用安装器测试；它只使用 Python 标准库，不需要 Axure 或任何宿主 Agent：

```powershell
python -m unittest discover -s tests -v
```

测试覆盖同一包安装到不同目录、拒绝覆盖、dry-run 不写文件及排除运行产物。它不等于在每个 Agent 应用中分别实测。原型引擎已通过本机原生和无头运行检查，具体宿主自动发现及权限由宿主负责。


- [Spec 与 patch 格式](references/spec.md)
- [事件、表达式、面板、中继器与原生扩展口](references/interactions.md)
- [支持范围与未完成部分](references/capabilities.md)
- [依赖与版本校验](references/setup.md)
- [实现依据与已验证的原生约束](references/research.md)

升级 Axure 不能只修改版本号或移除 hash 检查；需要重新定位私有模型、适配引用关系，并通过原生保存/回读、官方语义核验及实际 HTML 运行检查。尚未封装的功能可以从 `models` / `native` 扩展口继续适配，但不能将模型存在当作功能已支持。

标准与接入资料：[Agent Skills](https://agentskills.io/specification)、[Claude Code](https://code.claude.com/docs/en/skills)、[Cursor](https://cursor.com/docs/context/skills)、[OpenCode](https://opencode.ai/docs/skills/)。

## License

本项目原创源码、skill 指令和文档采用 [MIT License](LICENSE)。Axure 及其官方 API、默认库仍遵循各自许可证；Playwright 为可选的外部依赖，不打包到本仓库。本项目是独立适配工具，并非 Axure 官方产品。
