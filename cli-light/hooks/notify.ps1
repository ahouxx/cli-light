param([string]$state)

# Debug log
$logFile = "$env:USERPROFILE\.cli-light\hook-debug.log"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logFile -Value "$timestamp - Hook called with state: $state" -ErrorAction SilentlyContinue

# Walk up process tree to find the real CLI process (claude.exe / opencode.exe / kimi-cli.exe)
$agentId = "cli-unknown"
$currentPid = $PID

# Try Get-CimInstance first, fall back to Get-Process + WMI filter
function Get-ParentProcessId {
    param([int]$ProcessId)
    try {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction Stop
        return $proc.ParentProcessId
    } catch {
        # Get-CimInstance may need admin; fall back to Get-Process
        try {
            $proc = Get-WmiObject Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction Stop
            return $proc.ParentProcessId
        } catch {
            return 0
        }
    }
}

for ($i = 0; $i -lt 5; $i++) {
    $ppid = Get-ParentProcessId $currentPid
    if ($ppid -eq 0) { break }
    $pname = (Get-Process -Id $ppid -ErrorAction SilentlyContinue).ProcessName
    if ($pname -eq 'claude' -or $pname -eq 'opencode' -or $pname -eq 'kimi-cli' -or $pname -eq 'codex') {
        $agentId = "cli-$ppid"
        break
    }
    $currentPid = $ppid
}

try {
    $body = ConvertTo-Json -InputObject @{state=$state; agent=$agentId} -Compress
    Add-Content -Path $logFile -Value "$timestamp - Sending to agent: $agentId" -ErrorAction SilentlyContinue
    Invoke-WebRequest -Uri http://localhost:9876/hook -Method POST -Body $body `
        -ContentType "application/json" -UseBasicParsing | Out-Null
    Add-Content -Path $logFile -Value "$timestamp - HTTP request succeeded" -ErrorAction SilentlyContinue
} catch {
    Add-Content -Path $logFile -Value "$timestamp - HTTP request failed: $_" -ErrorAction SilentlyContinue
    exit 0
}
