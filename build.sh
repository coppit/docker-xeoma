#!/usr/bin/env bash

# Example: build.sh
# Example: build.sh v1

echo "Building locally..."
docker build -t coppit/xeoma .
docker tag coppit/xeoma coppit/xeoma:dev

VERSION_URL=$(curl -s http://felenasoft.com/xeoma/en/download/ | grep 'images/theme/download/version.js' | sed 's|[^"]*"\([^"]*\)".*|http://felenasoft.com\1|')
STABLE_VERSION=$(curl -s $VERSION_URL | grep 'var version ' | sed 's/.*"\(.*\)".*/\1/')
BETA_VERSION=$(curl -s $VERSION_URL | grep 'var version_beta ' | sed 's/.*"\(.*\)".*/\1/')

echo "Local version built, tagged as coppit/xeoma:dev. Stable version is $STABLE_VERSION. Beta version is $BETA_VERSION"

if [[ "$#" == 1 ]]; then
    RELEASE=$1

    TAG="stable${STABLE_VERSION}_beta${BETA_VERSION}_$RELEASE"

    echo "Tagging and pushing..."
    docker tag coppit/xeoma:latest coppit/xeoma:$TAG
    docker push coppit/xeoma:latest
    docker push coppit/xeoma:$TAG
fi
