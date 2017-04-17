#!/bin/bash

set -e

function ts {
  echo [`date '+%b %d %X'`]
}

#-----------------------------------------------------------------------------------------------------------------------

source /config/xeoma.conf

#-----------------------------------------------------------------------------------------------------------------------

VERSION=stable

if [[ "$USE_BETA" == y* ]]; then
  VERSION=beta
fi

echo "$(ts) Using the $VERSION version of Xeoma"

echo "$(ts) Setting the password"
/files/$VERSION/xeoma.app -setpassword "$PASSWORD"

echo "$(ts) Starting the server in 5 seconds..."
/files/$VERSION/xeoma.app -core -service -log -startdelay 5
