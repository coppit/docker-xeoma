#!/usr/bin/with-contenv bash
set -e

if [[ ! "${UMASK:-022}" =~ ^0?[0-7]{3}$ ]]; then
  echo "UMASK must contain three or four octal digits." >&2
  exit 1
fi
if [[ ! "$PUID" =~ ^[0-9]+$ || ! "$PGID" =~ ^[0-9]+$ ]] ||
   [[ "$(id -u abc)" != "$PUID" || "$(id -g abc)" != "$PGID" ]]; then
  echo "PUID/PGID must be numeric IDs successfully assigned to the abc user." >&2
  exit 1
fi

# Root-only snapshot for config-file/environment precedence; rebuilt on every start.
mkdir -p /run/xeoma
chmod 700 /run/xeoma
rm -f /run/xeoma/ready

# Rebuild registration on every start, including when configuration changes or fails.
rm -f /etc/cron.hourly/update_xeoma
mkdir -p /etc/crontabs

# Preserve unrelated root jobs and remove only our tagged entry, even on failed startup.
(crontab -u root -l 2>/dev/null || true) |
  sed '/# xeoma-auto-update$/d' > /etc/crontabs/root
chmod 600 /etc/crontabs/root
crontab -u root /etc/crontabs/root
(umask 077; export -p > /run/xeoma/environment.sh)
trap 'for file in /config/xeoma.conf /config/xeoma_password; do
  if [[ -f "$file" ]] && ! mountpoint -q "$file"; then chown abc:abc "$file"; fi
done' EXIT
/usr/local/lib/xeoma/parse_config_file.sh

# Installation is root-owned and must remain executable by the abc user.
umask 022
/usr/local/lib/xeoma/install_xeoma.py
/usr/local/lib/xeoma/configure_xeoma.sh

# Prepare the crontab for LinuxServer init-crontab-config, which depends on this step.
(
  unset VERSION
  . /etc/envvars.merged
  case "$VERSION" in
    latest|latest_beta)
      printf '%s\n' '17 * * * * /usr/local/lib/xeoma/update_xeoma.sh > /proc/1/fd/1 2> /proc/1/fd/2 # xeoma-auto-update' \
        >> /etc/crontabs/root
      ;;
  esac
)

touch /run/xeoma/ready
