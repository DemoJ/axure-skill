---
name: axure-skill
description: Create and edit native Axure RP9 prototypes with precise layouts and complex interactions. Use for Axure prototyping without desktop input automation. 在 Windows 后台创建、修改原生可编辑的 Axure RP9 原型，支持精确布局、页面跳转、条件事件、嵌套动态面板、变量和中继器，并导出真实交互 HTML，不占用鼠标键盘。用于 Axure 原型制作和批量修改；仅适配已验证的 RP 9.0.0.3744。
license: MIT
---

# Axure Skill

这是遵循 Agent Skills 格式的通用技能。使用 Agent 自己的文件读取、文件写入与终端/进程工具调用本地 CLI 和本机 Axure 原生序列化器生成 `.rp`，不接管编辑器窗口，不发送桌面键鼠事件。原生 HTML 由 Axure 自身生成器导出，可用无头浏览器执行真实交互。无需常驻 MCP 服务。

## 开始

执行环境要求 Windows、Python 3.12、.NET Framework 4、Windows PowerShell 和 Axure RP 9.0.0.3744。

以本 `SKILL.md` 所在目录为 skill 根目录，不假定当前工作目录或任何厂商安装路径。将下方路径替换为实际根目录；所有 references/examples/scripts 路径都相对于该根目录解析。

```powershell
$axureSkill = 'D:\AgentSkills\axure-skill' # 替换为当前 SKILL.md 的所在目录
python "$axureSkill\scripts\axure_skill.py" doctor
```

宿主不必提供专用 skill 工具：可直接读取本文件，按需读取引用文档，然后用终端执行上述 CLI。不要依赖厂商特有的工具名、动态变量或 slash 命令。安装位置与宿主接入方式见 [references/agent-integration.md](references/agent-integration.md)。

执行器必须能访问本机 Windows、已安装的 Axure 和目标文件；仅能访问云端容器的 Agent 无法直接操作用户本地 Axure，需要由用户提供能在这台 Windows 上执行命令的连接。`agents/openai.yaml` 只是可选的宿主展示信息，其他 Agent 可忽略，不参与运行。

CLI 的 stdout 是 JSON，成功时含 `ok:true`；失败时非零退出并在 stderr 返回 `ok:false/error`。同时检查退出码和 JSON，不能只看输出文件存在。

`doctor` 检查准确的 Axure 二进制 SHA256；版本不符时报告限制，不绕过检查。依赖问题读 [references/setup.md](references/setup.md)。此适配器不是 RP10/11 通用接口。

## 创建与交互

1. 按 [references/spec.md](references/spec.md) 写 UTF-8 JSON spec，使用稳定的页面/控件 ID。涉及事件、面板或数据时再读 [references/interactions.md](references/interactions.md)。简单布局参考 `examples/login.json`，复杂原型参考 `examples/advanced.json`，表单/动作/状态样式参考 `examples/controls.json`。
2. 在用户工作区选择新输出路径，生成并核验：

```powershell
python "$axureSkill\scripts\axure_skill.py" create --spec 'C:\path\design.json' --output 'C:\path\prototype.rp'
python "$axureSkill\scripts\axure_skill.py" verify 'C:\path\prototype.rp' --render-dir 'C:\path\native-preview'
python "$axureSkill\scripts\axure_skill.py" export-html 'C:\path\prototype.rp' --output 'C:\path\prototype-html'
```

3. 检查真实视觉结果。复杂交互应对导出的 HTML 做关键流程测试，再交付 `.rp`、预览和验证结果。用 `scripts/runtime_test.cjs` 执行无头测试，方法见 interactions 文档。测试仅使用浏览器内部输入，不移动桌面鼠标。

`create` 会做原生保存/回读，核对面板内和中继器项内的控件文字、保存坐标及数据；官方 API 可用时再核对页面、面板状态中的控件和字体。它不能代替交互运行测试。旁边保留 `.spec.json`、`.manifest.json`、`.verification.json` 方便迭代。

**官方 API 的整页 PNG 会漏画动态面板内容**；单独状态 PNG 可以显示该状态。完整复杂预览使用真实 HTML 的无头浏览器截图，不能把空白区域当作工程正常的证据。

HTML 导出在临时工程副本中执行，完成时阻止生成器自动打开浏览器。返回 `browser_opened:false`、`source_unchanged:true`；输出目录必须是新的。导出超时会停止独立辅助进程，不继续反复重试。不使用旧研究用的 HtmlProbe 程序。

## 修改已有工程

先 `inspect` 获取真实页面/控件名称或 GUID，再另存新文件：

```powershell
python "$axureSkill\scripts\axure_skill.py" inspect 'C:\path\source.rp'
python "$axureSkill\scripts\axure_skill.py" edit --input 'C:\path\source.rp' --patch 'C:\path\changes.json' --output 'C:\path\revised.rp'
```

Patch 可修改文字、位置、样式，也可替换控件的完整 `events`；`events:{}` 清除交互。支持递归定位面板状态内控件和中继器项。选择器有歧义时用 GUID，同一控件的改动合并为一条 update。示例见 `examples/advanced.edit.json`。复杂编辑后重新导出并测试受影响流程。

读取的是已保存磁盘文件。无法读取编辑器未保存修改，也不自动保存或关闭用户的 Axure。原文件保留；不能将重新生成 spec 称为对任意 RP 工程的无损结构编辑。添加/删除结构时，自己的 spec 工程优先更新 spec 重建。

## 扩展与边界

查看 [references/capabilities.md](references/capabilities.md) 区分已实际执行、仅有原生封装、尚未支持的功能。不能宣称全功能已覆盖，也不要遇到缺项就退回一张静态图。

未封装动作可通过 `models` 查询本机真实模型/枚举，用 `native` 动作、原生表达式和属性扩展。必须补齐原生引用关系，并验证输出与真实运行；导出成功本身不证明交互正确。母版、Adaptive Views、自定义图片源及 table/tree/menu 内容、团队工程尚无完整高层接口。

维护桥接或编译器后运行 `scripts/smoke_test.py`；交互改动运行相应 examples 测试计划。实现证据与关键原生约束见 [references/research.md](references/research.md)。
