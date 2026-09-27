#!/usr/bin/with-contenv bash

set -e

function ts {
  echo `date '+[%Y-%m-%d %H:%M:%S]'`
}

#-----------------------------------------------------------------------------------------------------------------------

echo "$(ts) Starting the server in 5 seconds. See the log directory in your config directory for server logs."

umask "${UMASK:-022}"
export HOME=/config XDG_CONFIG_HOME=/.config
unset PASSWORD
cd /config

if [[ -e /archive-cache/4vagl0js6k ]]
then
    echo "$(ts) Not using archive cache"
    exec s6-setuidgid abc /usr/bin/xeoma -core -service -log -startdelay 5
else
    echo "$(ts) Using archive cache"
    exec s6-setuidgid abc /usr/bin/xeoma -core -service -log -startdelay 5 -archivecache /archive-cache
fi
