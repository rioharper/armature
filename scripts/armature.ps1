# The plugin's own engine, run through uv: scripts/armature.sh for
# PowerShell, where there is no Git Bash. Same verbs, same venv under
# $env:CLAUDE_PLUGIN_DATA, same behaviour:
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File `
#       "${CLAUDE_PLUGIN_ROOT}/scripts/armature.ps1" check
#
# Written for Windows PowerShell 5.1: no &&, no ternary, no ?? . A native
# command's stderr under 'Stop' throws in 5.1, so errors stay 'Continue'.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$argv = @($args)
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

if ($argv.Count -eq 0) {
    [Console]::Error.WriteLine('usage: armature.ps1 <check|ledger> [args...]')
    exit 2
}
$uv = Find-Uv
if (-not $uv) {
    [Console]::Error.WriteLine('error: the engine runs on uv, which is not installed; ' +
        'install uv (https://docs.astral.sh/uv/getting-started/installation/)')
    exit 2
}
$env:UV_PROJECT_ENVIRONMENT = Join-Path $data 'venv'
$env:PYTHONPYCACHEPREFIX = Join-Path $data 'pycache'
$tail = @()
if ($argv.Count -gt 1) { $tail = $argv[1..($argv.Count - 1)] }
& $uv run --quiet --frozen --no-dev --project (Join-Path $root 'engine') python -m ('armature.' + $argv[0]) @tail
exit $LASTEXITCODE
