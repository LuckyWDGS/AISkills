function Get-FlClashRecoveryAction {
    param($Journal, [bool]$Managed, [bool]$Healthy, [int]$Misses, [string]$Current)

    if ($Journal) {
        if ($Healthy -or !$Managed) {
            if ($Current -ceq $Journal.After) { return 'Restore' }
            return 'Clear'
        }
        if ($Current -ceq $Journal.After) { return 'FallbackActive' }
        if ($Current -ceq $Journal.Before) { return 'Retry' }
        return 'UserChangedOverride'
    }
    if ($Healthy) { return 'Healthy' }
    if (!$Managed) { return 'Unmanaged' }
    if ($Misses -lt 2) { return 'WaitingForListener' }
    return 'Apply'
}

function Send-FlClashProxySettingChange {
    if (!('ClaudeWinInetNotifications' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class ClaudeWinInetNotifications {
    [DllImport("wininet.dll", SetLastError = true)]
    public static extern bool InternetSetOption(IntPtr handle, int option, IntPtr value, int length);
}
'@
    }
    $null = [ClaudeWinInetNotifications]::InternetSetOption([IntPtr]::Zero, 39, [IntPtr]::Zero, 0)
    $null = [ClaudeWinInetNotifications]::InternetSetOption([IntPtr]::Zero, 37, [IntPtr]::Zero, 0)
}

function Invoke-FlClashRecoveryCheck {
    param([string]$StateDirectory, [ref]$MissingChecks)

    $key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
    $settings = Get-ItemProperty -LiteralPath $key
    $managed = [int]$settings.ProxyEnable -eq 1 -and $settings.ProxyServer -eq '127.0.0.1:7890' -and !$settings.AutoConfigURL
    $listener = Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort 7890 -ErrorAction SilentlyContinue | Select-Object -First 1
    $owner = if ($listener) { Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue }
    $healthy = $owner.ProcessName -eq 'FlClashCore'
    if ($listener -and !$healthy) { $managed = $false }
    if ($healthy -or !$managed) { $MissingChecks.Value = 0 } else { $MissingChecks.Value++ }

    $journalPath = Join-Path $StateDirectory 'flclash-recovery.json'
    $journal = if (Test-Path -LiteralPath $journalPath) { Get-Content -Raw -LiteralPath $journalPath | ConvertFrom-Json }
    $current = [string]$settings.ProxyOverride
    $action = Get-FlClashRecoveryAction -Journal $journal -Managed $managed -Healthy $healthy -Misses $MissingChecks.Value -Current $current
    if ($action -notin 'Apply', 'Retry', 'Restore', 'Clear') { return $action }

    if ($action -eq 'Apply') {
        $domains = 'bilibili.com', 'bilivideo.com', 'bilivideo.cn', 'hdslb.com', 'biliimg.com', 'baidu.com', 'mp.weixin.qq.com'
        $existing = @($current -split ';' | ForEach-Object { $_.Trim() })
        $additional = @($domains | ForEach-Object { $_; '*.' + $_ } | Where-Object { $_ -notin $existing })
        if (!$additional.Count) { return 'DomesticBypassAlreadyPresent' }
        $after = (@($current.TrimEnd(';')) + $additional | Where-Object { $_ }) -join ';'
        $journal = [pscustomobject]@{
            Before = $current
            After = $after
            Existed = $settings.PSObject.Properties.Name -contains 'ProxyOverride'
        }
        $stage = $journalPath + '.next'
        $journal | ConvertTo-Json -Compress | Set-Content -LiteralPath $stage -Encoding UTF8
        Move-Item -LiteralPath $stage -Destination $journalPath -Force
    }

    if ($action -ne 'Clear') {
        $latest = Get-ItemProperty -LiteralPath $key
        if ([string]$latest.ProxyOverride -cne $current -or
            ($action -ne 'Restore' -and ([int]$latest.ProxyEnable -ne 1 -or $latest.ProxyServer -ne '127.0.0.1:7890' -or $latest.AutoConfigURL))) {
            return 'UserChangedOverride'
        }
        if ($action -eq 'Restore') {
            if ($journal.Existed) {
                Set-ItemProperty -LiteralPath $key -Name ProxyOverride -Value $journal.Before
            } else {
                Remove-ItemProperty -LiteralPath $key -Name ProxyOverride
            }
        } else {
            Set-ItemProperty -LiteralPath $key -Name ProxyOverride -Value $journal.After
        }
        Send-FlClashProxySettingChange
    }
    if ($action -in 'Restore', 'Clear') { Remove-Item -LiteralPath $journalPath }
    if ($action -in 'Apply', 'Retry') { return 'FallbackActive' }
    return $action
}
