[CmdletBinding()]
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$CodexSkillsDir = $(if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $HOME '.codex\skills' }),
    [string[]]$Skills = @(),
    [switch]$Replace
)

$ErrorActionPreference = 'Stop'

$repoRootPath = (Resolve-Path -LiteralPath $RepoRoot).Path
$skillsRoot = Join-Path $repoRootPath 'skills'

if (-not (Test-Path -LiteralPath $skillsRoot -PathType Container)) {
    throw "Missing skills directory: $skillsRoot"
}

if (-not (Test-Path -LiteralPath $CodexSkillsDir -PathType Container)) {
    New-Item -ItemType Directory -Path $CodexSkillsDir -Force | Out-Null
}

$codexSkillsPath = (Resolve-Path -LiteralPath $CodexSkillsDir).Path

if ($Skills.Count -eq 0) {
    $Skills = Get-ChildItem -LiteralPath $skillsRoot -Directory |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md') } |
        Sort-Object Name |
        Select-Object -ExpandProperty Name
}

if ($Skills.Count -eq 0) {
    Write-Host "No skills found under $skillsRoot"
    exit 0
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'

function Remove-LinkDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)

    [System.IO.Directory]::Delete($Path, $false)
}

foreach ($name in $Skills) {
    $target = Join-Path $skillsRoot $name
    $manifest = Join-Path $target 'SKILL.md'
    $linkPath = Join-Path $codexSkillsPath $name

    if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) {
        throw "Skill '$name' is missing SKILL.md at $manifest"
    }

    if (Test-Path -LiteralPath $linkPath) {
        $existing = Get-Item -LiteralPath $linkPath -Force

        if ($existing.LinkType -in @('Junction', 'SymbolicLink')) {
            Remove-LinkDirectory -Path $linkPath
        }
        elseif ($Replace) {
            $backup = "$linkPath.backup-$timestamp"
            Move-Item -LiteralPath $linkPath -Destination $backup
            Write-Host "Backed up existing $name to $backup"
        }
        else {
            throw "Destination already exists and is not a junction/symlink: $linkPath. Re-run with -Replace to back it up."
        }
    }

    New-Item -ItemType Junction -Path $linkPath -Target $target | Out-Null
    Write-Host "Linked $name -> $target"
}
