param(
    [string]$InstallRoot = "E:\RetailPulseEnterprise",
    [ValidateSet("User", "Machine", "None")]
    [string]$PersistScope = "User",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$components = Join-Path $InstallRoot "components"
$downloads = Join-Path $InstallRoot "downloads"
$dataRoot = Join-Path $InstallRoot "data"
$logsRoot = Join-Path $InstallRoot "logs"
$tmpRoot = Join-Path $InstallRoot "tmp"

$officialComponents = @(
    @{
        Name = "Hadoop"
        Version = "3.4.2"
        Url = "https://downloads.apache.org/hadoop/common/hadoop-3.4.2/hadoop-3.4.2.tar.gz"
        Archive = "hadoop-3.4.2.tar.gz"
        Dir = "hadoop-3.4.2"
        Type = "tar"
    },
    @{
        Name = "Spark"
        Version = "3.5.8"
        Url = "https://downloads.apache.org/spark/spark-3.5.8/spark-3.5.8-bin-hadoop3.tgz"
        Archive = "spark-3.5.8-bin-hadoop3.tgz"
        Dir = "spark-3.5.8-bin-hadoop3"
        Type = "tar"
    },
    @{
        Name = "Hive"
        Version = "4.2.0"
        Url = "https://downloads.apache.org/hive/hive-4.2.0/apache-hive-4.2.0-bin.tar.gz"
        Archive = "apache-hive-4.2.0-bin.tar.gz"
        Dir = "apache-hive-4.2.0-bin"
        Type = "tar"
    },
    @{
        Name = "Kafka"
        Version = "3.9.2"
        Url = "https://downloads.apache.org/kafka/3.9.2/kafka_2.13-3.9.2.tgz"
        Archive = "kafka_2.13-3.9.2.tgz"
        Dir = "kafka_2.13-3.9.2"
        Type = "tar"
    },
    @{
        Name = "ZooKeeper"
        Version = "3.9.5"
        Url = "https://downloads.apache.org/zookeeper/zookeeper-3.9.5/apache-zookeeper-3.9.5-bin.tar.gz"
        Archive = "apache-zookeeper-3.9.5-bin.tar.gz"
        Dir = "apache-zookeeper-3.9.5-bin"
        Type = "tar"
    },
    @{
        Name = "HBase"
        Version = "2.6.4"
        Url = "https://downloads.apache.org/hbase/2.6.4/hbase-2.6.4-bin.tar.gz"
        Archive = "hbase-2.6.4-bin.tar.gz"
        Dir = "hbase-2.6.4"
        Type = "tar"
    },
    @{
        Name = "Flink"
        Version = "2.1.1"
        Url = "https://downloads.apache.org/flink/flink-2.1.1/flink-2.1.1-bin-scala_2.12.tgz"
        Archive = "flink-2.1.1-bin-scala_2.12.tgz"
        Dir = "flink-2.1.1"
        Type = "tar"
    },
    @{
        Name = "Sqoop"
        Version = "1.4.7"
        Url = "https://archive.apache.org/dist/sqoop/1.4.7/sqoop-1.4.7.bin__hadoop-2.6.0.tar.gz"
        Archive = "sqoop-1.4.7.bin__hadoop-2.6.0.tar.gz"
        Dir = "sqoop-1.4.7.bin__hadoop-2.6.0"
        Type = "tar"
    },
    @{
        Name = "Redis"
        Version = "stable"
        Url = "https://download.redis.io/redis-stable.tar.gz"
        Archive = "redis-stable.tar.gz"
        Dir = "redis-stable"
        Type = "tar"
    },
    @{
        Name = "Maven"
        Version = "3.9.15"
        Url = "https://downloads.apache.org/maven/maven-3/3.9.15/binaries/apache-maven-3.9.15-bin.zip"
        Archive = "apache-maven-3.9.15-bin.zip"
        Dir = "apache-maven-3.9.15"
        Type = "zip"
    }
)

$sqoopCompatibilityJar = @{
    Name = "Sqoop commons-cli compatibility jar"
    Version = "1.2"
    Url = "https://repo.maven.apache.org/maven2/commons-cli/commons-cli/1.2/commons-cli-1.2.jar"
    Archive = "commons-cli-1.2.jar"
    TargetDir = "sqoop-1.4.7.bin__hadoop-2.6.0\lib"
}

function Assert-EdrivePath {
    param([string]$Path)
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    if (-not $fullPath.StartsWith("E:\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "InstallRoot must be on E drive. Current value: $fullPath"
    }
}

function Download-File {
    param(
        [string]$Url,
        [string]$Destination
    )

    if ((Test-Path $Destination) -and -not $Force) {
        Write-Host "Skip existing archive: $Destination"
        return
    }

    $tmp = "$Destination.tmp"
    if (Test-Path $tmp) {
        Remove-Item -LiteralPath $tmp -Force
    }

    Write-Host "Downloading $Url"
    if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
        & curl.exe -L --fail --retry 3 --retry-delay 3 -o $tmp $Url
        if ($LASTEXITCODE -ne 0) {
            throw "curl failed for $Url"
        }
    } else {
        Invoke-WebRequest -Uri $Url -OutFile $tmp -UseBasicParsing
    }

    Move-Item -LiteralPath $tmp -Destination $Destination -Force
}

function Expand-Component {
    param(
        [hashtable]$Component
    )

    $archivePath = Join-Path $downloads $Component.Archive
    $targetPath = Join-Path $components $Component.Dir

    if ((Test-Path $targetPath) -and -not $Force) {
        Write-Host "Skip existing component: $targetPath"
        return
    }

    if ((Test-Path $targetPath) -and $Force) {
        Remove-Item -LiteralPath $targetPath -Recurse -Force
    }

    Write-Host "Extracting $($Component.Name) $($Component.Version)"
    if ($Component.Type -eq "zip") {
        Expand-Archive -LiteralPath $archivePath -DestinationPath $components -Force
    } else {
        & tar -xzf $archivePath -C $components
        if ($LASTEXITCODE -ne 0 -and -not (Test-Path $targetPath)) {
            throw "Failed to extract $archivePath"
        }
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "tar reported warnings while extracting $archivePath, but $targetPath exists."
        }
    }
}

function New-JunctionAlias {
    param(
        [string]$AliasPath,
        [string]$TargetPath
    )

    if (Test-Path $AliasPath) {
        $item = Get-Item -LiteralPath $AliasPath
        if ($item.LinkType -eq "Junction" -or $item.LinkType -eq "SymbolicLink") {
            Write-Host "Alias already exists: $AliasPath"
            return
        } else {
            Write-Warning "Alias path exists and is not a junction: $AliasPath"
            return
        }
    }

    if (Test-Path $TargetPath) {
        New-Item -ItemType Junction -Path $AliasPath -Target $TargetPath | Out-Null
        Write-Host "Created alias: $AliasPath -> $TargetPath"
    }
}

Assert-EdrivePath -Path $InstallRoot

foreach ($path in @($InstallRoot, $components, $downloads, $dataRoot, $logsRoot, $tmpRoot)) {
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

foreach ($component in $officialComponents) {
    Download-File -Url $component.Url -Destination (Join-Path $downloads $component.Archive)
    Expand-Component -Component $component
}

$sqoopCompatTargetDir = Join-Path $components $sqoopCompatibilityJar.TargetDir
$sqoopCompatArchive = Join-Path $downloads $sqoopCompatibilityJar.Archive
New-Item -ItemType Directory -Force -Path $sqoopCompatTargetDir | Out-Null
Download-File -Url $sqoopCompatibilityJar.Url -Destination $sqoopCompatArchive
Copy-Item -LiteralPath $sqoopCompatArchive -Destination (Join-Path $sqoopCompatTargetDir $sqoopCompatibilityJar.Archive) -Force

$runtimeHadoopBin = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")) ".runtime\hadoop\bin"
$hadoopBin = Join-Path $components "hadoop-3.4.2\bin"
if (Test-Path (Join-Path $runtimeHadoopBin "winutils.exe")) {
    Copy-Item -LiteralPath (Join-Path $runtimeHadoopBin "winutils.exe") -Destination $hadoopBin -Force
}
if (Test-Path (Join-Path $runtimeHadoopBin "hadoop.dll")) {
    Copy-Item -LiteralPath (Join-Path $runtimeHadoopBin "hadoop.dll") -Destination $hadoopBin -Force
}

New-JunctionAlias -AliasPath "E:\rp-kafka" -TargetPath (Join-Path $components "kafka_2.13-3.9.2")

& "$PSScriptRoot\apply_enterprise_configs.ps1" -InstallRoot $InstallRoot
& "$PSScriptRoot\use_enterprise_env.ps1" -InstallRoot $InstallRoot -PersistScope $PersistScope

$manifestPath = Join-Path $InstallRoot "component-manifest.txt"
@(
    "RetailPulse Enterprise Official Component Manifest",
    "InstallRoot=$InstallRoot",
    "GeneratedAt=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "PersistScope=$PersistScope",
    "",
    "Official components:"
) | Set-Content -Path $manifestPath -Encoding UTF8

foreach ($component in $officialComponents) {
    " - $($component.Name) $($component.Version) => $(Join-Path $components $component.Dir)" |
        Add-Content -Path $manifestPath -Encoding UTF8
    "   Source: $($component.Url)" |
        Add-Content -Path $manifestPath -Encoding UTF8
}

" - $($sqoopCompatibilityJar.Name) $($sqoopCompatibilityJar.Version) => $(Join-Path $sqoopCompatTargetDir $sqoopCompatibilityJar.Archive)" |
    Add-Content -Path $manifestPath -Encoding UTF8
"   Source: $($sqoopCompatibilityJar.Url)" |
    Add-Content -Path $manifestPath -Encoding UTF8

Write-Host ""
Write-Host "Official enterprise components installed under: $components"
Write-Host "Manifest: $manifestPath"
Write-Host "Environment persistence scope: $PersistScope"
