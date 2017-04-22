#!/bin/bash

set -e

function ts {
  echo [`date '+%b %d %X'`]
}

#-----------------------------------------------------------------------------------------------------------------------

echo "$(ts) Starting the server in 5 seconds..."
/usr/bin/xeoma -core -service -log -startdelay 5
