#!/bin/bash

# These need to match 40_install_xeoma.py
INSTALL_LOCATION=/files/xeoma
LAST_INSTALLED_BREADCRUMB=$INSTALL_LOCATION/last_installed_version.txt

#-----------------------------------------------------------------------------------------------------------------------

function ts {
  echo `date '+[%Y-%m-%d %H:%M:%S]'`
}

#-----------------------------------------------------------------------------------------------------------------------

function get_installed_version {
  if [[ -e "$LAST_INSTALLED_BREADCRUMB" ]];then
    cat "$LAST_INSTALLED_BREADCRUMB" | tr -d '\n'
  else
    echo -n ""
  fi
}

#-----------------------------------------------------------------------------------------------------------------------

# Read saved settings in a separate shell, as the installer does. Never let an
# inherited VERSION hide missing settings or fall back to latest in a cron job.
if ! version=$(/bin/bash -c '
  unset VERSION
  [[ -f /etc/envvars.merged && -r /etc/envvars.merged ]] || exit 1
  . /etc/envvars.merged >/dev/null || exit 1
  [[ -n "$VERSION" ]] || exit 1
  printf "%s" "$VERSION"
' 2>/dev/null); then
  echo "$(ts) Cannot read saved VERSION from /etc/envvars.merged. Skipping auto-update." >&2
  exit 1
fi

case "$version" in
  latest|latest_beta) ;;
  *)
    echo "$(ts) Skipping auto-update: VERSION is not latest or latest_beta."
    exit 0
    ;;
esac

echo "$(ts) Attempting to auto-update Xeoma"

echo "vvvvvvvvvvvvvvvvvvv"
last_installed_version=$(get_installed_version)
/etc/my_init.d/40_install_xeoma.py
new_installed_version=$(get_installed_version)
echo "^^^^^^^^^^^^^^^^^^^"

if [[ "$last_installed_version" != "$new_installed_version" ]];then
  echo "$(ts) Xeoma has been updated. Restarting the service."
  pkill xeoma

  # The phusion framework will restart it for us
else
  echo "$(ts) Xeoma has not been updated."
fi
