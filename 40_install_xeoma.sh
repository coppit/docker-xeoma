#!/bin/bash

set -e

LATEST_VERSIONS_URL=http://felenasoft.com/xeoma/en/download/
DOWNLOAD_URL='http://felenasoft.com/xeoma/downloads/xeoma_previous_versions/?get=xeoma_linux64_$VERSION.tgz'

DOWNLOAD_LOCATION=/config/downloads

# These need to match update_xeoma.sh
INSTALL_LOCATION=/files/xeoma
LAST_INSTALLED_BREADCRUMB=$INSTALL_LOCATION/last_installed_version.txt

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
    return
  fi

  mkdir -p "$DOWNLOAD_LOCATION"

  echo "$(ts) Deleting files in $DOWNLOAD_LOCATION to reclaim space..."

  for existing_file in "$DOWNLOAD_LOCATION/xeoma_"*".tgz"; do
    echo "Deleting $existing_file"
    rm -f "$existing_file"
  done

  echo "$(ts) Downloading from $download_url into $DOWNLOAD_LOCATION"

  wget -q -O "$DOWNLOAD_LOCATION/xeoma_temp.tgz" "$download_url"

  mv "$DOWNLOAD_LOCATION/xeoma_temp.tgz" "$LOCAL_FILE"

  echo "$(ts) Downloaded $LOCAL_FILE..."
}

#-----------------------------------------------------------------------------------------------------------------------

function install_xeoma {
  version=$1
  local_file=$2

  # Xeoma prints a version string like 2017-05-05, which I guess translates to 17.5.5. But the user can also specify a
  # URL to a version, and it's possible that the Xeoma devs might produce a test version that doesn't bump the version
  # number. So let's just use a breadcrumb to track the last version that we installed.
  if [[ -e "$LAST_INSTALLED_BREADCRUMB" ]];then
    last_installed_version=$(cat "$LAST_INSTALLED_BREADCRUMB" | tr -d '\n')
  else
    last_installed_version=""
  fi

  if [[ "$last_installed_version" == "$version" ]]; then
    echo "$(ts) Skipping installation because the currently installed version is the correct one"
    return
  fi

  echo "$(ts) Installing Xeoma from $local_file"

  mkdir -p "$INSTALL_LOCATION"

  tar -xzf "$local_file" -C "$INSTALL_LOCATION"

  rm -f /usr/bin/xeoma
  ln -s "$INSTALL_LOCATION/xeoma.app" /usr/bin/xeoma

  echo "$version" > $LAST_INSTALLED_BREADCRUMB

  echo "$(ts) Installation complete"
}

#-----------------------------------------------------------------------------------------------------------------------

if [[ "$VERSION" == "latest" ]] || [[ "$VERSION" == "" ]]; then
  VERSION=$(latest_stable_version)
  VERSION_STRING="$VERSION (the latest stable version)"
  DOWNLOAD_URL=$(eval echo "$DOWNLOAD_URL")
elif [[ "$VERSION" == "latest_beta" ]]; then
  VERSION=$(latest_beta_version)
  VERSION_STRING="$VERSION (the latest beta version)"
  DOWNLOAD_URL=$(eval echo "$DOWNLOAD_URL")
elif [[ "$VERSION" == "http://"* ]] || [[ "$VERSION" == "https://"* ]] || [[ "$VERSION" == "ftp://"* ]]; then
  VERSION_STRING="from url ($VERSION)"
  DOWNLOAD_URL="$VERSION"
# A version like "17.5.5"
else
  VERSION_STRING="$VERSION (a user-specified version)"
  DOWNLOAD_URL=$(eval echo "$DOWNLOAD_URL")
fi

echo "$(ts) Using Xeoma version $VERSION_STRING"

download_xeoma $VERSION $DOWNLOAD_URL

install_xeoma $VERSION $LOCAL_FILE
