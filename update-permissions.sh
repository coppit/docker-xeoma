#!/bin/bash

/bin/sleep 8
/bin/chmod -R og-rwx /config
/bin/chmod -R og-w /archive
/bin/chmod -R og-w /archive-cache

echo "[`date '+%b %d %X'`] Applied permissions restrictions"