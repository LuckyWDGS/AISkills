param([switch]$Once)
$ErrorActionPreference = 'Stop'
$logDir = Join-Path $PSScriptRoot 'logs'
[IO.Directory]::CreateDirectory($logDir) | Out-Null
$packagePattern = '[\\/]AnthropicPBC[.]Claude_[^\\/]+[\\/]'
$lastDay = ''
$lastState = ''
$recoveryState = 'NotChecked'
$missingChecks = 0
if (!$Once) { . (Join-Path $PSScriptRoot 'FlClashRecovery.ps1') }

function Test-PublicAddress([string]$Address) {
    $ip = $null
    if (![Net.IPAddress]::TryParse($Address, [ref]$ip)) { return $false }
    if ($ip.IsIPv4MappedToIPv6) { $ip = $ip.MapToIPv4() }
    $bytes = $ip.GetAddressBytes()
    if ($bytes.Count -eq 16) { return ($bytes[0] -band 224) -eq 32 }
    $a, $b = $bytes
    return $a -notin 0,10,127 -and $a -lt 224 -and
        !($a -eq 169 -and $b -eq 254) -and !($a -eq 192 -and $b -eq 168) -and
        !($a -eq 172 -and $b -in 16..31) -and !($a -eq 100 -and $b -in 64..127)
}

function Get-GuardSample {
    $processes = @(Get-CimInstance Win32_Process -Property ProcessId,ParentProcessId,CreationDate,Name,ExecutablePath)
    $cowork = Get-CimInstance Win32_Service -Filter "Name = 'CoworkVMServiceStore'" -Property ProcessId,State
    $coworkPid = if ($cowork.State -eq 'Running') { [int]$cowork.ProcessId } else { 0 }
    $tracked = @{}
    foreach ($process in $processes) {
        if ($process.ExecutablePath -match $packagePattern -or ($coworkPid -gt 0 -and $process.ProcessId -eq $coworkPid -and $process.Name -eq 'cowork-svc.exe')) { $tracked[[int]$process.ProcessId] = $process }
    }
    do {
        $added = $false
        foreach ($process in $processes) {
            $id = [int]$process.ProcessId
            $parent = $tracked[[int]$process.ParentProcessId]
            if (!$tracked.ContainsKey($id) -and $parent -and $process.CreationDate -ge $parent.CreationDate) {
                $tracked[$id] = $process
                $added = $true
            }
        }
    } while ($added)

    $indices = @(Get-NetAdapter -Physical | Select-Object -ExpandProperty ifIndex)
    $physical = @(Get-NetIPAddress | Where-Object InterfaceIndex -in $indices | Select-Object -ExpandProperty IPAddress)
    $proxy = $false
    $dnsTcp = $false
    $dedicatedProxy = 0
    $sharedProxy = 0
    $connections = @(Get-NetTCPConnection)
    $physicalPublic = @(foreach ($connection in $connections) {
        if ($connection.State -eq 'Listen') {
            if ($connection.LocalAddress -eq '127.0.0.1' -and $connection.LocalPort -eq 17891) { $proxy = $true }
            if ($connection.LocalAddress -eq '127.0.0.2' -and $connection.LocalPort -eq 53) { $dnsTcp = $true }
            continue
        }
        $process = $tracked[[int]$connection.OwningProcess]
        if ($process -and $connection.RemoteAddress -in '127.0.0.1','::1','::ffff:127.0.0.1' -and $connection.State -eq 'Established') {
            if ($connection.RemotePort -eq 17891) { $dedicatedProxy++ }
            if ($connection.RemotePort -eq 7890) { $sharedProxy++ }
        }
        if ($process -and $connection.LocalAddress -in $physical -and (Test-PublicAddress $connection.RemoteAddress)) {
            [pscustomobject]@{ process = $process.Name; remoteAddress = $connection.RemoteAddress; remotePort = $connection.RemotePort; state = [string]$connection.State }
        }
    })
    $dnsUdp = @(Get-NetUDPEndpoint | Where-Object { $_.LocalAddress -eq '127.0.0.2' -and $_.LocalPort -eq 53 }).Count -gt 0
    [ordered]@{ proxyListening = $proxy; dnsTcpListening = $dnsTcp; dnsUdpListening = $dnsUdp; trackedProcessCount = $tracked.Count; dedicatedProxyConnections = $dedicatedProxy; ordinaryProxyConnections = $sharedProxy; physicalPublicTcp = $physicalPublic }
}

do {
    $now = [DateTime]::UtcNow
    $day = $now.ToString('yyyy-MM-dd')
    try { $sample = Get-GuardSample }
    catch { $sample = [ordered]@{ error = $_.Exception.GetType().Name } }
    $sample['flClashRecovery'] = $recoveryState
    $state = ConvertTo-Json -InputObject $sample -Compress -Depth 5
    if ($day -ne $lastDay -or $state -ne $lastState -or $Once) {
        $record = ConvertTo-Json -InputObject ([ordered]@{ timeUtc = $now.ToString('o'); state = $sample }) -Compress -Depth 6
        [IO.File]::AppendAllText((Join-Path $logDir ('network-' + $day + '.jsonl')), $record + [Environment]::NewLine)
        if ($Once) { $record }
        $lastState = $state
    }
    if ($day -ne $lastDay) {
        Get-ChildItem -LiteralPath $logDir -File -Filter 'network-*.jsonl' | Where-Object {
            $_.Name -match '^network-\d{4}-\d{2}-\d{2}\.jsonl$' -and $_.LastWriteTimeUtc -lt $now.AddDays(-7)
        } | ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force }
        $lastDay = $day
    }
    if (!$Once) {
        for ($check = 0; $check -lt 5; $check++) {
            try { $recoveryState = Invoke-FlClashRecoveryCheck -StateDirectory $logDir -MissingChecks ([ref]$missingChecks) }
            catch { $recoveryState = 'Error: ' + $_.Exception.GetType().Name }
            Start-Sleep -Seconds 3
        }
    }
} while (!$Once)
