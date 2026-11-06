#!/bin/bash
# SSH Login Banner - Clean Monochromatic Lightning Bolt & Specs

[ -t 1 ] || return 0 2>/dev/null || exit 0

# Sembunyikan pesan default MOTD Ubuntu ("Welcome to Ubuntu...")
if [ -d /etc/update-motd.d ]; then
    for f in /etc/update-motd.d/*; do
        [ -f "$f" ] && chmod -x "$f" 2>/dev/null
    done
fi
[ -f /etc/motd ] && echo "" > /etc/motd

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

# Layout Berdampingan: Icon Petir (Lightning) di Kiri & Spesifikasi Sistem di Kanan
printf "         ⚡          User   : %s@%s\n" "$_user" "$_host"
printf "        ⚡⚡         OS     : %s\n" "$_os"
printf "       ⚡⚡⚡        Kernel : %s\n" "$_kernel"
printf "      ⚡⚡⚡⚡       Uptime : %s\n" "$_uptime"
printf "     ⚡⚡⚡⚡⚡      CPU    : %s (%s cores)\n" "$_cpu" "$_cores"
printf "    ⚡⚡⚡⚡⚡⚡     Memory : %s\n" "$_mem"
printf "         ⚡⚡        Disk   : %s\n" "$_disk"
printf "         ⚡⚡        Port   : %s (Railway HTTP Ingress)\n" "$_api_port"
printf "         ⚡⚡        \n"

printf '\n'
printf '  ────────────────────────────────────────────────────────────\n'
printf '  Tip: Bind your API server or AI agent to port %s\n' "${_api_port}"
printf '       to access it directly via your Railway public domain.\n'
printf '       Management Bot @forariey\n'
printf '\n'
