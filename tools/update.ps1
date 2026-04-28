[CmdletBinding()]
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$CodexSkillsDir = $(if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $HOME '.codex\skills' })
)

$ErrorActionPreference = 'Stop'

$repoRootPath = (Resolve-Path -LiteralPath $RepoRoot).Path
git -C $repoRootPath pull --ff-only

& (Join-Path $PSScriptRoot 'install.ps1') -RepoRoot $repoRootPath -CodexSkillsDir $CodexSkillsDir
