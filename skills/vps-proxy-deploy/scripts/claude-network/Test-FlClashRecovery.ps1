$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'FlClashRecovery.ps1')

$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('flclash-recovery-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot | Out-Null
$testKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
$script:settings = [pscustomobject]@{ ProxyEnable = 1; ProxyServer = '127.0.0.1:7890'; ProxyOverride = '<local>' }
$script:mockOwner = ''
$script:notifications = 0
$misses = 0

function Get-ItemProperty([string]$LiteralPath) {
    if ($LiteralPath -ne $testKey) { throw 'Unexpected settings path in test.' }
    return $script:settings
}
function Get-NetTCPConnection { if ($script:mockOwner) { [pscustomobject]@{ OwningProcess = 123 } } }
function Get-Process { [pscustomobject]@{ ProcessName = $script:mockOwner } }
function Set-ItemProperty([string]$LiteralPath, [string]$Name, [string]$Value) {
    if ($LiteralPath -ne $testKey -or $Name -ne 'ProxyOverride') { throw 'Unexpected write in test.' }
    $script:settings | Add-Member -NotePropertyName $Name -NotePropertyValue $Value -Force
}
function Remove-ItemProperty([string]$LiteralPath, [string]$Name) {
    if ($LiteralPath -ne $testKey -or $Name -ne 'ProxyOverride') { throw 'Unexpected removal in test.' }
    $script:settings.PSObject.Properties.Remove($Name)
}
function Send-FlClashProxySettingChange { $script:notifications++ }
function Assert-Recovery([bool]$Condition, [string]$Message) { if (!$Condition) { throw $Message } }

try {
    $journal = Join-Path $testRoot 'flclash-recovery.json'
    Assert-Recovery ((Invoke-FlClashRecoveryCheck $testRoot ([ref]$misses)) -eq 'WaitingForListener') 'Applied on the first check.'
    Assert-Recovery ((Invoke-FlClashRecoveryCheck $testRoot ([ref]$misses)) -eq 'FallbackActive') 'Did not enable the domestic fallback.'
    $override = @($script:settings.ProxyOverride -split ';')
    Assert-Recovery ('<local>' -in $override -and '*.bilivideo.com' -in $override -and '*.baidu.com' -in $override) 'Expected exceptions were missing.'
    Assert-Recovery (!@($override | Where-Object { $_ -eq '*' -or $_ -match 'claude|anthropic' }).Count) 'Unexpected bypass scope.'
    Assert-Recovery ((Invoke-FlClashRecoveryCheck $testRoot ([ref]$misses)) -eq 'FallbackActive' -and $script:notifications -eq 1) 'Repeated a settings write.'
    $script:mockOwner = 'FlClashCore'
    Assert-Recovery ((Invoke-FlClashRecoveryCheck $testRoot ([ref]$misses)) -eq 'Restore') 'Did not restore on proxy recovery.'
    Assert-Recovery ($script:settings.ProxyOverride -ceq '<local>' -and !(Test-Path -LiteralPath $journal)) 'Failed to restore exact prior state.'

    $script:mockOwner = 'OtherProxy'
    Assert-Recovery ((Invoke-FlClashRecoveryCheck $testRoot ([ref]$misses)) -eq 'Unmanaged') 'Acted on another listener.'
    $script:mockOwner = ''
    $script:settings | Add-Member -NotePropertyName AutoConfigURL -NotePropertyValue 'https://example.com/proxy.pac'
    Assert-Recovery ((Invoke-FlClashRecoveryCheck $testRoot ([ref]$misses)) -eq 'Unmanaged') 'Acted on a PAC-managed configuration.'
    $script:settings.PSObject.Properties.Remove('AutoConfigURL')
    $script:settings.PSObject.Properties.Remove('ProxyOverride')
    $null = Invoke-FlClashRecoveryCheck $testRoot ([ref]$misses)
    $null = Invoke-FlClashRecoveryCheck $testRoot ([ref]$misses)
    $script:settings.ProxyEnable = 0
    Assert-Recovery ((Invoke-FlClashRecoveryCheck $testRoot ([ref]$misses)) -eq 'Restore') 'Did not clear recovery after an intentional proxy stop.'
    Assert-Recovery ($script:settings.PSObject.Properties.Name -notcontains 'ProxyOverride') 'Failed to restore a missing registry property.'

    $script:settings.ProxyEnable = 1
    $null = Invoke-FlClashRecoveryCheck $testRoot ([ref]$misses)
    $null = Invoke-FlClashRecoveryCheck $testRoot ([ref]$misses)
    $script:settings.ProxyOverride = 'user-changed.example'
    Assert-Recovery ((Invoke-FlClashRecoveryCheck $testRoot ([ref]$misses)) -eq 'UserChangedOverride') 'Did not detect a settings change during recovery.'
    $script:mockOwner = 'FlClashCore'
    Assert-Recovery ((Invoke-FlClashRecoveryCheck $testRoot ([ref]$misses)) -eq 'Clear') 'Did not clear recovery on a user-modified configuration.'
    Assert-Recovery ($script:settings.ProxyOverride -ceq 'user-changed.example') 'Overwrote concurrent user settings.'
    'All FlClash recovery simulations passed.'
} finally {
    foreach ($name in 'flclash-recovery.json','flclash-recovery.json.next') {
        $testFile = Join-Path $testRoot $name
        if (Test-Path -LiteralPath $testFile) { Remove-Item -LiteralPath $testFile }
    }
    Remove-Item -LiteralPath $testRoot
}
