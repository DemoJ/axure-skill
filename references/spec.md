# RP9 spec 与编辑格式

复杂交互语法见 [interactions.md](interactions.md)，验证范围见 [capabilities.md](capabilities.md)。

## 工程与页面

```json
{
  "title":"订单原型",
  "page_alignment":"center",
  "variables":{"UserName":"访客"},
  "pages":[{
    "id":"home", "name":"首页",
    "events":{"OnLoad":[{"type":"set_text","target":"status","value":{"expr":"欢迎，[[UserName]]"}}]},
    "widgets":[
      {"id":"status","kind":"text","x":48,"y":40,"width":600,"height":48,"text":"欢迎","font_size":28}
    ]
  }]
}
```

`pages` 必须非空，页面 `id` 唯一，`name` 非空，`widgets` 为列表。`title` 为可选标签。`variables` 为名称到标量默认值的映射；Axure 全局变量以字符串保存，数字会转换为文本。页面顺序决定 sitemap 顺序，控件按从底到顶排列。用底层矩形定义需要的画面范围；Axure 本身仍为无限画布。

`page_alignment` 控制浏览器中整页的水平位置，仅接受 `center` / `left`，工程级省略时默认 `center`；单页同名字段可覆盖工程值。它写入原生 `PageStyle.PAGE_ALIGNMENT`，在 Axure 中继续导出也有效，和控件的 `align`（文字对齐）独立。页面仍顶部对齐，控件 x/y 不变；窗口小于页面时左边缘可访问，超宽内容可水平滚动，不会自动缩小为响应式布局。

### 原生编辑布局与演示布局

Axure 的无限编辑画布和浏览器演示是两件事。`page_alignment` 只影响演示，不会把原生控件移到编辑区中央。新绘制的固定宽度原型默认采用 1440px 参考编辑区，画面左右至少留 160px；若画面更宽，将参考区扩大到至少画面宽度+320px。画面宽为 W 时，其左边界取 `(参考宽度-W)/2`；390px 移动端即 x=525，背景范围为 x=525..915。参考区只是布局基准，不是有限画板字段；不要编造 `canvas_width` 等 spec 属性。

页面级控件使用真实页面坐标，例如手机号框原来在画面内 x=24，就保存为 x=549。动态面板本身放到 x=525 后，其状态内控件仍使用原来的局部坐标。隐藏的页面级弹层使用同一偏移；页面坐标系下的绝对移动目标值/表达式也要同步，面板内的相对动作不变。示例见 `examples/presentation.json`。y 坐标保留设计值，水平编辑留白不要求增加演示顶部空白。

原生 `center` 导出按内容范围消除正的起始 x 偏移，生成的 body 可为 `left:-525px;width:390px;margin-left:auto;margin-right:auto`。因此原生编辑区可保留左右空间，手机 HTML 仍是 390px 宽；不要将 body 的负补偿值误判为内容偏左。不要增加空白占位或巨大背景来撑编辑区。普通文本批注也会参与导出范围，使用 Axure 原生说明可避免扩大移动端画面。

直接页面和 `start.html` 播放器分别在自身可用内容区居中；播放器侧栏会占用一部分宽度。`left` 演示保留页面坐标里的起始空白，若需左对齐演示同时编辑留白，需另行设计，不能假定它也会裁掉起始偏移。新建工程自动打开首个真实页面；编辑器窗口大小、工具栏宽度和用户缩放决定实际屏幕位置，不是固定的显示器像素居中。

控件 `id` 写入 Axure 控件名称，同页所有容器内也必须唯一。原生 GUID 自动生成；`inspect` 可取得真实 GUID。创建时交互引用使用 spec ID；编辑时使用现有名称或 GUID。

## 基本控件字段

| 字段 | 值 | 说明 |
|---|---|---|
| id / kind | 非空 ID / 下表类型 | 必填 |
| x / y | 有限数值，绝对值 ≤20000 | 必填；页面或父容器内坐标，像素 |
| width / height | >0 且 ≤20000 | 必填；保存的 bounds |
| text | 字符串 | 文字或输入框初值 |
| placeholder | 字符串 | input / textarea 提示 |
| password | 布尔值 | 仅 input |
| font_size | 1–300 | 像素；内部 point 值乘 0.75 |
| font_family / bold | 字体名 / 布尔值 | 使用已安装字体 |
| color / fill / border_color | #RRGGBB 或 #AARRGGBB | 文字、填充和边框色 |
| border_width | 非负数 | 边框宽度 |
| align | left / center / right | 水平文字对齐 |
| hidden / disabled / selected | 布尔值 | 原生初始状态；取决于控件具有该属性 |
| tooltip / selection_group | 字符串 | 原生提示与选择组；不适用的原生字段报错 |
| events | 对象 | 原生事件树，见 interactions 文档 |
| native_style | 对象 | 以原生 PName 名称配置样式，如 {"CORNER_RADIUS":12} |
| state_styles | 对象 | 以原生状态名配置样式，如下例 |
| native | 对象 | 原生控件字段扩展；不是自由 HTML 属性 |

未指定样式继承本机默认库。未知字段报错；不要编造 `on_click` 或 `radius`。`rect`、`text`、`button` 在原生模型均可显示为 VectorShape。

| kind | 原生默认库模板 |
|---|---|
| rect / text / button | Box 1 / Paragraph / Primary Button |
| input / textarea / checkbox / radio | Text Field / Text Area / Checkbox / Radio Button |
| panel / repeater | Dynamic Panel / Repeater |
| droplist / listbox | Droplist / List Box，支持 options |
| ellipse / placeholder / hotspot / iframe | 对应默认模板 |
| line / vline / arrow | 水平线 / 垂直线 / 水平箭头 |
| heading1 / heading2 / heading3 / label / link | 对应文字模板 |
| image / table / tree / menu / vmenu | 仅默认模板；未提供自定义图片源/单元格/节点/菜单数据接口 |

模板可创建不等于每个属性/事件已验证，具体见能力矩阵。控件克隆时清除默认库自带的演示事件和 AdaptiveStyles。

复选框和单选框显示高度由字体测量；repeater 显示尺寸由内容计算。`inspect` 返回保存 bounds，官方 API 返回计算后的可视 bounds；不能承诺二者尺寸始终相同。输入框提示在编辑画布 PNG 可能不显示，运行时 HTML 才体现。

## 下拉列表与状态样式

```json
{
  "id":"choice","kind":"droplist","x":48,"y":40,"width":240,"height":44,
  "options":["待处理",{"text":"已完成","selected":true}]
}
```

`options` 的元素为字符串或 `{text,selected}`；`multiple` 仅用于 droplist/listbox，通常配合 listbox。

```json
{
  "native_style":{"CORNER_RADIUS":12},
  "state_styles":{
    "MouseOver":{"FILL":"#16A34A"},
    "Selected":{"FILL":"#9333EA"}
  }
}
```

以上片段合并到控件。状态名包括 MouseOver、MouseDown、Selected、Disabled、Focused、SelectedFocused、SelectedDisabled、Hint 等。属性必须存在于本机 PName 和模板属性集中；复杂属性可使用原生结构值。`models --enum Axure.Constants.PName` 查询实际名称。

## 修改 patch

单独修复已有原型的演示对齐，可只写 `page_updates`：

```json
{"page_updates":[{"page":"首页","set":{"page_alignment":"center"}}]}
```

`page` 接受现有页面名或 GUID，每页只写一条。页面级 `set` 当前仅支持 `page_alignment`。`page_updates` 和控件级 `updates` 可一起使用，至少一个列表非空。页面、控件 GUID、控件布局及交互保留；未指定的页面对齐不变。

```json
{
  "updates":[
    {"page":"首页","widget":"status","set":{"text":"已更新","x":80,"font_size":24}},
    {"page":"首页","widget":"submit","events":{"OnClick":[{"type":"set_text","target":"status","value":"交互已更新"}]}}
  ]
}
```

`page` 为现有页面名称或 GUID；`widget` 为控件名称或 GUID，递归查找面板状态与中继器项。缺失或歧义拒绝。同一控件只写一条 update，可同时包含 set 与 events。

`set` 支持 x/y/width/height/text/placeholder/password/font_size/font_family/bold/color/fill/border_color/border_width/align。当前编辑器接受 VectorShape、TextBox、Checkbox、DynamicPanel、Repeater；其他类型仍需适配。文字替换会统一为一个 run，单改字体/颜色保留原文。未指定的输入值、提示和密码属性保留。

`events` 替换该控件完整交互，`{}` 删除交互；省略则保留。编辑时 `open_page.page` 可使用现有页面名称或 GUID，动作目标同样支持名称或 GUID。不能借 patch 重命名、增删控件或状态；这些操作目前需改生成 spec。

## CLI 与输出

- `doctor`：版本、hash、安装位置、官方 API 是否存在、ui_automation=false。
- `inspect FILE`：真实递归结构、GUID、package_stem、每页有效 page_alignment、文字/bounds、面板状态、中继器数据、全局变量及原生 interaction_records 摘要；editor 包含 initial_page 与 open_pages。
- `verify FILE --render-dir DIR`：官方语义加载/读取及 PNG。顶层面板另存独立状态 PNG；整页 PNG 会漏画面板，应使用真实 HTML 截图检查复杂原型。
- `create --spec SPEC --output NEW.rp`：原生工程、spec、manifest、可用时官方 verification；widgets 为顶层数量，widgets_including_containers 包含面板/中继器内控件。
- `edit --input SOURCE.rp --patch PATCH --output NEW.rp`：新工程、patch、可用时 verification。
- `export-html FILE --output NEW_DIR`：Axure 自身生成器产出的完整本地 HTML；不开浏览器、不上传。
- `models [--model MODEL | --enum FULL_ENUM_NAME]`：真实模型字段和枚举。

工程及伴随文件不覆盖；HTML 目录必须是新目录。临时 staging 在成功/失败后清理。API 缺失时仍做原生回读，但不能声称经过官方独立验证。渲染目录中的同名 PNG 会更新，使用本次专用目录。

## 页面演示对齐检查

`runtime_test.cjs` 的 step 可指定 `viewport:{"width":1440,"height":1000}` 改变窗口，并用 `page_alignment:"center"` / `"left"` 断言整页的实际浏览器位置及页面能放下时无水平溢出。可增加 `canvas:"画面背景控件ID"` 直接核对可见画面的边界，避免把 body 的原生负偏移补偿误判为偏左。示例：

```powershell
python "$axureSkill\scripts\axure_skill.py" create --spec "$axureSkill\examples\presentation.json" --output 'C:\path\presentation.rp'
python "$axureSkill\scripts\axure_skill.py" export-html 'C:\path\presentation.rp' --output 'C:\path\presentation-html'
node "$axureSkill\scripts\runtime_test.cjs" 'C:\path\presentation-html' "$axureSkill\examples\presentation.test.json"
```

该计划覆盖原生 x=525 留白布局在桌面宽屏、同宽手机、窄窗口和缩放下的可见画面位置，以及单页覆盖和文字对齐不变。原生创建/编辑回归还核对首屏自动打开和原生保存坐标，可在源码根目录设置 `AXURE_NATIVE_TESTS=1` 后运行 `python -m unittest discover -s tests -p test_page_alignment.py -v`，需要本机 RP9 和可选的 Playwright/Chromium。
