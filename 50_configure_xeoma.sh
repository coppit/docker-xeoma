#!/bin/bash

set -e

DEFAULT_CONFIG_FILE=/files/xeoma.conf.default
CONFIG_FILE=/config/xeoma.conf
MAC_FILE=/config/macs.txt

#-----------------------------------------------------------------------------------------------------------------------

function ts {
  echo [`date '+%b %d %X'`]
}

#-----------------------------------------------------------------------------------------------------------------------

# Handle the config file
if [ ! -f "$CONFIG_FILE" ]
then
  echo "$(ts) Creating config file $CONFIG_FILE. Please set the password and rerun this container."
  cp "$DEFAULT_CONFIG_FILE" "$CONFIG_FILE"
  chmod a+w "$CONFIG_FILE"
  exit 1
fi

# Deal with \r caused by editing in windows
tr -d '\r' < "$CONFIG_FILE" > /tmp/xeoma.conf

source /tmp/xeoma.conf

if [[ "$PASSWORD" == "YOUR_PASSWORD" ]]; then
  echo "$(ts) Config file still has the default password. Please change the password and rerun this container."
  exit 1
fi

#-----------------------------------------------------------------------------------------------------------------------

# Save some information about the interface that talks to the internet, in case we need it later.

# Have to parse /proc/net/route because there is no "ip" to do this: iface=$(ip route show default | awk '/default/ {print $5}')
iface=$(grep -E '^\S+\s+00000000' /proc/net/route | awk '{print $1}')
mac_address=$(cat /sys/class/net/$iface/address)
echo "$(ts) $iface $mac_address" >> "$MAC_FILE"

#-----------------------------------------------------------------------------------------------------------------------

# If we were to install Xeoma, it would run in /usr/local/Xeoma. But we're not, so it runs in /.config
mkdir /.config

# Delete before creating the symlinks, for two reasons: (1) the symlink might be left-over from a previous container (and
# therefore invalid in this container), and (2) if the container is restarted, there will already be a symlink, causing
# a new symlink like /usr/local/Xeoma/config/config
rm -f /.config/Xeoma
ln -s /config /.config/Xeoma

rm -f /config/XeomaArchive
ln -s /archive /config/XeomaArchive

# Clean up any mess from before
rm -f /config/config
