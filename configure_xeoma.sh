#!/bin/bash

MACS_FILE=/config/macs.txt

#-----------------------------------------------------------------------------------------------------------------------

. /etc/envvars.merged

set -e

#-----------------------------------------------------------------------------------------------------------------------

function ts {
  echo `date '+[%Y-%m-%d %H:%M:%S]'`
}

#-----------------------------------------------------------------------------------------------------------------------

if [ -n "$MAC_ADDRESS" ]; then
  echo "$(ts) Setting container mac address to $MAC_ADDRESS"
  ip link set eth0 address $MAC_ADDRESS
fi

# Older images append to this history but do not know about the ownership marker.
# Capture its state before our own entry to detect an intervening downgrade/start.
previous_startup_history=missing
if [[ -f "$MACS_FILE" ]]; then
  previous_startup_history=$(cksum < "$MACS_FILE")
fi

# Save some information about the interface that talks to the internet, in case we need it later.
iface=$(ip route show default | awk '/default/ {print $5}')
mac_address=$(cat /sys/class/net/$iface/address)
echo "$(ts) $iface $mac_address" >> "$MACS_FILE"

#-----------------------------------------------------------------------------------------------------------------------

# Delete before creating the symlinks, for two reasons: (1) the symlink might be left-over from a previous container (and
# therefore invalid in this container), and (2) if the container is restarted, there will already be a symlink, causing
# a new symlink like /usr/local/Xeoma/config/config

# Clean up any mess from before
rm -f /config/config

# NOTE: Around version 18.7.10 /.config is no longer used. Instead /usr/local/Xeoma is used whether or not the software
# is installed.

# == Old code below (for backwards compatibility)
# If we were to install Xeoma, it would run in /usr/local/Xeoma. But we're not, so it runs in /.config
mkdir -p /.config

rm -f /.config/Xeoma
ln -s /config /.config/Xeoma

rm -f /config/XeomaArchive
ln -s /archive /config/XeomaArchive

# == New code below.
rm -f /usr/local/Xeoma
ln -s /config /usr/local/Xeoma

rm -f /usr/local/Xeoma/XeomaArchive
ln -s /archive /usr/local/Xeoma/XeomaArchive

#-----------------------------------------------------------------------------------------------------------------------

# Migrate once per UID/GID. Read the marker as data, never as shell code.
ownership_marker=/config/.xeoma-ownership
ownership_version="v2:$(id -u abc):$(id -g abc):$previous_startup_history"
if [[ ! -f "$ownership_marker" ]] || [[ "$(cat "$ownership_marker")" != "$ownership_version" ]]; then
  echo "$(ts) Updating storage ownership for $(id -u abc):$(id -g abc)"
  rm -f "$ownership_marker"
  # Do not follow symlinks into other mounts while changing ownership.
  # A separately mounted read-only password file must retain its host ownership.
  find /config -path /config/xeoma_password -prune -o -exec chown -h abc:abc {} +
  chown -hR abc:abc /archive /archive-cache
else
  echo "$(ts) Storage ownership already initialized; skipping recursive ownership changes."
fi
# These paths may be newly created on each start; fixing them does not traverse storage.
chown -h abc:abc /config /archive /archive-cache /config/macs.txt /config/XeomaArchive
# Publish only after ownership changes succeed, including this start's history entry.
# Even a skipped migration must advance the history checkpoint.
marker_tmp=$(mktemp "${ownership_marker}.XXXXXX")
printf 'v2:%s:%s:%s\n' "$(id -u abc)" "$(id -g abc)" "$(cksum < "$MACS_FILE")" > "$marker_tmp"
chown abc:abc "$marker_tmp"
mv -f "$marker_tmp" "$ownership_marker"
umask "${UMASK:-022}"
export HOME=/config XDG_CONFIG_HOME=/.config

echo "$(ts) Setting the password"
# Pass the password unchanged and let Xeoma validate it. Its diagnostics may echo
# rejected password fragments, so report failure without copying those diagnostics.
if s6-setuidgid abc /usr/bin/xeoma -setpassword "$PASSWORD" > /dev/null 2>&1; then
  :
else
  status=$?
  echo "$(ts) ERROR: Xeoma's password-setting command failed (exit status $status). Startup stopped." >&2
  echo "$(ts) Check the configured password and Xeoma's requirements, then restart the container." >&2
  echo "$(ts) Xeoma's raw output is withheld because it may contain the password." >&2
  exit "$status"
fi

# Not sure why this is necessary, but without it, I can't connect to the server
s6-setuidgid abc /usr/bin/xeoma -showpassword > /dev/null 2>&1

exit 0
