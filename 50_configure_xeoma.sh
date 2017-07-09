#!/bin/bash

set -e

FIXED_CONFIG_FILE=/tmp/xeoma.conf
MAC_FILE=/config/macs.txt

#-----------------------------------------------------------------------------------------------------------------------

function ts {
  echo [`date '+%b %d %X'`]
}

#-----------------------------------------------------------------------------------------------------------------------

source "$FIXED_CONFIG_FILE"

#-----------------------------------------------------------------------------------------------------------------------

# Save some information about the interface that talks to the internet, in case we need it later.

# Have to parse /proc/net/route because there is no "ip" to do this: iface=$(ip route show default | awk '/default/ {print $5}')
iface=$(grep -E '^\S+\s+00000000' /proc/net/route | awk '{print $1}')
mac_address=$(cat /sys/class/net/$iface/address)
echo "$(ts) $iface $mac_address" >> "$MAC_FILE"

#-----------------------------------------------------------------------------------------------------------------------

# If we were to install Xeoma, it would run in /usr/local/Xeoma. But we're not, so it runs in /.config
mkdir -p /.config

# Delete before creating the symlinks, for two reasons: (1) the symlink might be left-over from a previous container (and
# therefore invalid in this container), and (2) if the container is restarted, there will already be a symlink, causing
# a new symlink like /usr/local/Xeoma/config/config
rm -f /.config/Xeoma
ln -s /config /.config/Xeoma

rm -f /config/XeomaArchive
ln -s /archive /config/XeomaArchive

# Clean up any mess from before
rm -f /config/config

#-----------------------------------------------------------------------------------------------------------------------

echo "$(ts) Setting the password"
/usr/bin/xeoma -setpassword "$PASSWORD"

# Not sure why this is necessary, but without it, I can't connect to the server
/usr/bin/xeoma -showpassword > /dev/null 2>&1

exit 0
