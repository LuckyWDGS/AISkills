$sourcePath = Join-Path $PSScriptRoot 'Claude-AI.js'
$source = Get-Content -Raw -LiteralPath $sourcePath
$declaration = [regex]::Match($source, '(?m)^\s*const domains = (\[[^\r\n]+\]);\s*$')
if (!$declaration.Success) { throw 'Could not read the domain list from Claude-AI.js.' }
$domains = @($declaration.Groups[1].Value | ConvertFrom-Json)
if (!$domains.Count -or @($domains | Where-Object { $_ -cnotmatch '^(?:[a-z0-9-]+\.)+[a-z]+$' }).Count) {
    throw 'Claude-AI.js contains an invalid DNS suffix.'
}
foreach ($domain in ($domains | Sort-Object -Unique)) {
    $domain
    '.' + $domain
}
