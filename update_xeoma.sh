#!/bin/bash

# These need to match 40_install_xeoma.sh
INSTALL_LOCATION=/files/xeoma
LAST_INSTALLED_BREADCRUMB=$INSTALL_LOCATION/last_installed_version.txt

#-----------------------------------------------------------------------------------------------------------------------

function ts {
  echo [`date '+%b %d %X'`]
}

#-----------------------------------------------------------------------------------------------------------------------

function get_installed_version {
  if [[ -e "$LAST_INSTALLED_BREADCRUMB" ]];then
    cat "$LAST_INSTALLED_BREADCRUMB" | tr -d '\n'
  else
    echo -n ""
  fi
}

#-----------------------------------------------------------------------------------------------------------------------

echo "$(ts) Attempting to auto-update Xeoma"

echo "vvvvvvvvvvvvvvvvvvv"
last_installed_version=$(get_installed_version)
bash /etc/my_init.d/40_install_xeoma.sh 
new_installed_version=$(get_installed_version)
echo "^^^^^^^^^^^^^^^^^^^"

if [[ "$last_installed_version" != "$new_installed_version" ]];then
  echo "$(ts) Xeoma has been updated. Restarting the service."
  pkill xeoma

  # The phusion framework will restart it for us
else
  echo "$(ts) Xeoma has not been updated."
fi

