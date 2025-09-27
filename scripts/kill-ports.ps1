$ErrorActionPreference = 'SilentlyContinue'

param(
  [int[]] $Ports = @(8101, 8102, 8001, 8000, 5173)
)

function Stop-Ports {
  param([int[]] $Ports)
  $killed = @()
  foreach ($p in $Ports) {
    # Try Get-NetTCPConnection first
    $pids = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue |
      Select-Object -ExpandProperty OwningProcess -Unique

    # Fallback to netstat if needed
    if (-not $pids) {
      $lines = netstat -ano | Select-String -Pattern (":" + $p + "\s")
      $pids = @()
      foreach ($line in $lines) {
        $parts = ($line.ToString().Trim() -split "\s+")
        if ($parts.Length -gt 0) {
          $procId = $parts[$parts.Length - 1]
          if ($procId -match '^[0-9]+$') { $pids += [int]$procId }
        }
      }
      $pids = $pids | Sort-Object -Unique
    }

    foreach ($procId in $pids) {
      try { taskkill /PID $procId /F /T | Out-Null } catch {}
      $killed += $procId
    }
    Write-Output ("Cleared port {0}" -f $p)
  }
  if ($killed.Count -gt 0) {
    Write-Output ("Killed PIDs: " + (($killed | Sort-Object -Unique) -join ", "))
  } else {
    Write-Output "No processes found on specified ports."
  }
}

Stop-Ports -Ports $Ports


