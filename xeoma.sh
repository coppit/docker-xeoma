#!/bin/bash

set -e

function ts {
  echo [`date '+%b %d %X'`]
}

#-----------------------------------------------------------------------------------------------------------------------

echo "$(ts) Starting the server in 5 seconds. See the log directory in your config directory for server logs."

if [[ -e /archive-cache/4vagl0js6k ]]
then
    echo "$(ts) Not using archive cache"
    /usr/bin/xeoma -core -service -log -startdelay 5
else
    echo "$(ts) Using archive cache"
    /usr/bin/xeoma -core -service -log -startdelay 5 -archivecache /archive-cache
fi
