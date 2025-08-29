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

DOWNLOAD_LOCATION = '/config/downloads'

VERSION_URL = 'http://felenasoft.com/xeoma/downloads/version3.xml'
VERSION_DOWNLOAD_URL = 'https://felenasoft.com/xeoma/downloads/{}/linux/xeoma_linux64.tgz'

# These need to match update_xeoma.sh
INSTALL_LOCATION = '/files/xeoma'
XEOMA_BINARY = '/usr/bin/xeoma'
LAST_INSTALLED_BREADCRUMB = f'{INSTALL_LOCATION}/last_installed_version.txt'

#-----------------------------------------------------------------------------------------------------------------------

def read_version_from_config():
    pipe = subprocess.Popen(['/bin/bash', '-c', '. /etc/envvars.merged; echo -n "$VERSION"'], stdout=subprocess.PIPE)
    return pipe.stdout.read().decode('ascii')

#-----------------------------------------------------------------------------------------------------------------------

def latest_version(beta=False):
    logging.info(f'Fetching version information from Felenasoft at {VERSION_URL}')

    e = xml.etree.ElementTree.ElementTree(file=urllib.request.urlopen(VERSION_URL)).getroot()

    beta_string = ''
    if beta:
        if e.find('beta/version'):
            beta_string = 'beta/'
        else:
            logging.info(f'Could not find beta version information from Felenasoft at {VERSION_URL}. Using non-beta version')

    version_number = e.find(f'{beta_string}version').text

    download_url = e.find(f'{beta_string}platform[@name="linux64"]').find('url').text

    alternate_download_url = VERSION_DOWNLOAD_URL.format(version_number.replace('.', '-'))

    # There's a size field in the XML, but it doesn't appear to be correct.

    return version_number, download_url, alternate_download_url

#-----------------------------------------------------------------------------------------------------------------------

def resolve_download_info():
    logging.info('Determining version of Xeoma to use')

    version = read_version_from_config()

    logging.info(f'Config version is "{version}"')

    version = 'latest' if version == '' else version

    if version == 'latest':
        version_number, download_url, alternate_download_url = latest_version()
        version_string = f'{version_number} (the latest stable version)'
    elif version == 'latest_beta':
        version_number, download_url, alternate_download_url = latest_version(beta=True)
        version_string = f'{version_number} (the latest beta version)'
    elif version.split('://')[0] in ['http', 'https', 'ftp']:
        download_url = version
        version_number, alternate_download_url = None, None
        version_string = f'from url ({download_url})'
    # A version like "17.5.5"
    else:
        version_number = version

        # update from version in format 21.18.11, to download url in format 2021-18-11
        version_string = "20" + version_number.replace('.', '-')

        download_url = VERSION_DOWNLOAD_URL.format(version_string)
        alternate_download_url = None
        version_string = f'{version_number} (a user-specified version)'

    logging.info(f'Using Xeoma version {version_string}')

    return version_number, download_url, alternate_download_url

#-----------------------------------------------------------------------------------------------------------------------

def download_xeoma(version_number, download_url, alternate_download_url):
    if version_number:
        local_file = f'{DOWNLOAD_LOCATION}/xeoma_{version_number}.tgz'
    else:
        local_file = f'{DOWNLOAD_LOCATION}/xeoma_from_url.tgz'

    if os.path.exists(local_file):
        logging.info(f'Downloaded file {local_file} already exists. Skipping download')
        return local_file

    pathlib.Path(DOWNLOAD_LOCATION).mkdir(parents=True, exist_ok=True)

    logging.info(f'Deleting files in {DOWNLOAD_LOCATION} to reclaim space...')

    for existing_file in glob.glob(f'{DOWNLOAD_LOCATION}/xeoma_*.tgz'):
        logging.info(f'Deleting {existing_file}')
        os.remove(existing_file)

    TEMP_FILE = f'{DOWNLOAD_LOCATION}/xeoma_temp.tgz'

    logging.info(f'Downloading from {download_url} into {DOWNLOAD_LOCATION}')

    def do_download(url):
        def string_in_file(string, filename):
            with open(filename, 'rb') as f:
                contents = f.read()
                return string in contents

        logging.info(f'Downloading from {url}')

        urllib.request.urlretrieve(url, TEMP_FILE)

        if not string_in_file(b'file not found', TEMP_FILE):
            os.rename(TEMP_FILE, local_file)
            logging.info(f'Downloaded to {local_file}')
            return True

        if os.path.exists(TEMP_FILE): os.remove(TEMP_FILE)

        return False

    if do_download(download_url): return local_file

    # Sometimes the latest beta isn't at the normal location. Try the versioned location.
    if alternate_download_url:
        logging.info('Download from default location failed. Trying alternate location.')

        if do_download(alternate_download_url): return local_file

    logging.error(f'Could not download Xeoma version "{version_number}" from {download_url} or {alternate_download_url}')
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

    logging.info(f'Installing Xeoma from {local_file}')

    pathlib.Path(INSTALL_LOCATION).mkdir(parents=True, exist_ok=True)

    subprocess.run(['tar', '-xzf', local_file, '-C', INSTALL_LOCATION], stdout=subprocess.DEVNULL, check=True)

    if os.path.exists(XEOMA_BINARY): os.remove(XEOMA_BINARY)

    os.symlink(f'{INSTALL_LOCATION}/xeoma.app', XEOMA_BINARY)

    with open(LAST_INSTALLED_BREADCRUMB, 'w') as f:
        f.write(current_version)

    logging.info('Installation complete')

#-----------------------------------------------------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

version_number, download_url, alternate_download_url = resolve_download_info()

local_file = download_xeoma(version_number, download_url, alternate_download_url)

install_xeoma(local_file)

sys.exit(0)
