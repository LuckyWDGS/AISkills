[CmdletBinding()]
param(
    [string]$RepoRoot = '',
    [string]$CodexSkillsDir = $(if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $HOME '.codex\skills' }),
    [string[]]$Skills = @(),
    # UE skills live in skills\ue<version>\ with identical names, so only one
    # version can be linked at a time. Empty = keep the currently linked version
    # (first install: $DefaultUEVersion).
    [string]$UEVersion = '',
    [switch]$Replace
)

$ErrorActionPreference = 'Stop'
$DefaultUEVersion = '5.8'
$UECoreSkill = 'unreal-engine-mcp'

# Resolve script-relative defaults in the script body. Windows PowerShell 5.1
# can evaluate parameter defaults before $PSScriptRoot is populated.
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Join-Path -Path $PSScriptRoot -ChildPath '..'
}

$repoRootPath = (Resolve-Path -LiteralPath $RepoRoot).Path
$skillsRoot = Join-Path $repoRootPath 'skills'

if (-not (Test-Path -LiteralPath $skillsRoot -PathType Container)) {
    throw "Missing skills directory: $skillsRoot"
}

if (-not (Test-Path -LiteralPath $CodexSkillsDir -PathType Container)) {
    New-Item -ItemType Directory -Path $CodexSkillsDir -Force | Out-Null
}

$codexSkillsPath = (Resolve-Path -LiteralPath $CodexSkillsDir).Path

function Get-SkillDirs {
    param([Parameter(Mandatory = $true)][string]$Parent)

    Get-ChildItem -LiteralPath $Parent -Directory |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md') } |
        Sort-Object Name
}

# --- UE version groups: skills\ue<major.minor>\<skill>\SKILL.md ---
$ueGroups = @{}
foreach ($dir in (Get-ChildItem -LiteralPath $skillsRoot -Directory)) {
    if ($dir.Name -match '^ue(\d+\.\d+)$') {
        $ueGroups[$Matches[1]] = $dir.FullName
    }
}

if ([string]::IsNullOrWhiteSpace($UEVersion) -and $ueGroups.Count -gt 0) {
    # Keep whatever UE version is currently linked, so update.ps1 does not flip it back.
    $coreLink = Join-Path $codexSkillsPath $UECoreSkill
    $item = Get-Item -LiteralPath $coreLink -Force -ErrorAction SilentlyContinue
    if ($null -ne $item) {
        if ($item.LinkType -in @('Junction', 'SymbolicLink')) {
            $current = [string](@($item.Target)[0])
            if ($current -match '[\\/]ue(\d+\.\d+)[\\/]') { $UEVersion = $Matches[1] }
        }
    }
    if ([string]::IsNullOrWhiteSpace($UEVersion)) { $UEVersion = $DefaultUEVersion }
}

# --- Collect name -> source directory ---
$available = [ordered]@{}
foreach ($dir in (Get-SkillDirs -Parent $skillsRoot)) {
    $available[$dir.Name] = $dir.FullName
}

if ($ueGroups.Count -gt 0) {
    if (-not $ueGroups.ContainsKey($UEVersion)) {
        $known = ($ueGroups.Keys | Sort-Object) -join ', '
        throw "Unknown -UEVersion '$UEVersion'. Available: $known"
    }
    foreach ($dir in (Get-SkillDirs -Parent $ueGroups[$UEVersion])) {
        if ($available.Contains($dir.Name)) {
            throw "Skill name '$($dir.Name)' exists both at the top level and in ue$UEVersion"
        }
        $available[$dir.Name] = $dir.FullName
    }
    Write-Host "UE skills: version $UEVersion ($($ueGroups[$UEVersion]))"
}

if ($Skills.Count -eq 0) {
    $Skills = @($available.Keys)
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
    if (-not $available.Contains($name)) {
        throw "Unknown skill '$name' (UE skills resolve from ue$UEVersion)"
    }
    $target = $available[$name]
    $manifest = Join-Path $target 'SKILL.md'
    $linkPath = Join-Path $codexSkillsPath $name

    if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) {
        throw "Skill '$name' is missing SKILL.md at $manifest"
    }

    # Test-Path follows the link, so a junction whose old target moved away
    # (e.g. skills\unreal-engine-mcp before the ue5.x split) would look absent.
    $existing = Get-Item -LiteralPath $linkPath -Force -ErrorAction SilentlyContinue
    if ($null -ne $existing) {
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
