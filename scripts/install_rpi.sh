#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/server-manager"
CONFIG_DIR="/etc/server-manager"
DATA_DIR="/var/lib/server-manager"
USER_NAME="server-manager"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo scripts/install_rpi.sh" >&2
  exit 1
fi

if ! id "${USER_NAME}" >/dev/null 2>&1; then
  useradd --system --home-dir "${APP_DIR}" --shell /usr/sbin/nologin "${USER_NAME}"
fi

mkdir -p "${APP_DIR}" "${CONFIG_DIR}" "${DATA_DIR}"
rsync -a --delete \
  --exclude ".venv" \
  --exclude "__pycache__" \
  --exclude ".pytest_cache" \
  --exclude "data" \
  ./ "${APP_DIR}/"

python3 -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/python" -m pip install --upgrade pip
"${APP_DIR}/.venv/bin/python" -m pip install -e "${APP_DIR}"

if [[ ! -f "${CONFIG_DIR}/server-manager.env" ]]; then
  install -m 0600 systemd/server-manager.env.example "${CONFIG_DIR}/server-manager.env"
fi

if [[ ! -f "${CONFIG_DIR}/services.toml" ]]; then
  install -m 0640 config/services.example.toml "${CONFIG_DIR}/services.toml"
fi

install -m 0644 systemd/server-manager.service /etc/systemd/system/server-manager.service
chown -R "${USER_NAME}:${USER_NAME}" "${APP_DIR}" "${DATA_DIR}"
chown -R root:"${USER_NAME}" "${CONFIG_DIR}"
chmod 0750 "${CONFIG_DIR}"
chmod 0640 "${CONFIG_DIR}/services.toml"

systemctl daemon-reload
echo "Edit ${CONFIG_DIR}/server-manager.env and ${CONFIG_DIR}/services.toml, then run:"
echo "  systemctl enable --now server-manager.service"
