param(
    [string]$ToolBase = (Join-Path $env:LOCALAPPDATA "mirofish-pro-tools")
)

$ErrorActionPreference = "Stop"

$erlangHome = Join-Path $ToolBase "erlang-27.3.4.11"
$rabbitHome = Join-Path $ToolBase "rabbitmq-4.3.0\rabbitmq_server-4.3.0"
$runtimeBase = Join-Path $ToolBase "rabbitmq-runtime"
$rabbitCtl = Join-Path $rabbitHome "sbin\rabbitmqctl.bat"

if (-not (Test-Path $rabbitCtl)) {
    throw "rabbitmqctl.bat was not found at $rabbitCtl"
}

$env:ERLANG_HOME = $erlangHome
$env:PATH = "$erlangHome\bin;$env:PATH"
$env:RABBITMQ_BASE = $runtimeBase
$env:RABBITMQ_MNESIA_BASE = Join-Path $runtimeBase "mnesia"
$env:RABBITMQ_LOG_BASE = Join-Path $runtimeBase "log"
$env:RABBITMQ_ENABLED_PLUGINS_FILE = Join-Path $runtimeBase "enabled_plugins"
$env:RABBITMQ_CONFIG_FILE = Join-Path $runtimeBase "rabbitmq.conf"
$env:RABBITMQ_NODENAME = "rabbit@localhost"

& $rabbitCtl shutdown
Write-Host "RabbitMQ shutdown command sent."
