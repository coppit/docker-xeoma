#!/bin/bash

set -e

DEFAULT_CONFIG_FILE=/files/xeoma.conf.default
CONFIG_FILE=/config/xeoma.conf
FIXED_CONFIG_FILE=/tmp/xeoma.conf

#-----------------------------------------------------------------------------------------------------------------------

function ts {
  echo [`date '+%b %d %X'`]
}

#-----------------------------------------------------------------------------------------------------------------------

echo "$(ts) Processing config file"

# Create default config file if necessary
if [ ! -f "$CONFIG_FILE" ]
then
  echo "$(ts) Creating config file $CONFIG_FILE. Please set the password and rerun this container."
  cp "$DEFAULT_CONFIG_FILE" "$CONFIG_FILE"
  chmod a+w "$CONFIG_FILE"
  exit 1
fi

# Deal with \r caused by editing in windows
tr -d '\r' < "$CONFIG_FILE" > "$FIXED_CONFIG_FILE"

source "$FIXED_CONFIG_FILE"

if [[ "$PASSWORD" == "YOUR_PASSWORD" ]]; then
  echo "$(ts) Config file still has the default password. Please change the password and rerun this container."
  exit 1
fi

# Check for old config file
if [[ "$USE_BETA" != "" ]]; then
  echo "$(ts) Please upgrade your config file! Replace USE_BETA='xxx' with VERSION='latest'. See docs for details"
  exit 1
fi

exit 0
