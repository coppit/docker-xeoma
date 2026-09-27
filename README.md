# docker-xeoma

This is a Docker container for running [Xeoma](http://felenasoft.com/xeoma/en/), surveillance software developed by
Felena Soft. It supports a wide range of security cameras, has low CPU overhead, and a very easy-to-use interface. The
container is just for the server, and does not have a user interface. Run the client on any computer or mobile device,
connecting to the server on port 8090. You can also [configure Xeoma's
cameras](https://felenasoft.com/xeoma/en/articles/transmitter/) to be shown in the web UI, which is accessible on port
10090.

The container uses LinuxServer.io's Ubuntu base with s6 supervision. This is an independently maintained Xeoma image;
application and container support remain with FelenaSoft and this repository, respectively.

This docker image is available [on Docker Hub](https://hub.docker.com/r/coppit/xeoma/).

You can try out Xeoma using the trial version of the software, then purchase it when you are ready. Note the limitations
of the trial version however -- settings aren't saved, and archived videos get deleted after 1 hour. Avoid the free
version, as it cannot connect to your container. Make sure you read [the EULA](http://felenasoft.com/xeoma/en/eula/) as
you are effectively agreeing to it by running this docker.

## Running

You can use environment variables or a configuration file to configure this container. For passwords, use
[a password file](#password-from-a-secret-file), which is more secure than putting the password in an environment
variable.

`docker run -d --name=Xeoma -p 8090:8090 -p 10090:10090 -v /local/path/to/config:/config -v /local/path/to/archive:/archive -e PUID=1000 -e PGID=1000 -e UMASK=022 -e VERSION='latest' -e PASSWORD='<password>' coppit/xeoma`

To generate configuration and password files instead, run:

`docker run -d --name=Xeoma -p 8090:8090 -p 10090:10090 -v /local/path/to/config:/config -v /local/path/to/archive:/archive coppit/xeoma`

On first run, the container creates `xeoma.conf` and an empty `xeoma_password` in the config directory, then exits. Put
only your password in `xeoma_password` with no quotes, escaping, comments, assignments, etc. Trailing newline characters
are removed. All other characters are read literally. The password file is created with owner-only permissions and an
existing file is never overwritten. If Xeoma's password-setting command fails, startup stops and the container logs a
clear error with its exit status. Correct the password and restart. Raw Xeoma diagnostics are withheld because they can
reveal password fragments.

The generated `xeoma.conf` documents the default password path without defining a password variable. Change `VERSION` or
`MAC_ADDRESS` there if needed; otherwise leave it unchanged. Restart the container after filling in the password file.
Existing configurations containing `PASSWORD` continue to work.

The archive folder holds the saved video recordings.

To access your xeoma server, simply download the same version from [the Xeoma
website](http://felenasoft.com/xeoma/en/download/) and set it up to connect to a remote server using the IP address of
the docker host and the password you selected.

NOTE: If you're opening port 10090 for the web server, you need to actually add the web server to at least one camera.
Otherwise you'll get a "404 Not Found" message when you access the webpage with a browser.

See the notes below for special networking considerations depending on your cameras, and for licensing issues.

View logs using:

`docker logs xeoma`

## File Ownership and Permissions

Xeoma runs as LinuxServer's `abc` user, mapped to the numeric `PUID` and `PGID` you provide. Set these to the host user
and group that should own configuration and recordings. Use `id -u` and `id -g` on the Docker host to find those values.
Both default to `911`. Set these options as container environment variables, not in `xeoma.conf`; leave Docker's
`--user` option unset so initialization can prepare storage and then drop privileges for Xeoma.

`UMASK` controls permissions on newly created files. It defaults to `022`; typical settings are:

| UMASK | Files created with mode 666 | Directories created with mode 777 |
| --- | --- | --- |
| `022` | Owner writes; everyone reads | Owner writes; everyone reads/traverses |
| `002` | Owner/group write; everyone reads | Owner/group write; everyone reads/traverses |
| `007` | Owner/group read and write | Owner/group access only |
| `077` | Owner access only | Owner access only |

The application may request more restrictive permissions or explicitly change them. UMASK does not add permissions or
change existing files. The old hourly recursive permission script has been removed so it does not override the
chosen mask. For example, use `PUID=1000`, `PGID=100`, and `UMASK=007` to share newly created recordings with group 100.

When upgrading from the older Phusion-based image, choose PUID/PGID before starting. The first successful ownership
migration recursively changes ownership of `/config`, `/archive`, and `/archive-cache`, including existing files. This
can be a slow operation, so the UID/GID and a checksum record the startup history in `/config/.xeoma-ownership`.
Subsequent starts will skip this recursive step unless PUID/PGID changes or the history has changed since the previous
start. (Older images append to `macs.txt` without updating the marker, so downgrading, running an older image, and
re-upgrading triggers migration again.) Existing permission modes are preserved.

If you replace a storage mount, restore files with different owners, or want to repeat the migration, delete
`/config/.xeoma-ownership` and restart. The marker does not detect externally added files. Keep the same volume
mappings and networking/MAC settings to preserve configuration and licensing identity.

## Password from a Secret File

**Recommended:** mount your password file read-only at `/config/xeoma_password`. The container reads this fixed path
automatically. The file should only contain the password. Existing passwords from the environment or config remain
supported; a valid password file takes precedence over them.

You can use either or both of these mounts:

```sh
--mount type=bind,src=/local/path/to/config,dst=/config
--mount type=bind,src=/local/path/to/secrets/xeoma_password,dst=/config/xeoma_password,readonly
```

With only the directory mount, the password comes from `/local/path/to/config/xeoma_password`. With both mounts, the
separate password file appears at `/config/xeoma_password`, hiding any file already there for the container's lifetime.
The password file mount also works without a host directory mounted at `/config`; this image then uses an anonymous
config volume. Map `/config` explicitly if you want predictable configuration persistence when recreating the container.

Settings from `xeoma.conf` are loaded first, then environment variables override matching names. Missing settings use
their defaults. After merging, a valid `/config/xeoma_password` overrides `PASSWORD`. An unreadable or empty file logs a
warning and falls back to the merged `PASSWORD`; an absent file preserves legacy behavior.

A password in a properly protected `xeoma.conf` remains supported without an environment-password warning and can be
about as secure as a separately protected password file. Both store plaintext credentials; file-based password loading
does not itself encrypt them. Restrict access to either file and its backups, and omit credentials when sharing settings.
A separate secret file makes it easier to mount the credential read-only and keep it outside `/config` and routine
configuration backups. Its benefit is separation and access control, rather than encryption.

For Docker Compose:

```yaml
services:
  xeoma:
    image: coppit/xeoma
    ports:
      - "8090:8090"
      - "10090:10090"
    environment:
      PUID: "1000"
      PGID: "1000"
      UMASK: "007"
      VERSION: "latest"
    volumes:
      - ./config:/config
      - ./archive:/archive
    secrets:
      - source: xeoma_password
        target: /config/xeoma_password

secrets:
  xeoma_password:
    file: ./secrets/xeoma_password
```

Create `./secrets/xeoma_password` containing your password and restrict access to that host file. Compose mounts it at
`/config/xeoma_password`. With `docker run`, use the read-only bind mount shown above. The file is read on each container start; restart after changing it.
The container does not print the password, though Xeoma still receives it through its password-setting command.

## Using an Archive Cache

You can optionally use a folder for temporary storage of recording files until they are fully recorded, then moved to
the archive. Using this parameter significantly reduces disk fragmentation. This can be useful for a large number of
cameras, or when using an SSD for the main archive.

To use this feature, simply add an additional option when running the container: `-v
/local/path/to/archive-cache:/archive-cache`.

## Choosing a Version

The `VERSION` environment variable can be used to select the version of Xeoma to use. Values can be "latest",
"latest_beta", a version string like "17.5.5", or a URL that starts with "http://", "https://" or "ftp://". The default
value is "latest". The change history for Xeoma is [here](http://felenasoft.com/xeoma/en/changes/).

During startup, the desired version of Xeoma is downloaded as needed into the "downloads" subdirectory of the config
directory. Any files in that directory matching the pattern `xeoma_*.tgz` will be deleted. It is then installed
automatically.

**Warning**: By default, Xeoma will automatically detect new versions on startup and update itself. You should disable
this feature in the user interface, and instead just rely on the container's version handling. If you're using a
specific version of the software, this will prevent Xeoma from auto-updating it if the container restarts. If you're
using the "latest" version, the container will already auto-update (even without a restart).

At startup, the container registers an hourly update job in root's crontab only when the resolved `VERSION` is `latest`
or `latest_beta`. LinuxServer's built-in cron service runs the job at 17 minutes past each hour; output goes to the
container logs. Pinned versions and custom download URLs have no hourly update job. Restarting after changing the
configured version removes any old registration and applies the new setting. The updater also checks the version when
invoked manually. If the saved version setting is missing or unreadable, the updater logs an error and skips the update
rather than defaulting to `latest`.

## Notes

### Licensing and Docker Containers

How licensing works is a bit unclear. As of version 16.12.26, the Lite version prohibits running inside virtual
machines. Whether (and how!) this applies to docker containers is unclear. Your container may also need continuous
internet access to validate the license.

When you register your software, the license will be stored in your config directory. So it will be carried across
container updates, along with any configuration changes you made in the app. But if you ever delete the config
directory, you might have to contact Felena soft for another registration key.

Be careful about choosing your networking settings before installing your license. If you have registered the software
with host or bridged networking, then if you change to the other type of networking, you will see an error message. You
should still be able to switch back.

However, if you have any issues, the container will append some information about the MAC address to the file macs.txt
each time it starts. If you have trouble getting the license to work, try using the `--mac-address` flag to the run
command to force your new container to have the same MAC address as your old one. This will only work if you are using
bridged networking.

Alternatively, or if you are running in a Kubernetes and cannot set your mac address, you can set the MAC_ADDRESS
variable, either in the container environment or in the xeoma.conf file. The container will set its own MAC address at
startup. Note that this may require the addition of the `--cap-add=NET_ADMIN` flag.

Finally, if all else fails, [use the felenasoft website for
help](http://felenasoft.com/xeoma/en/support/activation-issues/).

### Discovering Cameras

Depending on how your security camera works, you might need to enable host networking by adding `--net=host` to your run
command. If you are using IP cameras, you can run this container in bridged networking mode, which is more secure.
However, you will need to manually enter the URL for the camera, because the camera search feature probably won't work.
You can [consult this website](https://www.ispyconnect.com/sources.aspx) for information about rtsp:// URLs for
accessing the camera's low and high quality video streams.

### Support

If you find any bugs with the software that are related to the docker container, let me know and I'll investigate. If
you find bugs that are related to the actual software or cameras, etc then contact FelenaSoft.

## Running Tests

The default test suite requires Python 3, Bash at `/bin/bash`, `tar`, and standard Unix utilities on macOS or Linux. It
uses Python's built-in `unittest` module; no additional Python packages are needed.

From the repository root, run the default suite:

```sh
python3 -B -m unittest discover -s tests -v
```

The real Docker smoke test is skipped unless explicitly enabled. The default suite uses temporary directories, mock
commands, and an HTTP server bound to `127.0.0.1` on an automatically selected port. Your environment must allow
loopback connections. No external internet access or Docker server is needed for these tests.

| Test file | Coverage |
| --- | --- |
| `test_config.py` | Settings, secret files, defaults, environment precedence, stale settings, and first-run setup |
| `test_build.py` | Development/publish command selection, help, invalid arguments, and Docker command failures |
| `test_installer.py` | Stable/beta/pinned/custom versions, downloads, fallback, caching, extraction, and failures |
| `test_init.py` | Conditional hourly-job registration, version changes, and failed startup cleanup |
| `test_updates.py` | Installing updates, restart requests, unchanged/pinned versions, and failed downloads |
| `test_configure.py` | Password arguments, MAC handling, storage links, repeated setup, and command failures |
| `test_docker.py` | Real image, secrets, UID/GID, umask, cron, service restart, and storage persistence |

For example, run just the installer tests with:

```sh
python3 -B -m unittest discover -s tests -p test_installer.py -v
```

The installer tests serve fixture version XML and small archives from the local HTTP endpoint. They execute the real
installer with redirected paths and URLs, including real archive extraction and installation fingerprints. The update
tests call that installer and record service restart requests instead of killing processes. The Xeoma configuration
tests create real temporary storage links and record calls to Xeoma and network commands. They do not change your
network interfaces, passwords, existing containers, or stored camera settings.

### Real Docker Smoke Test

To also verify the actual image and proprietary Xeoma executable, enable the Docker smoke test:

```sh
XEOMA_DOCKER_TESTS=1 python3 -B -m unittest discover -s tests -p test_docker.py -v
```

This requires Docker with Buildx, a reachable Linux Docker server capable of running `linux/amd64` images, and internet
access for the base image, packages, and Xeoma download. It uses your current Docker context, including a remote server.
The test builds a unique `coppit/xeoma-test:suite-...` image and starts a disposable container with anonymous volumes.
It publishes no ports and uses no existing host directories or volumes. A temporary test password file is copied in.
It checks that Xeoma listens on port 8090 inside the container, runs with the requested UID/GID and umask, and survives
service and container restarts. It also checks secret-file configuration, legacy password fallback, read-only password mounts with and without a parent directory mount, and cron
availability. It removes its containers, test volumes, and image
afterward; Docker's build cache remains. It never pushes an image.

By default, this downloads the latest stable Xeoma release. To select a specific version:

```sh
XEOMA_DOCKER_TESTS=1 XEOMA_TEST_VERSION=25.8.22 python3 -B -m unittest discover -s tests -p test_docker.py -v
```

Allow several minutes for a fresh build and download. External service failures can cause this optional test to fail.
This is a startup smoke test, not a camera recording, licensing, or client authentication test.

New test files should be named `tests/test_*.py` and use `unittest.TestCase`. Keep new lines within 120 characters.

## Credits

This docker container was initially based on the [jedimonkey/xeoma
container](https://github.com/jedimonkey/xeoma-docker).

Thanks to [https://github.com/skylord123](skylord123) on github for the excellent suggestions about how to handle
versioning.
