param([switch]$Apply)

$ErrorActionPreference = 'Stop'
$taskName = 'ClaudeNetworkGuardWatch'
$windowsPowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$toolDirectory = Join-Path $env:LOCALAPPDATA 'ClaudeNetworkGuard'
$package = Get-AppxPackage -Name 'AnthropicPBC.Claude'
if (!$package) { throw 'Claude Desktop is required.' }

$sourceNames = 'Watch-ClaudeNetwork.ps1', 'FlClashRecovery.ps1'
foreach ($name in $sourceNames) {
    if (!(Test-Path -LiteralPath (Join-Path $PSScriptRoot $name) -PathType Leaf)) {
        throw ('Missing source file: ' + $name)
    }
}

$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
$existingDirectory = Test-Path -LiteralPath $toolDirectory
[pscustomobject]@{
    MonitorTask = $taskName
    ToolDirectory = $toolDirectory
    ExistingInstall = [bool]($existingTask -or $existingDirectory)
}
& (Join-Path $PSScriptRoot 'Set-ClaudeDesktopProxy.ps1')
if (!$Apply) { return }

if ($existingTask -or $existingDirectory) {
    throw 'An existing installation was detected. Use Test-ClaudeNetwork.ps1 to check it.'
}
if (!(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort 17891 -ErrorAction SilentlyContinue)) {
    throw 'Enable the Claude-AI script in FlClash before setup.'
}

$createdTask = $false
New-Item -Path $toolDirectory -ItemType Directory | Out-Null
try {
    foreach ($name in $sourceNames) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $toolDirectory $name)
    }
    $watch = Join-Path $toolDirectory 'Watch-ClaudeNetwork.ps1'
    $sample = & $windowsPowerShell -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -File $watch -Once
    if ($LASTEXITCODE -ne 0 -or !($sample | ConvertFrom-Json).state.proxyListening) {
        throw 'The monitor failed its startup check.'
    }

    $user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    $action = New-ScheduledTaskAction -Execute $windowsPowerShell -Argument ('-NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -WindowStyle Hidden -File "' + $watch + '"')
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
        -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings `
        -Description 'Samples Claude-related TCP sockets and loopback proxy/DNS health locally.' | Out-Null
    $createdTask = $true
    Start-ScheduledTask -TaskName $taskName
    & (Join-Path $PSScriptRoot 'Set-ClaudeDesktopProxy.ps1') -Apply
} catch {
    if ($createdTask) { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction Continue }
    foreach ($name in $sourceNames) {
        $path = Join-Path $toolDirectory $name
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -ErrorAction Continue }
    }
    throw
}
