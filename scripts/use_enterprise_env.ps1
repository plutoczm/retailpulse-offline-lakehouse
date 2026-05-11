param(
    [string]$InstallRoot = "E:\RetailPulseEnterprise",
    [ValidateSet("User", "Machine", "None")]
    [string]$PersistScope = "None",
    [switch]$PersistUser
)

$ErrorActionPreference = "Stop"

$components = Join-Path $InstallRoot "components"
$envMap = [ordered]@{
    RETAILPULSE_ENTERPRISE_HOME = $InstallRoot
    HADOOP_HOME = Join-Path $components "hadoop-3.4.2"
    SPARK_HOME = Join-Path $components "spark-3.5.8-bin-hadoop3"
    HIVE_HOME = Join-Path $components "apache-hive-4.2.0-bin"
    KAFKA_HOME = $(if (Test-Path "E:\rp-kafka") { "E:\rp-kafka" } else { Join-Path $components "kafka_2.13-3.9.2" })
    ZOOKEEPER_HOME = Join-Path $components "apache-zookeeper-3.9.5-bin"
    HBASE_HOME = Join-Path $components "hbase-2.6.4"
    SQOOP_HOME = Join-Path $components "sqoop-1.4.7.bin__hadoop-2.6.0"
    FLINK_HOME = Join-Path $components "flink-2.1.1"
    REDIS_HOME = Join-Path $components "redis-stable"
    MAVEN_HOME = Join-Path $components "apache-maven-3.9.15"
}

if ($PersistUser) {
    $PersistScope = "User"
}

foreach ($item in $envMap.GetEnumerator()) {
    if (-not (Test-Path $item.Value) -and $item.Key -ne "RETAILPULSE_ENTERPRISE_HOME") {
        Write-Warning "$($item.Key) target does not exist: $($item.Value)"
    }
    Set-Item -Path "Env:$($item.Key)" -Value $item.Value
    if ($PersistScope -ne "None") {
        [Environment]::SetEnvironmentVariable($item.Key, $item.Value, $PersistScope)
    }
}

$binDirs = @(
    (Join-Path $envMap.HADOOP_HOME "bin"),
    (Join-Path $envMap.HADOOP_HOME "sbin"),
    (Join-Path $envMap.SPARK_HOME "bin"),
    (Join-Path $envMap.SPARK_HOME "sbin"),
    (Join-Path $envMap.HIVE_HOME "bin"),
    (Join-Path $envMap.KAFKA_HOME "bin\windows"),
    (Join-Path $envMap.KAFKA_HOME "bin"),
    (Join-Path $envMap.ZOOKEEPER_HOME "bin"),
    (Join-Path $envMap.HBASE_HOME "bin"),
    (Join-Path $envMap.SQOOP_HOME "bin"),
    (Join-Path $envMap.FLINK_HOME "bin"),
    (Join-Path $envMap.REDIS_HOME "src"),
    (Join-Path $envMap.MAVEN_HOME "bin")
) | Where-Object { Test-Path $_ }

$reversedBinDirs = @($binDirs)
[array]::Reverse($reversedBinDirs)
foreach ($bin in $reversedBinDirs) {
    if ($env:PATH -notlike "*$bin*") {
        $env:PATH = "$bin;$env:PATH"
    }
}

if ($PersistScope -ne "None") {
    $currentPath = [Environment]::GetEnvironmentVariable("Path", $PersistScope)
    foreach ($bin in $binDirs) {
        if ($currentPath -notlike "*$bin*") {
            $currentPath = "$bin;$currentPath"
        }
    }
    [Environment]::SetEnvironmentVariable("Path", $currentPath, $PersistScope)
}

Write-Host "RetailPulse enterprise environment loaded for this PowerShell session."
Write-Host "Install root: $InstallRoot"
if ($PersistScope -ne "None") {
    Write-Host "$PersistScope-level environment variables were persisted. Open a new terminal to use them globally."
}
