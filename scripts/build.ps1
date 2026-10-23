param([string]$AxureDirectory = 'C:\Program Files (x86)\Axure\Axure RP 9')
$ErrorActionPreference = 'Stop'
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
if (!(Test-Path -LiteralPath $compiler)) { throw '.NET Framework C# compiler is unavailable.' }
& $compiler /nologo /target:exe /platform:x86 /optimize+ /r:System.Web.Extensions.dll /out:"$PSScriptRoot\NativeBridge.exe" "$PSScriptRoot\NativeBridge.cs"
if ($LASTEXITCODE -ne 0) { throw 'Bridge compilation failed.' }
Write-Output "$PSScriptRoot\NativeBridge.exe"
