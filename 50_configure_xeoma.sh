#!/bin/bash

MAC_FILE=/config/macs.txt

#-----------------------------------------------------------------------------------------------------------------------

. /etc/envvars.merged

set -e

#-----------------------------------------------------------------------------------------------------------------------

function ts {
  echo [`date '+%b %d %X'`]
}

#-----------------------------------------------------------------------------------------------------------------------

if [ -n "$MAC_ADDRESS" ]; then
  echo "$(ts) Setting container mac address to $MAC_ADDRESS"
  ip link set eth0 address $MAC_ADDRESS
fi

# Save some information about the interface that talks to the internet, in case we need it later.

# Have to parse /proc/net/route because there is no "ip" to do this: iface=$(ip route show default | awk '/default/ {print $5}')
iface=$(grep -E '^\S+\s+00000000' /proc/net/route | awk '{print $1}')
mac_address=$(cat /sys/class/net/$iface/address)
echo "$(ts) $iface $mac_address" >> "$MAC_FILE"

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

echo "$(ts) Setting the password"
/usr/bin/xeoma -setpassword "$PASSWORD"

# Not sure why this is necessary, but without it, I can't connect to the server
/usr/bin/xeoma -showpassword > /dev/null 2>&1

exit 0
