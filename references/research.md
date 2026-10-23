# 调研结论与实现证据

调研日期：2026-10-23。开发验证环境安装 Axure RP 9.0.0.3744。

## 为什么采用本地 skill + CLI

Axure 官方 [RP API](https://www.axure.com/axure-rp-api/) 是读取接口，适合读取页面/控件/样式和后台渲染，不能直接创建或写回 RP 文件。官方论坛也有 [写入 API 问题](https://forum.axure.com/t/is-it-possible-to-write-to-an-axure-project-file-using-the-api/29080) 与 [命令行构建讨论](https://forum.axure.com/t/build-commandline-tools/76464)。不能将只读 API 包装后声称具备绘图能力。

现有 [axure-cli 调研项目](https://leileqithu.github.io/reverse-cli-anything/axure-cli/README.html) 使用 RP11 的 .NET startup hook 思路，不能直接套用到本机 RP9 的 .NET Framework 程序。

[AxureDowngrade](https://github.com/muxia0396/AxureDowngrade) 提供了 RP 格式研究线索（参考 commit `5a4b8ff528f1a4eb88fdb91d7d049bbf5f9a148d`），但版本映射不同，且其许可证为 PolyForm Noncommercial。本实现没有复制该项目源码，也不将其作为运行依赖；采用本机独立反射映射和自写桥接代码。

因此实现一个可独立调用的本地 CLI：skill 将自然语言需求转换为声明式 JSON，再由 CLI 写出真实 `.rp`。这已经达到不占用桌面输入设备的目标，无需先搭建 MCP。以后若需要其他客户端访问，可在相同 CLI 外封装 MCP，但那只是调用层，不会自动扩展原生控件/交互能力。

## 写入与验证链

1. 仅读取本机安装的默认控件库，将原生对象包导出为带类型的中间数据。
2. 克隆页面和控件，生成 GUID 并更新引用、sitemap、样式缓存、富文本与属性。
3. 在独立 x86 进程加载本机 Axure 的原生序列化器，保存各对象包，逐包原生回读校验，重建 RP9 容器。
4. 从生成文件重新读取并核对目标文字、坐标、尺寸和输入框属性。
5. 用独立的官方只读 API 加载工程和所有页面；创建时再核对页面/控件数量、文字和指定字体。可用原生渲染器生成 PNG 检查视觉。
6. 检查通过后，才将工程和伴随 JSON 发布到用户指定的新文件路径。

不注入正在运行的 Axure 进程，不启动其编辑器窗口，不修改安装文件，不发送键鼠事件。原型由原生控件组成，可在 Axure 中继续编辑。

## 本轮复杂交互实现与证据

交互编译器克隆本机真实模型，构造事件树、case条件、表达式、控件路径、动态面板状态包和中继器数据集。模型 catalog 有81项，79项可构造保存，DummyActionInfo 与 RichTextLiteral 两项失败。模板/枚举来自本机原生序列化结果，没有将79个模板等同于79项已测试功能。

- advanced 示例在实际 HTML 中执行页面加载、跳转、嵌套状态、Lightbox、条件、变量、Item数据绑定、筛选和数值排序，共16步。
- controls 示例执行下拉/listbox选项、悬停样式/圆角、移动/尺寸/透明度/旋转、输入聚焦、勾选与禁用，共7步。
- 编辑示例另验证状态内文字修改与替换已有控件事件，共3步。
- 基础 smoke test 验证两页12控件、原生回读、官方加载/渲染、文字/位置/字体/输入属性修改、源hash不变、拒绝覆盖/无效patch和临时目录清理。

开发时曾实际执行以上测试；发布源码不包含本机 runtime 报告、截图或 Axure 生成产物。复现时请执行对应计划并保存自己的结果。完整范围见 [capabilities.md](capabilities.md)。

## 后台 HTML 导出与弹窗修复

使用本机私有 HTML generator 生成完整的 Axure HTML、JS、CSS及资源，不以自写网页模拟交互。加载临时 RP 副本，运行在独立 x86 辅助进程，不构造编辑器应用对象，也不读写用户的编辑器设置。

RP9 Generate() 末尾会无条件尝试打开浏览器，研究中的早期调用因此弹出 “The browser could not be opened”。正式 NativeExport 在文件生成结束、浏览器启动分支之前的完成事件中取消最后一步，要求该事件确实执行、原生错误字段为空且 start.html 存在；未满足则报错，不发布输出。返回 browser_opened=false，不再调用旧 HtmlProbe。导出具有60秒超时，超时停止该独立进程。

导出在临时目录运行，成功才发布新输出目录，结束比对源文件 SHA256。不会关闭用户现有的 Axure 进程或抢桌面输入。

## 原生结构中已经验证的约束

- `PName.PAGE_ALIGNMENT` 为 26，对应 `DOAName=-1073741798`，位于 `Axure:PageStyle.PropList`；0=left、1=center。写入每页原生样式，HTML 生成器会输出 relative body 与 auto 左右 margin；这与控件文字的 HORIZONTAL_ALIGNMENT 无关。`inspect` 先读单页样式，再读工程 DefaultPageStyle。回归见 presentation 示例与 tests/test_page_alignment.py。
- 编辑画面起始 x=525、宽390 且 PAGE_ALIGNMENT=1 时，原生导出 body 为 left:-525px、width:390px，控件仍保留原生 x=525；该补偿消除演示的左侧空白。编辑居中应直接安排原生坐标，不把演示对齐等同于编辑器位置。DocumentSettings 的 open-tab-package-ids/open-tab-object-ids 与 selected-tab-package-id 可保存首个真实页面的打开状态；本机 UI 保存回读验证了这组字段。
- 所有动态面板状态包（包括深层嵌套）必须平铺在所属 PAGE 的 index.children；设计元数据仍保持嵌套。
- 初始隐藏要同时设置 VisibleFromSettings 与样式 VISIBLE；只改其中一个会造成运行结果错误。
- SetPanelStateInfo 的 state-value 即使在指定状态模式也必须是非空表达式对象；RotateInfo 的 OffsetX/OffsetY 同理。
- GlobalVariableLiteral 是变量标识，读取值要用 GetGlobalVariableValue；set_variable 首参为标识引用。
- 正常页面加载使用 OnLoad，不能直接使用另一个 OnPageLoad 枚举。适配器提供别名转换。
- repeater-scope 引用实际 DataSet；Item列标识、作用域和目标的 repeater-path 必须正确。
- opacity 动作取0–100百分比，50才是CSS 0.5。
- 默认库控件可自带演示事件和自适应样式；新控件清理它们，防止幽灵交互。
- 交互样式除了正确的字典键，还必须设置样式记录自身的 style-name；否则可能只有CSS外观规则而没有正确的运行时状态绑定。
- 字体用 point 保存；复选框/单选框实际显示高度由字体测量，中继器显示范围由行内容计算。

## 验证器限制

官方 API 可以递归读取动态面板状态与控件，但不暴露中继器项内的控件；内部原生回读补充该部分。官方整页 RenderScreenshot 在此版本漏画面板内容，单独渲染面板状态可用。复杂原型的完整截图使用真实 HTML 的无头浏览器输出。

原生保存成功、官方读取成功和运行时正确是不同证据。没有对任意外部复杂工程作全面兼容承诺；母版、Adaptive Views、图片源等仍需要继续构建依赖并验证。
