param([switch]$ProbeNetwork)

$ErrorActionPreference = 'Stop'
$expectedNamespaces = @(& (Join-Path $PSScriptRoot 'Get-ClaudeDnsNamespaces.ps1'))
$guardRules = @(Get-NetFirewallRule -PolicyStore ActiveStore -Enabled True -Direction Outbound -Action Block |
    Where-Object Group -eq 'Claude-AI Guard')
$protectedNamespaces = @((Get-DnsClientNrptPolicy -Effective |
    Where-Object { $_.NameServers -contains '127.0.0.2' }).Namespace)
$task = Get-ScheduledTask -TaskName 'ClaudeNetworkGuardWatch' -ErrorAction SilentlyContinue
$proxy = Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort 17891 -ErrorAction SilentlyContinue
$dnsTcp = Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.2' -LocalPort 53 -ErrorAction SilentlyContinue
$dnsUdp = Get-NetUDPEndpoint -LocalAddress '127.0.0.2' -LocalPort 53 -ErrorAction SilentlyContinue
$claude = @(Get-CimInstance Win32_Process -Filter "Name = 'Claude.exe'" -Property ProcessId,CommandLine)
$proxyConnections = @(Get-NetTCPConnection -State Established -RemoteAddress '127.0.0.1' -RemotePort 17891 -ErrorAction SilentlyContinue |
    Where-Object OwningProcess -in @($claude.ProcessId))
$appProxy = & (Join-Path $PSScriptRoot 'Set-ClaudeDesktopProxy.ps1')
$result = [ordered]@{
    DedicatedProxyListening = [bool]$proxy
    ScopedDnsTcpListening = [bool]$dnsTcp
    ScopedDnsUdpListening = [bool]$dnsUdp
    MissingDnsNamespaces = @($expectedNamespaces | Where-Object { $_ -notin $protectedNamespaces })
    ActiveClaudeFirewallRules = $guardRules.Count
    FirewallInterfaces = @($guardRules | Get-NetFirewallInterfaceFilter | Select-Object -ExpandProperty InterfaceAlias -Unique)
    MonitorState = if ($task) { [string]$task.State } else { 'Missing' }
    ClaudeManagedProxyConfigured = [bool]$appProxy.Configured
    ClaudeStartedWithProxyFlag = [bool]@($claude | Where-Object CommandLine -match '--proxy-server=http://127\.0\.0\.1:17891(?:\s|$)').Count
    ClaudeDedicatedProxyConnections = $proxyConnections.Count
}

if ($ProbeNetwork) {
    $status = & curl.exe --disable --silent --show-error --head --proxy http://127.0.0.1:17891 `
        --noproxy no-bypass.invalid --connect-timeout 5 --max-time 15 --output NUL `
        --write-out '%{http_code}' https://example.com/
    $result['DedicatedProxyHttpsStatus'] = if ($LASTEXITCODE -eq 0 -and $status -match '^\d{3}$') { [int]$status } else { $null }
    $result['WindowsClaudeDnsResolves'] = [bool]@(Resolve-DnsName -Name 'api.anthropic.com' -Type A -DnsOnly -NoHostsFile `
        -QuickTimeout -ErrorAction SilentlyContinue | Where-Object Type -eq A).Count
}
[pscustomobject]$result | ConvertTo-Json -Depth 4
if ($ProbeNetwork -and ($result.DedicatedProxyHttpsStatus -ne 200 -or !$result.WindowsClaudeDnsResolves)) { exit 1 }
if (!$result.DedicatedProxyListening -or !$result.ScopedDnsTcpListening -or !$result.ScopedDnsUdpListening -or
    $result.MissingDnsNamespaces.Count -or !$result.ActiveClaudeFirewallRules -or $result.MonitorState -ne 'Running') { exit 1 }
