[CmdletBinding()]
param(
    [string]$RepoRoot = '',
    [string]$CodexSkillsDir = $(if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $HOME '.codex\skills' }),
    # Empty = keep the currently linked UE version (see install.ps1).
    [string]$UEVersion = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Join-Path -Path $PSScriptRoot -ChildPath '..'
}

$repoRootPath = (Resolve-Path -LiteralPath $RepoRoot).Path
git -C $repoRootPath pull --ff-only

& (Join-Path $PSScriptRoot 'install.ps1') -RepoRoot $repoRootPath -CodexSkillsDir $CodexSkillsDir -UEVersion $UEVersion
