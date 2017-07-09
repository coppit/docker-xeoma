#!/bin/bash

set -e

LATEST_VERSIONS_URL=http://felenasoft.com/xeoma/en/download/
VERSION_DOWNLOAD_URL='http://felenasoft.com/xeoma/downloads/xeoma_previous_versions/?get=xeoma_linux64_$VERSION.tgz'
LATEST_STABLE_DOWNLOAD_URL='http://felenasoft.com/xeoma/downloads/xeoma_linux64.tgz'
LATEST_BETA_DOWNLOAD_URL='http://felenasoft.com/xeoma/downloads/xeoma_beta_linux64.tgz'

DOWNLOAD_LOCATION=/config/downloads

# These need to match update_xeoma.sh
INSTALL_LOCATION=/files/xeoma
LAST_INSTALLED_BREADCRUMB=$INSTALL_LOCATION/last_installed_version.txt

# This needs to match 50_configure_xeoma.sh
CONFIG_FILE=/config/xeoma.conf
FIXED_CONFIG_FILE=/tmp/xeoma.conf

#-----------------------------------------------------------------------------------------------------------------------

function ts {
  echo [`date '+%b %d %X'`]
}

#-----------------------------------------------------------------------------------------------------------------------

function latest_stable_version {
  VERSION_URL=$(curl -s $LATEST_VERSIONS_URL | grep 'images/theme/download/version.js' | sed 's|[^"]*"\([^"]*\)".*|http://felenasoft.com\1|')
  VERSION=$(curl -s $VERSION_URL | grep 'var version ' | sed 's/.*"\(.*\)".*/\1/')
  echo "$VERSION"
}

#-----------------------------------------------------------------------------------------------------------------------

function latest_beta_version {
  VERSION_URL=$(curl -s $LATEST_VERSIONS_URL | grep 'images/theme/download/version.js' | sed 's|[^"]*"\([^"]*\)".*|http://felenasoft.com\1|')
  VERSION=$(curl -s $VERSION_URL | grep 'var version_beta ' | sed 's/.*"\(.*\)".*/\1/')
  echo "$VERSION"
}

#-----------------------------------------------------------------------------------------------------------------------

function download_xeoma {
  version=$1
  download_url=$2

  if [[ "$version" == "http://"* ]] || [[ "$version" == "https://"* ]] || [[ "$version" == "ftp://"* ]]; then
    LOCAL_FILE="$DOWNLOAD_LOCATION/xeoma_from_url.tgz"
  else
    LOCAL_FILE="$DOWNLOAD_LOCATION/xeoma_${version}.tgz"
  fi

  if [[ -e "$LOCAL_FILE" ]]; then
    echo "$(ts) Downloaded file $LOCAL_FILE already exists. Skipping download"
    RC='ok'
    return
  fi

  mkdir -p "$DOWNLOAD_LOCATION"

  echo "$(ts) Deleting files in $DOWNLOAD_LOCATION to reclaim space..."

  for existing_file in "$DOWNLOAD_LOCATION/xeoma_"*".tgz"; do
    echo "Deleting $existing_file"
    rm -f "$existing_file"
  done

  TEMP_FILE="$DOWNLOAD_LOCATION/xeoma_temp.tgz" 

  echo "$(ts) Downloading from $download_url into $DOWNLOAD_LOCATION"

  # Ignore errors here. We'll handle our own error checking
  wget -q -O "$TEMP_FILE" "$download_url" || true

  if grep -q 'file not found' "$TEMP_FILE"; then
    echo "$(ts) ERROR: Could not download from $download_url"
    rm -rf "$TEMP_FILE"
    RC='failed'
    return
  fi

  mv "$TEMP_FILE" "$LOCAL_FILE"

  echo "$(ts) Downloaded $LOCAL_FILE..."

  RC='ok'
}

#-----------------------------------------------------------------------------------------------------------------------

function install_xeoma {
  local_file=$1

  if [[ -e "$LAST_INSTALLED_BREADCRUMB" ]];then
    last_installed_version=$(cat "$LAST_INSTALLED_BREADCRUMB" | tr -d '\n')
  else
    last_installed_version=""
  fi

  current_version=$(md5sum $local_file | sed 's/ .*//')

  if [[ "$last_installed_version" == "$current_version" ]]; then
    echo "$(ts) Skipping installation because the currently installed version is the correct one"
    return
  fi

  echo "$(ts) Installing Xeoma from $local_file"

  mkdir -p "$INSTALL_LOCATION"

  tar -xzf "$local_file" -C "$INSTALL_LOCATION" > /dev/null

  rm -f /usr/bin/xeoma
  ln -s "$INSTALL_LOCATION/xeoma.app" /usr/bin/xeoma

  echo "$current_version" > $LAST_INSTALLED_BREADCRUMB

  echo "$(ts) Installation complete"
}

#-----------------------------------------------------------------------------------------------------------------------

source "$FIXED_CONFIG_FILE"

if [[ "$VERSION" == "latest" ]] || [[ "$VERSION" == "" ]]; then
  VERSION=$(latest_stable_version)
  VERSION_STRING="$VERSION (the latest stable version)"
  download_url="$LATEST_STABLE_DOWNLOAD_URL"
elif [[ "$VERSION" == "latest_beta" ]]; then
  VERSION=$(latest_beta_version)
  VERSION_STRING="$VERSION (the latest beta version)"
  download_url="$LATEST_BETA_DOWNLOAD_URL"
elif [[ "$VERSION" == "http://"* ]] || [[ "$VERSION" == "https://"* ]] || [[ "$VERSION" == "ftp://"* ]]; then
  VERSION_STRING="from url ($VERSION)"
  download_url="$VERSION"
# A version like "17.5.5"
else
  VERSION_STRING="$VERSION (a user-specified version)"
  download_url=$(eval echo "$VERSION_DOWNLOAD_URL")
fi

echo "$(ts) Using Xeoma version $VERSION_STRING"

download_xeoma $VERSION $download_url

# Sometimes the latest beta isn't at the normal location. Try the versioned location.
if [[ "$RC" != 'ok' ]];then
  if [[ "$VERSION" == "latest" ]] || [[ "$VERSION" == "" ]] || [[ "$VERSION" == "latest_beta" ]]; then
    echo "$(ts) Download from default location failed. Trying from alternate location."
    download_url=$(eval echo "$VERSION_DOWNLOAD_URL")

    download_xeoma $VERSION $download_url
  fi
fi

install_xeoma $LOCAL_FILE

exit 0
