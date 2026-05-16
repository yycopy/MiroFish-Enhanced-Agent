param(
    [string]$ToolBase = (Join-Path $env:LOCALAPPDATA "mirofish-pro-tools")
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $repoRoot ".env"
$downloadDir = Join-Path $ToolBase "downloads"
$erlangHome = Join-Path $ToolBase "erlang-27.3.4.11"
$rabbitRoot = Join-Path $ToolBase "rabbitmq-4.3.0"
$rabbitHome = Join-Path $rabbitRoot "rabbitmq_server-4.3.0"
$runtimeBase = Join-Path $ToolBase "rabbitmq-runtime"
$erlangZip = Join-Path $downloadDir "otp_win64_27.3.4.11.zip"
$rabbitZip = Join-Path $downloadDir "rabbitmq-server-windows-4.3.0.zip"
$rabbitServer = Join-Path $rabbitHome "sbin\rabbitmq-server.bat"

function Read-DotEnv {
    param([string]$Path)

    $values = @{}
    if (-not (Test-Path $Path)) {
        return $values
    }

    Get-Content -Path $Path | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            $values[$parts[0]] = $parts[1].Trim('"')
        }
    }

    return $values
}

function Ensure-Archive {
    param(
        [string]$Url,
        [string]$OutFile
    )

    if (Test-Path $OutFile) {
        return
    }

    Write-Host "Downloading $Url"
    Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing
}

function Ensure-Extracted {
    param(
        [string]$Archive,
        [string]$Destination
    )

    if (Test-Path $Destination) {
        return
    }

    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Expand-Archive -Path $Archive -DestinationPath $Destination -Force
}

New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null

Ensure-Archive `
    -Url "https://github.com/erlang/otp/releases/download/OTP-27.3.4.11/otp_win64_27.3.4.11.zip" `
    -OutFile $erlangZip

Ensure-Archive `
    -Url "https://github.com/rabbitmq/rabbitmq-server/releases/download/v4.3.0/rabbitmq-server-windows-4.3.0.zip" `
    -OutFile $rabbitZip

Ensure-Extracted -Archive $erlangZip -Destination $erlangHome
Ensure-Extracted -Archive $rabbitZip -Destination $rabbitRoot

if (-not (Test-Path $rabbitServer)) {
    throw "rabbitmq-server.bat was not found at $rabbitServer"
}

$envValues = Read-DotEnv -Path $envPath
$rabbitUser = if ($envValues["RABBITMQ_USER"]) { $envValues["RABBITMQ_USER"] } else { "mirofish" }
$rabbitPass = if ($envValues["RABBITMQ_PASSWORD"]) { $envValues["RABBITMQ_PASSWORD"] } else { "mirofish_password" }

New-Item -ItemType Directory -Force -Path $runtimeBase | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $runtimeBase "mnesia") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $runtimeBase "log") | Out-Null
Set-Content -Path (Join-Path $runtimeBase "enabled_plugins") -Value "[rabbitmq_management]." -Encoding ascii
$configFile = Join-Path $runtimeBase "rabbitmq.conf"
Set-Content -Path $configFile -Encoding ascii -Value @"
deprecated_features.permit.transient_nonexcl_queues = true
deprecated_features.permit.global_qos = true
"@

$env:ERLANG_HOME = $erlangHome
$env:PATH = "$erlangHome\bin;$env:PATH"
$env:RABBITMQ_BASE = $runtimeBase
$env:RABBITMQ_MNESIA_BASE = Join-Path $runtimeBase "mnesia"
$env:RABBITMQ_LOG_BASE = Join-Path $runtimeBase "log"
$env:RABBITMQ_ENABLED_PLUGINS_FILE = Join-Path $runtimeBase "enabled_plugins"
$env:RABBITMQ_CONFIG_FILE = $configFile
$env:RABBITMQ_NODENAME = "rabbit@localhost"
$env:RABBITMQ_DEFAULT_USER = $rabbitUser
$env:RABBITMQ_DEFAULT_PASS = $rabbitPass

$amqpAlreadyReady = Test-NetConnection -ComputerName localhost -Port 5672 -InformationLevel Quiet -WarningAction SilentlyContinue
$managementAlreadyReady = Test-NetConnection -ComputerName localhost -Port 15672 -InformationLevel Quiet -WarningAction SilentlyContinue

if ($amqpAlreadyReady -and $managementAlreadyReady) {
    Write-Host "RabbitMQ is already running."
} else {
    cmd.exe /c "call `"$rabbitServer`" -detached"
    Write-Host "RabbitMQ start command sent."
}

$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    $amqpReady = Test-NetConnection -ComputerName localhost -Port 5672 -InformationLevel Quiet -WarningAction SilentlyContinue
    $managementReady = Test-NetConnection -ComputerName localhost -Port 15672 -InformationLevel Quiet -WarningAction SilentlyContinue
    if ($amqpReady -and $managementReady) {
        $ready = $true
        break
    }
    Start-Sleep -Seconds 2
}

if (-not $ready) {
    throw "RabbitMQ did not become ready within 60 seconds. Check logs under $runtimeBase\log"
}

Write-Host "RabbitMQ AMQP ready: localhost:5672"
Write-Host "RabbitMQ management ready: http://localhost:15672"
Write-Host "RabbitMQ user: $rabbitUser"
Write-Host "RabbitMQ password: read it from .env"
