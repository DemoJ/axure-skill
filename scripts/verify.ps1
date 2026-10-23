param(
    [Parameter(Mandatory=$true)][string]$InputFile,
    [string]$RenderDirectory,
    [string]$ApiDll
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
if (!$ApiDll) { $ApiDll = Join-Path $PSScriptRoot '..\.cache\public-api\Axure.Document.dll' }
$ApiDll = [IO.Path]::GetFullPath($ApiDll)
if (!(Test-Path -LiteralPath $ApiDll)) { throw 'Official Axure RP9 read API is unavailable. See references/setup.md.' }
$verifyExe = Join-Path (Split-Path $ApiDll) 'OfficialVerify.exe'
if (!(Test-Path -LiteralPath $verifyExe) -or (Get-Item -LiteralPath $verifyExe).LastWriteTime -lt (Get-Item -LiteralPath "$PSScriptRoot\OfficialVerify.cs").LastWriteTime) {
    $compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
    $compileResult = & $compiler /nologo /utf8output /platform:x86 /r:System.Web.Extensions.dll /r:"$ApiDll" /out:"$verifyExe" "$PSScriptRoot\OfficialVerify.cs"
    if ($LASTEXITCODE -ne 0) { throw ($compileResult -join "`n") }
}
# Load official API bytes in a dedicated x86 .NET Framework process. This avoids
# the downloaded library's legacy LoadFrom security context; it does not alter registry ACLs.
[Reflection.Assembly]::Load([IO.File]::ReadAllBytes($ApiDll)) | Out-Null
$verify = [Reflection.Assembly]::Load([IO.File]::ReadAllBytes($verifyExe))
[string[]]$arguments = @([IO.Path]::GetFullPath($InputFile))
if ($RenderDirectory) {
    $arguments += [IO.Path]::GetFullPath($RenderDirectory)
}
$resultCode = $verify.EntryPoint.Invoke($null, @(,$arguments))
exit $resultCode
