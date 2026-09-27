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
    echo "ERROR: No password is set. Startup stopped." >&2
    echo "Put your password in /config/xeoma_password, or set PASSWORD in the environment or xeoma.conf." >&2
    exit 1
  fi
}

#-----------------------------------------------------------------------------------------------------------------------

print_config() {
  echo "Configuration:"
  echo "  PASSWORD=<hidden>"
  echo "  VERSION=$VERSION"
  echo "  MAC_ADDRESS=$MAC_ADDRESS"
  echo "  Current time and timezone=$(date)"
}

########################################################################################################################

ENV_VARS=/run/xeoma/environment.sh
MERGED_ENV_VARS=/etc/envvars.merged

#-----------------------------------------------------------------------------------------------------------------------

all_required_settings_exist() {
  ALL_REQUIRED_SETTINGS_EXIST=true
  for required_setting in $REQUIRED_SETTINGS
  do
    if [ -z "${!required_setting}" ]
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

  if [ $? -ne 0 ]; then
    echo "Could not copy template config file. Is the config share mapped as read-only?"
    exit 4
  fi

  # Search for config file. If it doesn't exist, copy the default one
  if [ ! -f "$CONFIG_FILE" ]; then
    echo "Creating xeoma.conf and a password file. Put your password in xeoma_password before restarting."
    cp "$TEMPLATE_CONFIG_FILE" "$CONFIG_FILE"
    chmod 600 "$CONFIG_FILE"
    if [[ ! -e "$CONFIG_PATH/xeoma_password" && ! -L "$CONFIG_PATH/xeoma_password" ]]; then
      (umask 077; : > "$CONFIG_PATH/xeoma_password") || exit 4
    fi
    exit 1
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

# Password files contain literal data. Command substitution strips trailing LF characters.
read_password_file() {
  local password_path="$CONFIG_PATH/xeoma_password"
  if [[ -e "$password_path" || -L "$password_path" ]]; then
    if [[ -f "$password_path" && -r "$password_path" ]] &&
       file_password=$(cat -- "$password_path" 2>/dev/null) && [[ -n "$file_password" ]]; then
      export PASSWORD="$file_password"
    else
      echo "Warning: /config/xeoma_password is unreadable or empty; falling back to PASSWORD or xeoma.conf." >&2
    fi
    unset file_password
  fi
}

########################################################################################################################

. "$ENV_VARS"

if [[ -n "${PASSWORD:-}" ]]; then
  echo "Warning: PASSWORD is set in the environment and may be visible in container configuration." >&2
  echo "Use /config/xeoma_password instead for more secure password handling." >&2
fi

# Always merge an existing config, even when the environment supplies a password.
if [[ -f "$CONFIG_FILE" ]]; then
  create_and_validate_config_file
  merge_config_vars_and_env_vars "$SAFE_CONFIG_FILE"
  rm -f "$SAFE_CONFIG_FILE"
  read_password_file
else
  read_password_file
  if [ $(all_required_settings_exist) != true ]; then
    create_and_validate_config_file
  fi
fi

validate_values

set_default_values

print_config

# Save only settings needed by the installer/configurer, readable by root only.
(umask 077
  rm -f "$MERGED_ENV_VARS"
  for name in PASSWORD VERSION MAC_ADDRESS; do
    printf 'export %s=%q\n' "$name" "${!name}"
  done > "$MERGED_ENV_VARS"
)
