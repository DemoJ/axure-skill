# 环境、依赖与版本适配

已验证环境：Windows、Python 3.12、Axure RP 9.0.0.3744。项目从源码分发，首次运行时在本地编译辅助程序、生成控件及模型缓存。

## 必需组件

- 自行安装 Axure RP **9.0.0.3744**，默认位置为 `C:\Program Files (x86)\Axure\Axure RP 9`。
- `AxureRP9.exe` 必须匹配已验证 SHA256：`f7dcdec8f44f122cf4c7f887655335dc49df159dc01dc981a649f1003b095505`。
- Python 3.12；核心 CLI 无第三方 Python 包依赖。
- Windows .NET Framework 4 C# 编译器：`%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe`。无需安装 .NET SDK，辅助程序编译为 x86。
- Windows PowerShell；官方读取/渲染使用 `%WINDIR%\SysWOW64\WindowsPowerShell\v1.0\powershell.exe`。

Axure 不在默认目录时使用：

```powershell
$env:AXURE9_DIR = 'D:\Apps\Axure RP 9'
python .\scripts\axure_skill.py doctor
```

也可以把 `--axure-dir 'D:\Apps\Axure RP 9'` 放在 CLI 子命令之前。`smoke_test.py` 读取 `AXURE9_DIR`。改变目录不会绕过二进制 hash 检查。

辅助程序首次调用或源码较新时自动编译；skill 所在目录需要可写。常规运行只读取自己的 Axure 安装，不修改安装文件、不注入现有 Axure 进程、不发送桌面键鼠输入。

## 首次生成的本地缓存

- `.cache/rp9-3744-v2`：从自己的 `DefaultSettings\Libraries\Default.rplib` 提取的模板。
- `.cache/native-schema-v3`：本机实际原生模型的序列化字段、枚举和模板。
- `scripts/NativeBridge.exe`、`scripts/NativeExport.exe`：由本项目 C# 源码本地编译的辅助程序。

这些文件不随仓库提供。`.gitignore` 排除缓存和二进制，不要将 Axure 默认库、官方组件或提取数据提交到公共仓库。

升级 Axure 后需要针对新版重新研究并适配；3744 的混淆类型映射不能直接套用到其他 build。不要仅移除版本/hash 检查。

## 可选：官方只读 API

核心 RP/HTML 生成不需要官方只读 DLL。独立语义核验、PNG 渲染和 `smoke_test.py` 需要它。

从 [Axure 官方 API 页面](https://www.axure.com/axure-rp-api/) 获取 **RP9 API**。开发验证时使用的 [官方 RP9 API ZIP](https://maxure.s3.us-east-1.amazonaws.com/AxureRP-9-0-API.zip) 内含 `bin/Axure.Document.dll`。请将 DLL 放在当前 skill/仓库根目录下的：

```text
.cache/public-api/Axure.Document.dll
```

创建目录示例：

```powershell
New-Item -ItemType Directory -Path .\.cache\public-api -Force | Out-Null
# 将自行下载的 RP9 Axure.Document.dll 复制到该目录
Get-FileHash .\.cache\public-api\Axure.Document.dll -Algorithm SHA256
python .\scripts\axure_skill.py doctor
```

已验证 DLL 的 SHA256：`5c16f81538c1606de34b64164b625f2fd7a1bd30113d72855977d9f6dce8570f`。不要混用 RP8/10/11 DLL；第三方组件遵循其自身条款，仓库不重新分发。

`scripts/verify.ps1` 自动编译 `OfficialVerify.cs` 到该缓存目录，从 DLL 字节加载 API；不需要修改注册表、用户许可证或全局系统设置。

```powershell
python .\scripts\axure_skill.py verify .\outputs\advanced.rp --render-dir .\outputs\native-preview
python .\scripts\smoke_test.py
```

官方整页 PNG 在已验证环境中会漏画动态面板内容，复杂原型使用下述真实 HTML 测试及截图。API 缺失时创建/修改仍做原生回读，但不会声称通过官方独立核验。

## 可选：真实 HTML 交互检查

在 skill 根目录（包含 package.json 的目录）执行：

```powershell
npm install
npx playwright install chromium
node .\scripts\runtime_test.cjs .\outputs\advanced-html .\examples\advanced.test.json .\outputs\advanced.png
```

需要 Node.js 20+；`package.json` 固定开发验证使用的 Playwright 版本。`npm install` 与浏览器安装需要网络，生成 RP/HTML 和已安装依赖下的测试可在本机完成。

测试使用无头浏览器和临时回环 HTTP 服务；服务仅监听 `127.0.0.1`，退出关闭。不会向桌面发送鼠标或键盘输入。

如果已有可用的 Chromium，可指定：

```powershell
$env:AXURE_TEST_BROWSER = 'D:\Tools\Chromium\chrome.exe'
```

可使用 skill 根目录的 `node_modules`，无需依赖任何 Agent 厂商的内置运行时路径。没有浏览器时报告未执行交互检查，不能用静态 PNG 代替。

测试计划应与相应 spec/patch 配套。主交互16步、控件动作7步、编辑3步；运行测试方式见 [交互文档](interactions.md)。
