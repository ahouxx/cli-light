# CLI Light — Hook installer for Claude Code / Kimi Code / OpenCode
# Install:   powershell -ExecutionPolicy Bypass -File install.ps1
# Uninstall: powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall
# Skip desktop shortcut: powershell -ExecutionPolicy Bypass -File install.ps1 -NoDesktop
param([switch]$Uninstall, [switch]$NoDesktop)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$NotifyPs1 = Join-Path $ScriptDir "hooks\notify.ps1"

# Build the command string for hook configs (PowerShell-escaped for JSON)
$CmdBase = "powershell -NoProfile -ExecutionPolicy Bypass -File `"$NotifyPs1`""

Write-Host @"

  CLI Light Hook Installer
  =========================
"@ -ForegroundColor Cyan

# ── Helpers ─────────────────────────────────────────────────
function Write-Step { param([string]$Text) Write-Host "  $Text" -NoNewline }
function Write-OK { Write-Host "  OK" -ForegroundColor Green }
function Write-Skip { Write-Host "  (skipped)" -ForegroundColor DarkGray }
function Write-Fail { param([string]$Msg) Write-Host "  FAIL — $Msg" -ForegroundColor Red }

# ── Detect Python (for generating launch.vbs) ───────────────
function Find-Pythonw {
    # Scan %LOCALAPPDATA%\Programs\Python for any pythonw.exe
    $localPy = "$env:LOCALAPPDATA\Programs\Python"
    if (Test-Path $localPy) {
        $found = Get-ChildItem $localPy -Recurse -Filter pythonw.exe -ErrorAction SilentlyContinue `
            | Select-Object -First 1 -ExpandProperty FullName
        if ($found) { return $found }
    }
    # Fall back: try "where pythonw"
    try {
        $fromPath = (Get-Command pythonw -ErrorAction Stop).Source
        if ($fromPath) { return $fromPath }
    } catch {}
    return "pythonw.exe"
}

# ── Claude Code ─────────────────────────────────────────────
function Install-ClaudeHooks {
    Write-Step "[Claude Code]"
    $settingsPath = "$env:USERPROFILE\.claude\settings.json"

    if (-not (Test-Path $settingsPath)) {
        # Create new settings file with hooks only
        $hooksJson = _Build-ClaudeHooksJson
        $content = "{`"hooks`": $hooksJson}"
        $parent = Split-Path $settingsPath -Parent
        if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
        Set-Content $settingsPath -Value $content -Encoding UTF8
        Write-OK
        return
    }

    try {
        $settings = Get-Content $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        Write-Fail "Cannot parse settings.json (invalid JSON). Please fix manually."
        return
    }

    # Build new hooks object
    $hooksObj = _Build-ClaudeHooksPSCustomObject

    # Merge: add/replace "hooks" key
    $settings | Add-Member -MemberType NoteProperty -Name "hooks" -Value $hooksObj -Force

    # Write back preserving as much structure as possible
    $newJson = $settings | ConvertTo-Json -Depth 6
    Set-Content $settingsPath -Value $newJson -Encoding UTF8
    Write-OK
}

function Remove-ClaudeHooks {
    Write-Step "[Claude Code]"
    $settingsPath = "$env:USERPROFILE\.claude\settings.json"
    if (-not (Test-Path $settingsPath)) { Write-Skip; return }
    try {
        $settings = Get-Content $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $settings.PSObject.Properties.Remove("hooks")
        $newJson = $settings | ConvertTo-Json -Depth 6
        Set-Content $settingsPath -Value $newJson -Encoding UTF8
        Write-OK
    } catch {
        Write-Fail "Cannot parse settings.json. Remove 'hooks' key manually."
    }
}

function _Build-ClaudeHooksJson {
    # Return raw JSON string for the hooks object value
    $run = "$CmdBase running"
    $need = "$CmdBase needs_input"
    $done = "$CmdBase done"
    return @"
{
  "UserPromptSubmit": [{
    "matcher": "",
    "hooks": [{ "type": "command", "command": "$run" }]
  }],
  "PermissionRequest": [{
    "matcher": "",
    "hooks": [{ "type": "command", "command": "$need" }]
  }],
  "PostToolUse": [{
    "matcher": "",
    "hooks": [{ "type": "command", "command": "$run" }]
  }],
  "Stop": [{
    "hooks": [{ "type": "command", "command": "$done" }]
  }]
}
"@
}

function _Build-ClaudeHooksPSCustomObject {
    $hooks = @{
        UserPromptSubmit = @(
            @{
                matcher = ""
                hooks = @(
                    @{ type = "command"; command = "$CmdBase running" }
                )
            }
        )
        PermissionRequest = @(
            @{
                matcher = ""
                hooks = @(
                    @{ type = "command"; command = "$CmdBase needs_input" }
                )
            }
        )
        PostToolUse = @(
            @{
                matcher = ""
                hooks = @(
                    @{ type = "command"; command = "$CmdBase running" }
                )
            }
        )
        Stop = @(
            @{
                hooks = @(
                    @{ type = "command"; command = "$CmdBase done" }
                )
            }
        )
    }
    return $hooks
}

# ── Kimi Code ───────────────────────────────────────────────
function Install-KimiHooks {
    Write-Step "[Kimi Code]  "
    $configPath = "$env:USERPROFILE\.kimi\config.toml"
    if (-not (Test-Path $configPath)) {
        Write-Skip; return
    }
    try {
        $content = Get-Content $configPath -Raw -Encoding UTF8
        $hooksBlock = @"
hooks = [
  { event = "UserPromptSubmit", command = '$CmdBase running' },
  { event = "PreToolUse",       command = '$CmdBase needs_input' },
  { event = "PostToolUse",      command = '$CmdBase running' },
  { event = "Stop",             command = '$CmdBase done' },
]
"@
        # Replace existing hooks block, or append before EOF
        if ($content -match 'hooks\s*=\s*\[') {
            $newContent = $content -replace 'hooks\s*=\s*\[[^\]]*\]', $hooksBlock
        } else {
            $newContent = $content.TrimEnd() + "`n`n$hooksBlock`n"
        }
        Set-Content $configPath -Value $newContent -Encoding UTF8 -NoNewline
        Write-OK
    } catch {
        Write-Fail $_
    }
}

function Remove-KimiHooks {
    Write-Step "[Kimi Code]  "
    $configPath = "$env:USERPROFILE\.kimi\config.toml"
    if (-not (Test-Path $configPath)) { Write-Skip; return }
    try {
        $content = Get-Content $configPath -Raw -Encoding UTF8
        $newContent = $content -replace 'hooks\s*=\s*\[[^\]]*\]', 'hooks = []'
        Set-Content $configPath -Value $newContent -Encoding UTF8 -NoNewline
        Write-OK
    } catch { Write-Skip }
}

# ── OpenCode ────────────────────────────────────────────────
function Install-OpenCodeHooks {
    Write-Step "[OpenCode]   "
    $configDir = "$env:USERPROFILE\.config\opencode"
    $configPath = Join-Path $configDir "hooks.json"

    if (-not (Test-Path $configDir)) {
        New-Item -ItemType Directory -Path $configDir -Force | Out-Null
    }

    $hooksObj = @{
        hooks = @{
            UserPromptSubmit = @(
                @{
                    matcher = ""
                    hooks = @(
                        @{ type = "command"; command = "$CmdBase running" }
                    )
                }
            )
            Stop = @(
                @{
                    hooks = @(
                        @{ type = "command"; command = "$CmdBase done" }
                    )
                }
            )
        }
    }

    $json = $hooksObj | ConvertTo-Json -Depth 6
    Set-Content $configPath -Value $json -Encoding UTF8
    Write-Host "  OK (UserPromptSubmit + Stop)" -ForegroundColor Green
}

function Remove-OpenCodeHooks {
    Write-Step "[OpenCode]   "
    $configPath = "$env:USERPROFILE\.config\opencode\hooks.json"
    if (-not (Test-Path $configPath)) { Write-Skip; return }
    Remove-Item $configPath -Force
    Write-OK
}

# ── Generate launch.vbs ─────────────────────────────────────
function New-LaunchVbs {
    $vbsPath = Join-Path $ScriptDir "launch.vbs"
    Write-Step "launch.vbs"
    $pythonw = Find-Pythonw

    $mainScript = Join-Path $ScriptDir "cli_light.py"

    $vbsContent = @"
' CLI Light launcher (auto-generated)
Set shell = CreateObject("WScript.Shell")
Set fso   = CreateObject("Scripting.FileSystemObject")

scriptDir  = fso.GetParentFolderName(WScript.ScriptFullName)
mainScript = fso.BuildPath(scriptDir, "cli_light.py")

pythonw = ""
' Scan %LOCALAPPDATA%\Programs\Python for any Python3* install
localPy = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\"
If fso.FolderExists(localPy) Then
    For Each folder In fso.GetFolder(localPy).SubFolders
        pyPath = folder.Path & "\pythonw.exe"
        If fso.FileExists(pyPath) Then
            pythonw = pyPath
            Exit For
        End If
    Next
End If

' Check common root installs
If pythonw = "" Then
    For Each ver In Array("314","313","312","311","310","39","38")
        testPath = "C:\Python" & ver & "\pythonw.exe"
        If fso.FileExists(testPath) Then
            pythonw = testPath
            Exit For
        End If
    Next
End If

' Fall back to PATH
If pythonw = "" Then
    pythonw = "pythonw.exe"
End If

shell.Run """" & pythonw & """ """ & mainScript & """", 0, False
"@
    Set-Content $vbsPath -Value $vbsContent -Encoding ASCII
    Write-Host "  OK (pythonw: $pythonw)" -ForegroundColor Green
}

# ── Desktop shortcut ─────────────────────────────────────────
function Add-DesktopShortcut {
    $desktopDir = [Environment]::GetFolderPath('Desktop')
    $shortcutPath = Join-Path $desktopDir "CLI Light.lnk"
    $vbsPath = Join-Path $ScriptDir "launch.vbs"

    $WshShell = New-Object -ComObject WScript.Shell
    $shortcut = $WshShell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $vbsPath
    $shortcut.WorkingDirectory = $ScriptDir
    $shortcut.Description = "CLI Light — desktop traffic light for CLI status"
    $shortcut.Save()
    Write-Host "  OK -> $shortcutPath" -ForegroundColor Green
}

function Remove-DesktopShortcut {
    $desktopDir = [Environment]::GetFolderPath('Desktop')
    $shortcutPath = Join-Path $desktopDir "CLI Light.lnk"
    if (Test-Path $shortcutPath) {
        Remove-Item $shortcutPath -Force
        Write-OK
    } else {
        Write-Skip
    }
}

# ── Kill running instances ──────────────────────────────────
function Stop-CliLight {
    Write-Step "Running processes"
    $killed = $false
    Get-Process python -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            $cmdline = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine
            if ($cmdline -like '*cli_light*') {
                Stop-Process -Id $_.Id -Force
                $killed = $true
            }
        } catch {}
    }
    if ($killed) { Write-OK } else { Write-Skip }
}

# ── Main ────────────────────────────────────────────────────
try {
    if ($Uninstall) {
        Write-Host "`nRemoving hooks...`n"
        Remove-ClaudeHooks
        Remove-KimiHooks
        Remove-OpenCodeHooks
        Write-Host ""
        Write-Step "Desktop shortcut"
        Remove-DesktopShortcut
        Write-Step "Running processes"
        Stop-CliLight
    } else {
        Write-Host "`nInstalling hooks...`n"
        Install-ClaudeHooks
        Install-KimiHooks
        Install-OpenCodeHooks
        Write-Host ""
        New-LaunchVbs
        if (-not $NoDesktop) {
            Write-Step "Desktop shortcut"
            Add-DesktopShortcut
        }
    }
} catch {
    Write-Host "`nError: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`nDone. Restart your CLI tools for changes to take effect.`n"
