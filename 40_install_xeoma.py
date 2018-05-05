#!/usr/bin/python3

import glob
import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree
import pathlib

#-----------------------------------------------------------------------------------------------------------------------

CONFIG_FILE = '/config/xeoma.conf'
DOWNLOAD_LOCATION = '/config/downloads'

VERSION_URL = 'http://felenasoft.com/xeoma/downloads/version2.xml'
VERSION_DOWNLOAD_URL = 'https://felenasoft.com/xeoma/downloads/xeoma_previous_versions/?get=xeoma_linux64_{}.tgz'

# These need to match update_xeoma.sh
INSTALL_LOCATION = '/files/xeoma'
XEOMA_BINARY = '/usr/bin/xeoma'
LAST_INSTALLED_BREADCRUMB = '{}/last_installed_version.txt'.format(INSTALL_LOCATION)

#-----------------------------------------------------------------------------------------------------------------------

def remove_linefeeds(input_filename):
    temp = tempfile.NamedTemporaryFile(delete=False)

    with open(input_filename, "r") as input_file:
        with open(temp.name, "w") as output_file:
            for line in input_file:
                output_file.write(line)

    return temp.name

#-----------------------------------------------------------------------------------------------------------------------

def read_version_from_config(config_file):
    config_file = remove_linefeeds(config_file)

    # Shenanigans to read docker env vars, and the bash format config file. I didn't want to ask them to change their
    # config files.
    dump_command = '{} -c "import os, json;print(json.dumps(dict(os.environ)))"'.format(sys.executable)

    pipe = subprocess.Popen(['/bin/bash', '-c', dump_command], stdout=subprocess.PIPE)
    string = pipe.stdout.read().decode('ascii')
    base_env = json.loads(string)

    source_command = 'source {}'.format(config_file)
    pipe = subprocess.Popen(['/bin/bash', '-c', 'set -a && {} && {}'.format(source_command,dump_command)],
        stdout=subprocess.PIPE)
    string = pipe.stdout.read().decode('ascii')
    config_env = json.loads(string)

    env = config_env.copy()
    env.update(base_env)

    return env["VERSION"]

#-----------------------------------------------------------------------------------------------------------------------

def latest_version(beta=False):
    beta_string = 'beta/' if beta else ''

    e = xml.etree.ElementTree.ElementTree(file=urllib.request.urlopen(VERSION_URL)).getroot()

    version_number = e.find('{}version'.format(beta_string)).text

    download_url = e.find('{}platform[@name="linux64"]'.format(beta_string)).find('url').text

    alternate_download_url = VERSION_DOWNLOAD_URL.format(version_number)

    # There's a size field in the XML, but it doesn't appear to be correct.

    return version_number, download_url, alternate_download_url

#-----------------------------------------------------------------------------------------------------------------------

def resolve_download_info():
    version = read_version_from_config(CONFIG_FILE)

    version = 'latest' if version == '' else version

    if version == 'latest':
        version_number, download_url, alternate_download_url = latest_version()
        version_string = '{} (the latest stable version)'.format(version_number)
    elif version == 'latest_beta':
        version_number, download_url, alternate_download_url = latest_version(beta=True)
        version_string = '{} (the latest beta version)'.format(version_number)
    elif version.split('://')[0] in ['http', 'https', 'ftp']:
        download_url = version
        version_number, alternate_download_url = None, None
        version_string = 'from url ({})'.format(download_url)
    # A version like "17.5.5"
    else:
        version_number, download_url = version, VERSION_DOWNLOAD_URL.format(version_number)
        alternate_download_url = None
        version_string = '{} (a user-specified version)'.format(version_number)

    logging.info('Using Xeoma version {}'.format(version_string))

    return version_number, download_url, alternate_download_url

#-----------------------------------------------------------------------------------------------------------------------

def download_xeoma(version_number, download_url, alternate_download_url):
    if version_number:
        local_file = '{}/xeoma_{}.tgz'.format(DOWNLOAD_LOCATION, version_number)
    else:
        local_file = '{}/xeoma_from_url.tgz'.format(DOWNLOAD_LOCATION)

    if os.path.exists(local_file):
        logging.info('Downloaded file {} already exists. Skipping download'.format(local_file))
        return local_file

    pathlib.Path(DOWNLOAD_LOCATION).mkdir(parents=True, exist_ok=True) 

    logging.info('Deleting files in {} to reclaim space...'.format(DOWNLOAD_LOCATION))

    for existing_file in glob.glob('{}/xeoma_*.tgz'.format(DOWNLOAD_LOCATION)):
        logging.info('Deleting {}'.format(existing_file))
        os.remove(existing_file)

    TEMP_FILE = '{}/xeoma_temp.tgz'.format(DOWNLOAD_LOCATION)

    logging.info('Downloading from {} into {}'.format(download_url, DOWNLOAD_LOCATION))

    def do_download(url):
        def string_in_file(string, filename):
            with open(filename, 'rb') as f:
                contents = f.read()
                return string in contents

        urllib.request.urlretrieve(url, TEMP_FILE)

        if not string_in_file(b'file not found', TEMP_FILE):
            os.rename(TEMP_FILE, local_file)
            logging.info('Downloaded to {}...'.format(local_file))
            return True

        if os.path.exists(TEMP_FILE): os.remove(TEMP_FILE)
        
        return False

    if do_download(download_url): return local_file

    # Sometimes the latest beta isn't at the normal location. Try the versioned location.
    if alternate_download_url:
        logging.info('Download from default location failed. Trying alternate location.')

        if do_download(alternate_download_url): return local_file

    logging.error('Could not download Xeoma version "{}" from {} or {}'.format(version_number, download_url,
        alternate_download_url))
    sys.exit(1)

#-----------------------------------------------------------------------------------------------------------------------

def install_xeoma(local_file):
    if os.path.exists(LAST_INSTALLED_BREADCRUMB):
        with open(LAST_INSTALLED_BREADCRUMB, 'r') as f:
            last_installed_version = f.read()
    else:
        last_installed_version = None
        
    m = hashlib.md5();
    m.update(open(local_file, 'rb').read());

    current_version = m.hexdigest()

    if last_installed_version == current_version:
      logging.info('Skipping installation because the currently installed version is the correct one')
      return

    logging.info('Installing Xeoma from $local_file')

    pathlib.Path(INSTALL_LOCATION).mkdir(parents=True, exist_ok=True) 

    subprocess.run(['tar', '-xzf', local_file, '-C', INSTALL_LOCATION], stdout=subprocess.DEVNULL, check=True)

    if os.path.exists(XEOMA_BINARY): os.remove(XEOMA_BINARY)

    os.symlink('{}/xeoma.app'.format(INSTALL_LOCATION), XEOMA_BINARY)

    with open(LAST_INSTALLED_BREADCRUMB, 'w') as f:
        f.write(current_version)

    logging.info('Installation complete')

#-----------------------------------------------------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

version_number, download_url, alternate_download_url = resolve_download_info()

local_file = download_xeoma(version_number, download_url, alternate_download_url)

install_xeoma(local_file)

sys.exit(0)
