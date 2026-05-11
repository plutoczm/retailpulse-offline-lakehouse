param(
    [ValidateSet("tiny", "small", "default")]
    [string]$Scale = "tiny",
    [string]$StartDate = "2025-01-01",
    [int]$Days = 90,
    [string]$DataRoot = "data",
    [switch]$SkipGenerate,
    [switch]$SkipQuality
)

$ErrorActionPreference = "Stop"

if ($env:OS -eq "Windows_NT" -and -not $env:HADOOP_HOME) {
    $runtimeHadoop = Resolve-Path -Path (Join-Path $PSScriptRoot "..\.runtime\hadoop") -ErrorAction SilentlyContinue
    if (-not $runtimeHadoop) {
        & (Join-Path $PSScriptRoot "setup_windows_spark.ps1")
        $runtimeHadoop = Resolve-Path -Path (Join-Path $PSScriptRoot "..\.runtime\hadoop")
    }
    Set-Item -Path Env:HADOOP_HOME -Value $runtimeHadoop.Path
    Set-Item -Path Env:hadoop.home.dir -Value $runtimeHadoop.Path
    $hadoopBin = Join-Path $runtimeHadoop.Path "bin"
    if ($env:PATH -notlike "*$hadoopBin*") {
        $env:PATH = "$hadoopBin;$env:PATH"
    }
}

$argsList = @(
    "scripts/run_all.py",
    "--scale", $Scale,
    "--start-date", $StartDate,
    "--days", "$Days",
    "--data-root", $DataRoot
)

if ($SkipGenerate) {
    $argsList += "--skip-generate"
}

if ($SkipQuality) {
    $argsList += "--skip-quality"
}

python @argsList
