param(
    [string]$RuntimeDir = ".runtime\hadoop",
    [string]$WinutilsUrl = "https://github.com/cdarlint/winutils/raw/master/hadoop-3.3.5/bin/winutils.exe",
    [string]$HadoopDllUrl = "https://github.com/cdarlint/winutils/raw/master/hadoop-3.3.5/bin/hadoop.dll"
)

$ErrorActionPreference = "Stop"

if (-not $IsWindows -and $env:OS -ne "Windows_NT") {
    Write-Host "This setup script is only needed on Windows."
    exit 0
}

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$RuntimePath = Join-Path $ProjectRoot $RuntimeDir
$BinPath = Join-Path $RuntimePath "bin"
$WinutilsPath = Join-Path $BinPath "winutils.exe"
$HadoopDllPath = Join-Path $BinPath "hadoop.dll"

if ((Test-Path $WinutilsPath) -and (Test-Path $HadoopDllPath)) {
    Write-Host "Windows Hadoop files already exist: $BinPath"
    Write-Host "Set HADOOP_HOME for this session with:"
    Write-Host "`$env:HADOOP_HOME = '$RuntimePath'"
    Write-Host "`$env:PATH = '$BinPath;' + `$env:PATH"
    exit 0
}

New-Item -ItemType Directory -Force -Path $BinPath | Out-Null
$StubProject = Join-Path $ProjectRoot "tools\winutils-stub\winutils-stub.csproj"

$Dotnet = Get-Command dotnet -ErrorAction SilentlyContinue
$SdkList = ""
if ($Dotnet) {
    $SdkList = dotnet --list-sdks
}

if ($Dotnet -and $SdkList) {
    dotnet publish $StubProject `
        -c Release `
        -r win-x64 `
        --self-contained false `
        /p:PublishSingleFile=true `
        /p:AssemblyName=winutils `
        -o $BinPath | Out-Host
} else {
    Write-Host "No .NET SDK found. Downloading winutils.exe to project runtime directory."
    Invoke-WebRequest -Uri $WinutilsUrl -OutFile $WinutilsPath
}

if (-not (Test-Path $HadoopDllPath)) {
    Write-Host "Downloading hadoop.dll to project runtime directory."
    Invoke-WebRequest -Uri $HadoopDllUrl -OutFile $HadoopDllPath
}

if ((-not (Test-Path $WinutilsPath)) -or (-not (Test-Path $HadoopDllPath))) {
    throw "Failed to create or download $WinutilsPath. Place a Hadoop winutils.exe under this path manually."
}

Write-Host "Prepared local Hadoop Windows files under: $BinPath"
Write-Host "Set HADOOP_HOME for this session with:"
Write-Host "`$env:HADOOP_HOME = '$RuntimePath'"
Write-Host "`$env:PATH = '$BinPath;' + `$env:PATH"
