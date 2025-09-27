#!/usr/bin/env bash
set -euo pipefail

PORTS=(8101 8102 8000 8001 5173)
if [ "$#" -gt 0 ]; then
  PORTS=("$@")
fi

killed=()
for p in "${PORTS[@]}"; do
  if command -v lsof >/dev/null 2>&1; then
    pids=$(lsof -t -i :"$p" || true)
  else
    # fallback to netstat/ss
    if command -v ss >/dev/null 2>&1; then
      pids=$(ss -lptn "sport = :$p" 2>/dev/null | awk -F',' '/pid=/ {print $2}' | sed 's/pid=//' | xargs -r echo)
    else
      pids=$(netstat -anp 2>/dev/null | grep ":$p " | awk '{print $7}' | cut -d'/' -f1 | xargs -r echo)
    fi
  fi
  if [ -n "${pids:-}" ]; then
    for pid in $pids; do
      if [[ "$pid" =~ ^[0-9]+$ ]]; then
        kill -9 "$pid" || true
        killed+=("$pid")
      fi
    done
    echo "Cleared port $p"
  else
    echo "No process found on port $p"
  fi
done

if [ ${#killed[@]} -gt 0 ]; then
  printf 'Killed PIDs: %s\n' "$(printf '%s ' "${killed[@]}" | sed 's/ $//')"
fi


