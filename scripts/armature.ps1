# The plugin's own engine, run through uv (ADR 0011): scripts/armature.sh for
# PowerShell, where there is no Git Bash. Same verbs, same venv under
# $env:CLAUDE_PLUGIN_DATA, same behaviour:
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File `
#       "${CLAUDE_PLUGIN_ROOT}/scripts/armature.ps1" gate status
#
# Windows' default execution policy refuses a script file, so the hook
# (hooks/hooks.json) runs this text with Invoke-Expression instead, naming
# the plugin root and the verb first:
#
#   $ArmatureRoot = "<plugin root>"; $ArmatureArgs = @('hook')
#   iex (Get-Content -Raw -LiteralPath "$ArmatureRoot/scripts/armature.ps1")
#
# Written for Windows PowerShell 5.1: no &&, no ternary, no ?? . A native
# command's stderr under 'Stop' throws in 5.1, so errors stay 'Continue'.
$ErrorActionPreference = 'Continue'
$utf8 = New-Object System.Text.UTF8Encoding $false
if ($PSScriptRoot) { $root = Split-Path -Parent $PSScriptRoot } else { $root = $ArmatureRoot }
$argv = @($args)
if ($ArmatureArgs) { $argv = @($ArmatureArgs) }
$data = $env:CLAUDE_PLUGIN_DATA
if (-not $data) { $data = Join-Path $HOME '.claude/plugins/data/armature-cli' }

function Find-Uv {
    $found = Get-Command uv -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($found) { return $found.Source }
    foreach ($c in @("$HOME/.local/bin/uv.exe", "$HOME/.cargo/bin/uv.exe",
                     "$HOME/.local/bin/uv", "$HOME/.cargo/bin/uv")) {
        if (Test-Path -LiteralPath $c -PathType Leaf) { return $c }
    }
    return $null
}

function Invoke-Engine($uv, [string[]]$rest, $stdin) {
    $env:UV_PROJECT_ENVIRONMENT = Join-Path $data 'venv'
    $env:PYTHONPYCACHEPREFIX = Join-Path $data 'pycache'
    $module = 'armature.' + $rest[0]
    $tail = @()
    if ($rest.Count -gt 1) { $tail = $rest[1..($rest.Count - 1)] }
    $argv = @('run', '--quiet', '--frozen', '--no-dev', '--project',
              (Join-Path $root 'engine'), 'python', '-m', $module) + $tail
    if ($null -ne $stdin) {
        $OutputEncoding = $utf8
        $stdin | & $uv @argv
    } else {
        & $uv @argv
    }
    exit $LASTEXITCODE
}

function Test-Project($folder) {
    if (-not $folder) { return $false }
    $top = & git -C $folder rev-parse --show-toplevel 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $top) { return $false }
    return (Test-Path -LiteralPath (Join-Path $top 'ledger.toml') -PathType Leaf)
}

function Resolve-From($path, $folder) {
    # The path, read from the folder; Git Bash's /c/... is C:/...
    if ($path -eq '~') { return $HOME }
    if ($path -match '^~[/\\]') { return (Join-Path $HOME $path.Substring(2)) }
    $path = $path -replace '^/([a-zA-Z])(?=/|$)', '$1:'
    if ([System.IO.Path]::IsPathRooted($path)) { return $path }
    return (Join-Path $folder $path)
}

# A cd (PowerShell's too) or git -C and the folder it names, plain or quoted.
$ChDir = '(?<![A-Za-z0-9_-])((?i:cd|pushd|chdir|set-location|sl)|-C)\s+' +
         '(?:(?i:-[a-z]*path)\s+)?("[^"]*"|''[^'']*''|[^\s;&|()]+)'

function Test-Reaches($folder, $command) {
    # The command runs in a project, from the folder or one a cd or git -C
    # on it names. A folder the line does not spell out (a variable, a
    # substitution) reaches none, as the engine's own reading has it.
    if (Test-Project $folder) { return $true }
    foreach ($m in [regex]::Matches($command, $ChDir)) {
        $target = $m.Groups[2].Value.Trim('"', "'")
        if (-not $target -or $target.Contains('$') -or $target.Contains('`')) { continue }
        $target = Resolve-From $target $folder
        if (Test-Project $target) { return $true }
        if ($m.Groups[1].Value -cne '-C') { $folder = $target }
    }
    return $false
}

function Test-EditProject($folder, $file) {
    # The file, read from the folder, is in a project.
    $at = Split-Path -Parent (Resolve-From $file $folder)
    while ($at -and -not (Test-Path -LiteralPath $at -PathType Container)) {
        $up = Split-Path -Parent $at
        if ($up -eq $at) { return $false }
        $at = $up
    }
    return ($at -and (Test-Project $at))
}

function Deny($reason) {
    $out = @{ hookSpecificOutput = @{ hookEventName = 'PreToolUse';
              permissionDecision = 'deny'; permissionDecisionReason = $reason } }
    [Console]::Out.Write(($out | ConvertTo-Json -Compress -Depth 4))
    exit 0
}

function Invoke-Hook {
    [Console]::InputEncoding = $utf8
    $raw = [Console]::In.ReadToEnd()
    $event = $raw | ConvertFrom-Json
    $tool = [string]$event.tool_name
    $cwd = [string]$event.cwd
    if (-not $cwd) { $cwd = $env:CLAUDE_PROJECT_DIR }
    if (-not $cwd) { $cwd = (Get-Location).Path }
    $input_ = $event.tool_input
    if ($tool -eq 'Bash' -or $tool -eq 'PowerShell') {
        # git and gh, run in a project
        $command = [string]$input_.command
        if ($command -notmatch '(^|[^A-Za-z0-9_.-])(git|gh)([^A-Za-z0-9_-]|$)') { exit 0 }
        if (-not (Test-Reaches $cwd $command)) { exit 0 }
        $gated = '(git|gh)[^|;&]*\s(merge|push|commit)'
        $subject = $command
    } elseif (@('Edit', 'Write', 'MultiEdit', 'NotebookEdit') -contains $tool) {
        $file = [string]$input_.file_path
        if (-not $file) { $file = [string]$input_.notebook_path }
        $file = $file -replace '\\', '/'
        # By file, what the edit writes that is gated: a stamp, a
        # confirmation (written, or a kind confirmed by default), a waiver,
        # an acceptance.
        if ($file -match '(^|/)\.armature/') { $gated = $null }
        elseif ($file -match '(^|/)ledger\.toml$') {
            $gated = 'confirmed|kind\s*=\s*["'']?(chosen|standard)' }
        elseif ($file -match '(^|/)waivers\.toml$') { $gated = 'confirmed|\[\[ *waiver' }
        elseif ($file -match '(^|/)reviews/') { $gated = 'accepted' }
        else { exit 0 }
        if (-not (Test-EditProject $cwd $file)) { exit 0 }
        $subject = (@($input_.new_string, $input_.content, $input_.new_source) +
                    @($input_.edits | ForEach-Object { $_.new_string }) |
                    Where-Object { $_ }) -join "`n"
    } else {
        exit 0
    }
    $uv = Find-Uv
    if (-not $uv) {
        if ($null -eq $gated -or $subject -match $gated) {
            Deny ('Armature (ADR 0011): this action is gated, and the gate runs on uv, ' +
                  'which is not installed. Install uv ' +
                  '(https://docs.astral.sh/uv/getting-started/installation/), then retry.')
        }
        exit 0
    }
    Invoke-Engine $uv @('gate.hook') $raw
}

if ($argv.Count -eq 0) {
    [Console]::Error.WriteLine('usage: armature.ps1 <gate|ledger|hook> [args...]')
    exit 2
}
if ($argv[0] -eq 'hook') { Invoke-Hook }
$uv = Find-Uv
if (-not $uv) {
    [Console]::Error.WriteLine('error: the engine runs on uv, which is not installed; ' +
        'install uv (https://docs.astral.sh/uv/getting-started/installation/)')
    exit 2
}
Invoke-Engine $uv ([string[]]$argv) $null
