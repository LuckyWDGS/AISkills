param([switch]$Apply, [switch]$UpdateDnsOnly)
$ErrorActionPreference = 'Stop'
$group = 'Claude-AI Guard'
$dnsRuleName = 'Claude-AI Guard scoped DNS'
$dnsAddress = '127.0.0.2'
$namespaces = @(& (Join-Path $PSScriptRoot 'Get-ClaudeDnsNamespaces.ps1'))

if ($UpdateDnsOnly) {
    $existing = @(Get-DnsClientNrptRule | Where-Object DisplayName -eq $dnsRuleName)
    if ($existing.Count -ne 1 -or $existing[0].NameServers -notcontains $dnsAddress) {
        throw 'The expected existing Claude-AI DNS rule was not found.'
    }
    $oldNamespaces = @($existing[0].Namespace)
    $additional = @($namespaces | Where-Object { $_ -notin $oldNamespaces })
    if ($Apply -and $additional.Count) {
        if (!(Get-NetTCPConnection -State Listen -LocalAddress $dnsAddress -LocalPort 53 -ErrorAction SilentlyContinue)) {
            throw 'Enable the current Claude-AI FlClash script before updating DNS.'
        }
        $merged = @($oldNamespaces + $additional | Sort-Object -Unique)
        try {
            Set-DnsClientNrptRule -Name $existing[0].Name -Namespace $merged
            $current = @(Get-DnsClientNrptPolicy -Effective | Where-Object { $_.NameServers -contains $dnsAddress })
            if (@($merged | Where-Object { $_ -notin @($current.Namespace) }).Count) { throw 'The updated DNS scopes are not effective.' }
            Clear-DnsClientCache
        } catch {
            Set-DnsClientNrptRule -Name $existing[0].Name -Namespace $oldNamespaces
            throw
        }
    }
    [pscustomobject]@{ Mode = if ($Apply) { 'Applied' } else { 'Preview' }; AddedDnsNamespaces = $additional } | ConvertTo-Json -Compress
    return
}
$app = @(Get-AppxPackage -Name 'AnthropicPBC.Claude')
if ($app.Count -ne 1) { throw 'Expected exactly one Claude Desktop package for the current Windows user.' }
$expectedNames = @('claude.exe', 'chrome-native-host.exe', 'claude-make-data-folder.exe', 'claude-ssh-askpass.exe', 'claude-ssh-broker.exe', 'claude-ssh-proxy.exe', 'cowork-svc.exe', 'github-mcp-server.exe')
$programs = @(Get-ChildItem -LiteralPath $app[0].InstallLocation -Filter '*.exe' -File -Recurse | Where-Object Name -in $expectedNames)
if ($programs.Count -ne $expectedNames.Count -or @($programs.Name | Sort-Object -Unique).Count -ne $expectedNames.Count) { throw 'Claude package files differ from the reviewed layout.' }
$interfaces = @(Get-NetAdapter -Physical | Select-Object -ExpandProperty Name -Unique)
if (!$interfaces.Count) { throw 'No physical network interface was found.' }
$service = Get-Service -Name 'CoworkVMServiceStore'
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Security.Principal;

public static class ClaudePackageSid {
    [DllImport("userenv.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
    private static extern int DeriveAppContainerSidFromAppContainerName(string name, out IntPtr sid);

    [DllImport("advapi32.dll", ExactSpelling = true)]
    private static extern IntPtr FreeSid(IntPtr sid);

    public static string Get(string name) {
        IntPtr sid;
        Marshal.ThrowExceptionForHR(DeriveAppContainerSidFromAppContainerName(name, out sid));
        try { return new SecurityIdentifier(sid).Value; }
        finally { FreeSid(sid); }
    }
}
"@
$packageSid = [ClaudePackageSid]::Get($app[0].PackageFamilyName)
$scopes = @(foreach ($program in $programs) { @{ Label = $program.BaseName; Selector = @{ Program = $program.FullName } } })
$scopes += @{ Label = 'Package'; Selector = @{ Package = $packageSid } }
$scopes += @{ Label = 'CoworkService'; Selector = @{ Service = $service.Name } }
if (!$Apply) {
    [pscustomobject]@{ Mode = 'Preview'; Interfaces = $interfaces; ProgramCount = $programs.Count; Service = $service.Name; FirewallRules = $scopes.Count; DnsNamespaces = $namespaces } | ConvertTo-Json -Compress
    return
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
if (!([Security.Principal.WindowsPrincipal]::new($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run as Administrator is required.' }
if (!(Get-NetTCPConnection -State Listen -LocalAddress $dnsAddress -LocalPort 53 -ErrorAction SilentlyContinue) -or
    !(Get-NetUDPEndpoint -LocalAddress $dnsAddress -LocalPort 53 -ErrorAction SilentlyContinue) -or
    !(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort 17891 -ErrorAction SilentlyContinue)) { throw 'FlClash proxy and both DNS transports must be listening before applying Windows rules.' }
Resolve-DnsName -Name 'api.anthropic.com' -Server $dnsAddress -Type A -DnsOnly -NoHostsFile -QuickTimeout | Out-Null
Resolve-DnsName -Name 'api.anthropic.com' -Server $dnsAddress -Type A -DnsOnly -NoHostsFile -TcpOnly -QuickTimeout | Out-Null
if (@(Get-NetFirewallRule -PolicyStore PersistentStore | Where-Object Group -eq $group).Count) { throw 'A Claude-AI Guard firewall group already exists.' }
$overlaps = @(Get-DnsClientNrptRule | Where-Object { @($_.Namespace | Where-Object { $_ -in $namespaces }).Count })
if ($overlaps.Count) { throw 'An existing Windows DNS policy already covers one of the requested exact namespaces.' }

$created = [Collections.Generic.List[string]]::new()
$dnsId = $null
try {
    foreach ($scope in $scopes) {
        $name = 'Claude-AI-Guard-' + $scope.Label
        $selector = $scope.Selector
        New-NetFirewallRule -PolicyStore PersistentStore -Name $name -DisplayName $name `
            -Group $group -Direction Outbound -Action Block -Enabled True -Profile Any `
            -InterfaceAlias $interfaces -RemoteAddress Any @selector | Out-Null
        $created.Add($name)
    }
    $active = @(Get-NetFirewallRule -PolicyStore ActiveStore -Enabled True -Direction Outbound -Action Block | Where-Object Group -eq $group)
    if ($active.Count -ne $created.Count) { throw 'Not all new firewall rules are enabled in the effective policy.' }
    $dnsRule = Add-DnsClientNrptRule -DisplayName $dnsRuleName -Namespace $namespaces -NameServers $dnsAddress -PassThru
    $dnsId = $dnsRule.Name
    $effective = @(Get-DnsClientNrptPolicy -Effective)
    foreach ($namespace in $namespaces) {
        if (!@($effective | Where-Object { $namespace -in $_.Namespace -and $dnsAddress -in $_.NameServers }).Count) {
            throw ('Windows did not activate the expected DNS policy for ' + $namespace)
        }
    }
    Clear-DnsClientCache
    [pscustomobject]@{ Mode = 'Applied'; ActiveFirewallRules = $active.Count; DnsRuleId = $dnsId; Interfaces = $interfaces; DnsNamespaces = $namespaces } | ConvertTo-Json -Compress
} catch {
    if ($dnsId) { Remove-DnsClientNrptRule -Name $dnsId -Force -ErrorAction Continue }
    foreach ($name in $created) { Remove-NetFirewallRule -PolicyStore PersistentStore -Name $name -ErrorAction Continue }
    throw
}
