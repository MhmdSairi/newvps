#!/bin/bash
# SSH Login Banner - Ubuntu ASCII Logo & Clean Side-by-Side Specs

[ -t 1 ] || return 0 2>/dev/null || exit 0

# Variabel Sistem
_os="$( . /etc/os-release 2>/dev/null; echo "${PRETTY_NAME:-Ubuntu 24.04}" )"
_kernel="$(uname -r 2>/dev/null)"
_host="$(hostname 2>/dev/null)"
_user="$(whoami 2>/dev/null)"
_uptime="$(uptime -p 2>/dev/null | sed 's/^up //')"; : "${_uptime:=just now}"
_cpu="$(grep -m1 'model name' /proc/cpuinfo 2>/dev/null | cut -d: -f2 | sed 's/^ *//; s/  */ /g')"
_cores="$(nproc 2>/dev/null)"; : "${_cpu:=CPU}"
_mem="$(free -h 2>/dev/null | awk '/^Mem:/ {print $3 " / " $2}')"
_disk="$(df -h / 2>/dev/null | awk 'NR==2 {print $3 " / " $2 " (" $5 ")"}')"
_api_port="${PORT:-8080}"

printf '\n'

# Menampilkan Logo ASCII Ubuntu di Kiri dan Spesifikasi di Kanan secara Berdampingan
cat << EOF
       _-----_       User   : ${_user}@${_host}
      (       \\      OS     : ${_os}
    __-\\-_--_-_/__    Kernel : ${_kernel}
   (               )   Uptime : ${_uptime}
  /                 \\  CPU    : ${_cpu} (${_cores} cores)
 |                   | Memory : ${_mem}
 |                   | Disk   : ${_disk}
  \\                 /  Port   : ${_api_port} (Railway HTTP Ingress)
   \\___-___-___-___/  
EOF

printf '\n'
printf '  ────────────────────────────────────────────────────────────\n'
printf '  Tip: Bind your API server or AI agent to port %s\n' "${_api_port}"
printf '       to access it directly via your Railway public domain.\n'
printf '\n'
