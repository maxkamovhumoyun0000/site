#!/usr/bin/env bash
# Diamond Education local printer installer for Debian/Ubuntu, Fedora and Arch.
# It installs a per-user service; no receipt data is stored on this computer.
set -euo pipefail

APP_DIR="${HOME}/.local/share/DiamondEducation/PrintAgent"
SERVICE_DIR="${HOME}/.config/systemd/user"
SOURCE_URL="${DIAMOND_PRINT_AGENT_SOURCE:-https://diamond-education.uz/downloads/diamond-print-agent.py}"

install_cups() {
  if command -v lp >/dev/null && command -v lpstat >/dev/null && command -v lpadmin >/dev/null && command -v lpinfo >/dev/null; then return; fi
  echo "CUPS va raw termal-printer vositalari o'rnatilmoqda..."
  if command -v apt-get >/dev/null; then
    sudo apt-get update && sudo apt-get install -y cups
  elif command -v dnf >/dev/null; then
    sudo dnf install -y cups
  elif command -v pacman >/dev/null; then
    sudo pacman -Sy --needed --noconfirm cups
  else
    echo "CUPS ni tizimingiz package manageri orqali o'rnating, so'ng skriptni qayta ishga tushiring." >&2
    exit 1
  fi
}

configure_raw_thermal_queue() {
  if lpstat -p 2>/dev/null | grep -Eqi 'xp[-_ ]?58|xprinter|thermal|receipt|pos[-_ ]?58|58mm'; then
    return
  fi
  mapfile -t usb_devices < <(lpinfo -v 2>/dev/null | awk '$1 == "direct" && $2 ~ /^usb:\/\// && $0 ~ /[Xx][Pp][- ]?58|[Xx][Pp]rinter|[Tt]hermal|[Rr]eceipt/ {print $2}')
  if [ "${#usb_devices[@]}" -eq 1 ]; then
    sudo lpadmin -p Diamond_XP58IIL -E -v "${usb_devices[0]}" -m raw
    echo "XP-58IIL uchun Diamond_XP58IIL raw queue yaratildi."
  elif [ "${#usb_devices[@]}" -gt 1 ]; then
    echo "Bir nechta termal USB printer topildi; noto'g'ri printer tanlanmasligi uchun raw queue yaratilmagan." >&2
  else
    echo "XP-58IIL USB qurilmasi topilmadi; printerni ulang va installerni qayta ishga tushiring." >&2
  fi
}

if ! command -v python3 >/dev/null; then
  echo "Python 3 topilmadi. Avval Python 3 ni o'rnating." >&2
  exit 1
fi
install_cups
configure_raw_thermal_queue

mkdir -p "$APP_DIR" "$SERVICE_DIR"
if command -v curl >/dev/null; then
  curl --fail --silent --show-error --location "$SOURCE_URL" --output "$APP_DIR/diamond-print-agent.py"
elif command -v wget >/dev/null; then
  wget --https-only --quiet "$SOURCE_URL" -O "$APP_DIR/diamond-print-agent.py"
else
  echo "curl yoki wget topilmadi; bittasini o'rnating." >&2
  exit 1
fi
chmod 700 "$APP_DIR/diamond-print-agent.py"

cat > "$SERVICE_DIR/diamond-print-agent.service" <<'UNIT'
[Unit]
Description=Diamond Education local receipt printer
After=default.target

[Service]
Type=simple
ExecStart=/usr/bin/env python3 %h/.local/share/DiamondEducation/PrintAgent/diamond-print-agent.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
UNIT

systemctl --user daemon-reload
systemctl --user enable --now diamond-print-agent.service
sleep 1
if curl --fail --silent http://127.0.0.1:18765/health >/dev/null; then
  echo "Tayyor. Agent ishga tushdi. Test va haqiqiy chek kesilishidan oldin taxminan 15 mm tashqariga chiqariladi. Developer sahifasidan 'Test chek chiqarish' tugmasini bosing."
else
  echo "Agent ishga tushmadi. Tekshirish: systemctl --user status diamond-print-agent.service" >&2
  exit 1
fi
