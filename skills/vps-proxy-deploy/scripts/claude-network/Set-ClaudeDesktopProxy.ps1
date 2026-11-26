param([switch]$Apply)

$ErrorActionPreference = 'Stop'
$expected = 'http://127.0.0.1:17891'
$userPath = 'HKCU:\Software\Policies\Claude'
$machinePath = 'HKLM:\Software\Policies\Claude'
$machine = Get-Item -LiteralPath $machinePath -ErrorAction SilentlyContinue
if ($machine -and $machine.GetValueNames().Count) {
    if ($machine.GetValue('egressProxyUrl', $null) -eq $expected -and !$machine.GetValue('egressProxyPacUrl', $null)) {
        [pscustomobject]@{ Scope = 'Machine'; Configured = $true; Proxy = $expected }
        return
    }
    throw 'Claude machine policy is present and takes precedence. Review it before applying a user policy.'
}
$user = Get-Item -LiteralPath $userPath -ErrorAction SilentlyContinue
$previous = if ($user) { $user.GetValue('egressProxyUrl', $null) }
if (($user -and $user.GetValue('egressProxyPacUrl', $null)) -or ($previous -and $previous -ne $expected)) {
    throw 'Claude already has a different user proxy policy.'
}
if ($Apply -and $previous -ne $expected) {
    if (!(Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort 17891 -State Listen -ErrorAction SilentlyContinue)) {
        throw 'Start the Claude-AI proxy before setting the Claude Desktop policy.'
    }
    if (!$user) { New-Item -Path $userPath -Force | Out-Null }
    New-ItemProperty -LiteralPath $userPath -Name egressProxyUrl -Value $expected -PropertyType String -Force | Out-Null
    $previous = (Get-Item -LiteralPath $userPath).GetValue('egressProxyUrl', $null)
    if ($previous -ne $expected) { throw 'Claude user proxy policy did not persist.' }
}
[pscustomobject]@{ Scope = 'User'; Configured = ($previous -eq $expected); Proxy = $expected }
