# 交互、容器与运行验证

完整工程见 `examples/advanced.json`；下拉控件/动作/悬停样式见 `examples/controls.json`。

## 事件与条件

控件 `events` 使用 Axure 原生事件名称，`OnClick`、`OnMouseEnter`、`OnTextChange`、`OnItemLoad` 等实际可用名称通过 `models --enum Axure.Constants.IxEventType` 查询。枚举存在不证明适合当前控件或已实际执行验证。

页面加载使用 **OnLoad**。此适配器将页面/状态上的 OnPageLoad 别名转换为 OnLoad，不能同时写二者；RP9 的另一个 OnPageLoad 枚举直接导出后不会触发正常页面加载流程。

事件值可为动作列表，或带条件的 case 列表：

```json
{"OnClick":[
  {"name":"输入为空","if":{"op":"Equals","left":{"widget_text":"name_input"},"right":""},"actions":[
    {"type":"set_text","target":"status","value":"请输入名字"}
  ]},
  {"name":"否则","actions":[
    {"type":"set_variable","variable":"UserName","value":{"widget_text":"name_input"}},
    {"type":"set_text","target":"status","value":{"var":"UserName"}}
  ]}
]}
```

case 字段为 name、if、new_if、actions。第一个 case 默认开始 if 组，后续默认 else if/else；`new_if:true` 开始独立 if 组。一个事件内使用同一种动作/case格式。输入校验错误会拒绝发布文件。

## 表达式

| JSON 值 | 含义 |
|---|---|
| 字符串、数字、布尔值 | 原生文字或布尔表达式；数值使用场景由 Axure 运行时转换 |
| {"widget_text":"input_id"} | 读取控件文本 |
| {"var":"UserName"} | 读取全局变量值 |
| {"widget":"widget_id"} | 控件路径 literal |
| {"variable_ref":"UserName"} | 变量标识引用，通常由 set_variable 内部使用 |
| {"op":"Equals","left":...,"right":...} | 原生 BinaryExpr；其他运算名查询 Axure.Platform.LogicalComparison |
| {"call":"FunctionName","args":[...]} | 原生函数调用，名称必须由本机模型/实际导出证实 |
| {"expr":"欢迎，[[UserName]]"} | Axure 字符串表达式与变量绑定 |
| {"expr":"[[Item.Price > 100]]","repeater":"orders"} | 带中继器数据集作用域的表达式 |
| {"native_model":"MODEL","fields":{...}} | 经导出白名单校验的原生表达式模型 |

变量要在顶层 variables 声明。`Item.Column` 引用必须指定 repeater；当前显式绑定列名建议使用英文标识符。自定义原生函数/表达式仅有入口不等于已验证其全部语义。

## 动态面板

```json
{
  "id":"content","kind":"panel","x":48,"y":160,"width":600,"height":300,
  "initial_state":"详情",
  "states":[
    {"name":"概览","widgets":[
      {"id":"overview","kind":"text","x":24,"y":24,"width":400,"height":40,"text":"概览"}
    ]},
    {"name":"详情","widgets":[
      {"id":"detail","kind":"text","x":24,"y":24,"width":400,"height":40,"text":"详情"}
    ]}
  ]
}
```

state 允许 name、widgets、events；widgets 可以继续包含 panel，实现嵌套。状态名称在同一面板内唯一。初始状态通过原生状态顺序实现。panel 未指定 states 时生成空 State1。

可选 hidden、fit_to_content、fixed、scrollbars，后者为原生值，应先查模型而不是猜枚举。fixed、滚动条等尚未逐项验证。状态内坐标相对面板，跨状态交互目标仍使用该页面内唯一控件 ID。

## 中继器

```json
{
  "id":"orders","kind":"repeater","x":48,"y":160,"width":600,"height":200,
  "columns":["Name","Price"],
  "data":[{"Name":"订单 A","Price":"120"},{"Name":"订单 B","Price":"240"}],
  "item_widgets":[
    {"id":"row_name","kind":"text","x":0,"y":0,"width":300,"height":42,"text":"名称"}
  ],
  "events":{"OnItemLoad":[
    {"type":"set_text","target":"row_name","value":{"expr":"[[Item.Name]]","repeater":"orders"}}
  ]}
}
```

columns 必须非空、唯一；每行只可包含已声明列，缺失值为 ""，数据以文本保存。原生数据集与 OnItemLoad 绑定均写入 `.rp`。当前未封装全部 repeater 布局、分页设置和增删改行参数；不要用简单 JSON 行替代真实绑定。

## 动作字段

所有动作有 type；target 为同页控件 ID。下列标注「多目标」的动作也可用非空 targets 列表，不能同时给 target。

正确的多目标写法为 `{"type":"show","targets":["a","b"]}`，不是 `"target":["a","b"]`。

| type | 字段与默认值 |
|---|---|
| open_page | page（创建为 spec 页面 ID，编辑为名称/GUID），window=Current |
| open_url | url（可为表达式），window=Current |
| back / reload / close | 前两项可设 window；close 关闭当前窗口，由浏览器规则决定效果 |
| wait | ms，毫秒 |
| set_text | target、value（文字或表达式）；自动区分普通文字与表单 |
| set_variable | variable、value |
| set_selected | target、value（布尔值）；使用原生 SetCheckState |
| set_panel_state | target、state；mode=Diagram、value=""、show=true、duration=0、enter_animation/exit_animation=None |
| show / hide / toggle | 多目标；duration=0、animation=None、show_type=None；弹窗可设 show_type=Lightbox |
| move | 多目标；x、y（表达式），mode=Location、duration=0 |
| resize | 多目标；width、height（表达式），anchor="top left"、duration=0 |
| opacity | 多目标；value 是 **0–100百分比**，duration=0；50 对应 CSS opacity 0.5 |
| rotate | 多目标；degrees、clockwise=true、duration=0、offset_x=0、offset_y=0、anchor=center |
| enable / disable | 多目标 |
| front / back_order | 多目标；层级操作 |
| focus | target、select_text=false |
| scroll_to | target、duration=0、direction=1（原生方向值） |
| filter | 多目标；value（带 repeater 作用域表达式）、name=filter、replace=true |
| sort | target、column、ascending=true、toggle=false、sort_type=1（数值）、name=sort |
| items_per_page | 多目标；value=10、unlimited=false；已封装但未逐项执行测试 |
| repeater_page | 多目标；value=1、mode=0；已封装但未逐项执行测试 |
| function | name、args；直接原生函数扩展 |

动画/动作模式应使用 `models --enum FULL_NAME` 中实际的值，例如 Axure.DocumentModel.Expressions.FadeEasingType、MoveBehavior、Axure.DocumentModel.Interaction.SetStateType、ShowType、LinkType。

## 原生扩展口

```powershell
python scripts/axure_skill.py models
python scripts/axure_skill.py models --model SetPanelStateInfo
python scripts/axure_skill.py models --enum Axure.Constants.IxEventType
```

本机导出目录包含79个可构造模型模板及其字段；另2个模型构造失败，不能用。catalog 是成功/失败清单，不是功能支持承诺。

普通封装的映射动作可设 `native_info` 覆盖其 info 原生字段。未封装动作支持：

```json
{"type":"native","model":"IxSetOpacityAction",
 "target":"shape","paths_field":"Paths","infos_field":"Infos",
 "info_model":"SetOpacityInfo","info":{"Opacity":{"$expr":50}}}
```

也可省略 info_model 并用 fields 配置 action 自身。字段必须存在，模型名称必须在已导出白名单内。值可为标量、原生结构；`{"$expr":...}` 创建表达式引用，`{"$widget_path":"id"}` 创建控件路径引用。此入口尚不自动构造任意引用列表、图片资源、Adaptive Views 或母版依赖。扩展后另存新输出；只有用户明确要求检查时，才按检查范围执行官方加载或受影响流程。未运行验证时如实说明，不能仅凭模型名承诺效果已验证。

## 真实 HTML 运行测试

仅在用户明确要求测试、检查或验收时使用本节；默认生成 RP/HTML 不编写测试计划、不调用本脚本或浏览器探测。根据用户指定的视觉/交互范围检查，见 [validation.md](validation.md)。

`scripts/runtime_test.cjs` 使用 Playwright 无头 Chromium 和退出即关闭的本机回环 HTTP 服务。安装 Node/Playwright/浏览器仅在运行此测试时需要；生成 RP/HTML 无此依赖。本机配置见 setup 文档。

```powershell
node scripts/runtime_test.cjs --doctor
node scripts/runtime_test.cjs 'C:\path\prototype-html' examples/advanced.test.json 'C:\path\preview.png'
```

`--doctor` 只检查已有 Playwright 和浏览器，不执行安装；ok:false 时按实际需要配置依赖，RP/HTML 生成仍可继续。

测试计划结构为 `{"steps":[...]}`，可指定 viewport。step 支持 open（页面名）、click、hover、target、fill、text/texts、visible、value、checked、disabled、options、url、style（CSS computed style）、visual_style（内部 _div 样式）、rotation（角度）、focused、wait（毫秒）、screenshot。`visible` 会等待显隐完成（默认最多 8 秒），避免异步动作尚未结束就误报失败；无需为正常显隐手写固定 sleep。fill 前在浏览器内点击输入框，以触发 Axure 提示清除逻辑。页面脚本错误将使测试失败。

`screenshot:true` 保留原行为，写入命令的预览 PNG 参数；`screenshot:"相对路径.png"` 保存到测试计划所在目录下的指定位置。同一次运行可以保存多个页面/状态/视口截图，JSON 报告的 `screenshots` 列出实际文件。默认截整页；同一步加 `screenshot_target:"画面面板ID"` 可直接截取该控件的可见区域，适用于手机画面，省去另写裁剪脚本。目标必须唯一且可见。局部截图不代替溢出/居中检查，宽屏布局继续使用 `page_alignment` 和 `canvas` 断言。例如：

```json
{"viewport":{"width":390,"height":844},"steps":[
  {"open":"登录","screenshot":"screenshots/login-phone.png","screenshot_target":"screen"},
  {"viewport":{"width":1440,"height":1000},"page_alignment":"center","screenshot":"screenshots/login-wide.png"},
  {"click":"submit","target":"error","visible":true,"screenshot":"screenshots/login-error.png"}
]}
```

上例 `screen` 为原型中固定 390×844 的画面 panel ID，替换成实际控件名；没有该容器时省略 `screenshot_target`。等待 toast 消失等异步状态可直接断言 `visible:false`；`wait` 只用于确有展示时间要求的检查，避免在每次回归中重复等待多余固定时长。

stdout 是 JSON 报告，stderr 显示当前步骤；保存报告作为执行证据。该测试操作无头浏览器 DOM，不使用桌面输入。示例 test 计划必须与对应 spec 一起使用。
