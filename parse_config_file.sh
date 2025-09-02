#!/bin/bash

# Container-specific stuff first

REQUIRED_SETTINGS="PASSWORD"
DEFAULT_SETTINGS="VERSION=latest"

TEMPLATE_CONFIG_FILE=/files/xeoma.conf.default
CONFIG_PATH=/config
CONFIG_FILE=$CONFIG_PATH/xeoma.conf

#-----------------------------------------------------------------------------------------------------------------------

validate_values() {
  if [ $(all_required_settings_exist) != true ]
  then
    echo "Missing required settings, which must be provided in the config file or by environment variables:"
    echo "$REQUIRED_SETTINGS"
    exit 0
  fi
}

#-----------------------------------------------------------------------------------------------------------------------

print_config() {
  echo "Configuration:"
  echo "  PASSWORD=<hidden>"
  echo "  VERSION=$VERSION"
  echo "  MAC_ADDRESS=$MAC_ADDRESS"
}

########################################################################################################################

ENV_VARS=/etc/container_environment.sh
MERGED_ENV_VARS=/etc/envvars.merged

#-----------------------------------------------------------------------------------------------------------------------

all_required_settings_exist() {
  ALL_REQUIRED_SETTINGS_EXIST=true
  for required_setting in $REQUIRED_SETTINGS
  do
    if [ -z "$(eval "echo \$$required_setting")" ]
    then
      ALL_REQUIRED_SETTINGS_EXIST=false
      break
    fi
  done

  echo $ALL_REQUIRED_SETTINGS_EXIST
}

#-----------------------------------------------------------------------------------------------------------------------

# Side effect: Sets SAFE_CONFIG_FILE
create_and_validate_config_file() {
  echo "Copying the latest template config file to $CONFIG_PATH for reference"
  cp -f "$TEMPLATE_CONFIG_FILE" "$CONFIG_PATH"

  # Search for config file. If it doesn't exist, copy the default one
  if [ ! -f "$CONFIG_FILE" ]; then
    echo "Creating config file. Please do not forget to edit it to specify your settings!"
    cp "$TEMPLATE_CONFIG_FILE" "$CONFIG_FILE"
    chmod a+w "$CONFIG_FILE"
    exit 1
  fi

  # Check to see if they didn't edit the config file
  if diff "$TEMPLATE_CONFIG_FILE" "$CONFIG_FILE" >/dev/null
  then
    echo "Please edit the config file to specify your settings"
    exit 3
  fi

  # Translate line endings, since they may have edited the file in Windows
  SAFE_CONFIG_FILE=$(mktemp)
  tr -d '\r' < "$CONFIG_FILE" > "$SAFE_CONFIG_FILE"
}

#-----------------------------------------------------------------------------------------------------------------------

merge_config_vars_and_env_vars() {
  SAFE_CONFIG_FILE=$1

  # Temporarily auto-export the variables we get from the files
  set -a

  . "$SAFE_CONFIG_FILE"

  # Env vars take precedence
  . "$ENV_VARS"

  set +a
}

#-----------------------------------------------------------------------------------------------------------------------

set_default_values() {
  # Handle defaults now
  for KEY_VALUE in $DEFAULT_SETTINGS
  do
    KEY=$(echo "$KEY_VALUE" | cut -d= -f1)
    VALUE=$(echo "$KEY_VALUE" | cut -d= -f2)

    eval "export $KEY=\${$KEY:=$VALUE}"
  done
}

########################################################################################################################

. "$ENV_VARS"

if [ $(all_required_settings_exist) = true ]
then
  echo "All required settings passed as environment variables. Skipping config file creation."
  exit 0
fi

create_and_validate_config_file

merge_config_vars_and_env_vars $SAFE_CONFIG_FILE

validate_values

set_default_values

print_config

# Now dump the envvars, in the style that boot.sh does.
export > $MERGED_ENV_VARS
