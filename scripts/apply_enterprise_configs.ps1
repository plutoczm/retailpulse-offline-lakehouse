param(
    [string]$InstallRoot = "E:\RetailPulseEnterprise"
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\use_enterprise_env.ps1" -InstallRoot $InstallRoot

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$configRoot = Join-Path $projectRoot "configs\enterprise"
$dataRoot = Join-Path $InstallRoot "data"
$logsRoot = Join-Path $InstallRoot "logs"

$dirs = @(
    "$dataRoot\hadoop\namenode",
    "$dataRoot\hadoop\datanode",
    "$dataRoot\hadoop\tmp",
    "$dataRoot\zookeeper",
    "$dataRoot\kafka-logs",
    "$dataRoot\hbase",
    "$dataRoot\flink",
    "$logsRoot\hadoop",
    "$logsRoot\spark",
    "$logsRoot\hive",
    "$logsRoot\kafka",
    "$logsRoot\hbase",
    "$logsRoot\flink"
)

foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

function Copy-ConfigDir {
    param(
        [string]$Source,
        [string]$Target
    )
    if (-not (Test-Path $Source)) {
        Write-Warning "Config source not found: $Source"
        return
    }
    if (-not (Test-Path $Target)) {
        New-Item -ItemType Directory -Force -Path $Target | Out-Null
    }
    Copy-Item -Path (Join-Path $Source "*") -Destination $Target -Recurse -Force
    Write-Host "Applied config: $Source -> $Target"
}

Copy-ConfigDir -Source (Join-Path $configRoot "hadoop") -Target (Join-Path $env:HADOOP_HOME "etc\hadoop")
Copy-ConfigDir -Source (Join-Path $configRoot "spark") -Target (Join-Path $env:SPARK_HOME "conf")
Copy-ConfigDir -Source (Join-Path $configRoot "hive") -Target (Join-Path $env:HIVE_HOME "conf")
Copy-ConfigDir -Source (Join-Path $configRoot "kafka") -Target (Join-Path $env:KAFKA_HOME "config")
Copy-ConfigDir -Source (Join-Path $configRoot "zookeeper") -Target (Join-Path $env:ZOOKEEPER_HOME "conf")
Copy-ConfigDir -Source (Join-Path $configRoot "hbase") -Target (Join-Path $env:HBASE_HOME "conf")
Copy-ConfigDir -Source (Join-Path $configRoot "sqoop") -Target (Join-Path $env:SQOOP_HOME "conf")
Copy-ConfigDir -Source (Join-Path $configRoot "flink") -Target (Join-Path $env:FLINK_HOME "conf")

$runtimeHadoopBin = Join-Path $projectRoot ".runtime\hadoop\bin"
if (-not (Test-Path (Join-Path $runtimeHadoopBin "winutils.exe"))) {
    & "$PSScriptRoot\setup_windows_spark.ps1"
}

if (Test-Path (Join-Path $runtimeHadoopBin "winutils.exe")) {
    Copy-Item -LiteralPath (Join-Path $runtimeHadoopBin "winutils.exe") -Destination (Join-Path $env:HADOOP_HOME "bin") -Force
}
if (Test-Path (Join-Path $runtimeHadoopBin "hadoop.dll")) {
    Copy-Item -LiteralPath (Join-Path $runtimeHadoopBin "hadoop.dll") -Destination (Join-Path $env:HADOOP_HOME "bin") -Force
}

Write-Host "Enterprise configs applied."
Write-Host "Data root: $dataRoot"
Write-Host "Logs root: $logsRoot"
