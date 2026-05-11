param(
    [string]$InstallRoot = "E:\RetailPulseEnterprise"
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\use_enterprise_env.ps1" -InstallRoot $InstallRoot

$checks = @(
    @{ Name = "Java"; Command = "java"; Args = "-version"; Mode = "run" },
    @{ Name = "Hadoop"; Command = "hadoop"; Args = "version"; Mode = "run" },
    @{ Name = "Spark"; Command = "spark-submit.cmd"; Args = "--version"; Mode = "run" },
    @{ Name = "Maven"; Command = "mvn.cmd"; Args = "--version"; Mode = "run" },
    @{ Name = "Kafka"; Command = "kafka-topics.bat"; Args = "--version"; Mode = "run" },
    @{ Name = "Zookeeper"; Command = "zkServer.cmd"; Args = ""; Mode = "exists" },
    @{ Name = "HBase"; Command = "hbase.cmd"; Args = "version"; Mode = "run" },
    @{ Name = "Sqoop"; Command = "sqoop.cmd"; Args = "version"; Mode = "run" },
    @{ Name = "Redis"; Command = "redis-server"; Args = "--version"; Mode = "source" },
    @{ Name = "Hive"; Command = "hive"; Args = "--version"; Mode = "exists" },
    @{ Name = "Flink"; Command = "flink"; Args = "--version"; Mode = "exists" }
)

foreach ($check in $checks) {
    Write-Host ""
    Write-Host "==== $($check.Name) ===="
    if ($check.Mode -eq "source") {
        if ($env:REDIS_HOME -and (Test-Path $env:REDIS_HOME)) {
            Write-Host "Found Redis source package: $env:REDIS_HOME"
            Write-Host "Note: Redis official distribution is source-first; run it from WSL/Linux/Docker for service mode on Windows."
        } else {
            Write-Warning "Redis source package not found."
        }
        continue
    }

    $cmd = Get-Command $check.Command -ErrorAction SilentlyContinue
    if (-not $cmd) {
        Write-Warning "$($check.Command) not found in PATH"
        continue
    }

    if ($check.Mode -eq "exists") {
        Write-Host "Found: $($cmd.Source)"
        Write-Host "Note: this distribution uses shell scripts or service commands; start it from Git Bash/WSL/Linux or a component-specific Windows script."
        continue
    }

    $commandLine = "`"$($cmd.Source)`" $($check.Args)"
    $output = cmd.exe /d /c "$commandLine 2>&1"
    $exitCode = $LASTEXITCODE
    $output | Select-Object -First 10
    $looksLikeVersionOutput = ($output -join "`n") -match "version|Version|HBase|Hadoop|Maven|Spark|Sqoop"
    if ($exitCode -ne 0 -and -not $looksLikeVersionOutput) {
        Write-Warning "$($check.Name) exited with code $LASTEXITCODE"
    }
}
