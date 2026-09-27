"""Opt-in smoke test of the actual image and vendor binary on a Docker server."""

import os
import subprocess
import tempfile
from pathlib import Path
import time
import unittest
import uuid

from xeoma_fixture import ROOT


@unittest.skipUnless(os.environ.get("XEOMA_DOCKER_TESTS") == "1", "set XEOMA_DOCKER_TESTS=1 for real Docker tests")
class DockerTests(unittest.TestCase):
    def docker(self, *arguments, timeout=60, check=True):
        result = subprocess.run(
            ["docker", *arguments], cwd=ROOT, capture_output=True, text=True, timeout=timeout
        )
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def wait_for_server(self, container):
        deadline = time.monotonic() + 180
        probe = "import socket; socket.create_connection(('127.0.0.1', 8090), timeout=2).close()"
        while time.monotonic() < deadline:
            state = self.docker("inspect", "--format", "{{.State.Running}}", container).stdout.strip()
            if state != "true":
                break
            if (self.docker("exec", container, "test", "-f", "/run/xeoma/ready", check=False).returncode == 0
                    and self.docker("exec", container, "python3", "-c", probe, check=False).returncode == 0):
                return
            time.sleep(2)
        logs = self.docker("logs", container, check=False)
        self.fail("Xeoma did not start listening on port 8090.\n" + logs.stdout + logs.stderr)

    def test_real_install_configuration_and_restart(self):
        image = f"coppit/xeoma-test:suite-{uuid.uuid4().hex[:12]}"
        self.addCleanup(self.docker, "image", "rm", image, check=False)
        self.docker("buildx", "build", "--platform", "linux/amd64", "--load", "-t", image, ".", timeout=600)
        # Storage belongs only to this test. No existing host data or published ports are used.
        container = self.docker(
            "create", "--platform", "linux/amd64",
            "--label", "xeoma.test-suite=true",
            "-e", "PUID=12345", "-e", "PGID=12346", "-e", "UMASK=007",
            "-e", f"VERSION={os.environ.get('XEOMA_TEST_VERSION', 'latest')}",
            image,
        ).stdout.strip()
        self.addCleanup(self.docker, "rm", "-f", "-v", container)
        with tempfile.TemporaryDirectory() as directory:
            secret = Path(directory) / "secrets"
            secret.mkdir()
            (secret / "xeoma_password").write_text("xeoma-test-only-password\n")
            self.docker("cp", str(secret / "xeoma_password"), f"{container}:/config/xeoma_password")
        self.docker("start", container)
        self.wait_for_server(container)
        self.docker("exec", container, "bash", "-ec", '''
test -s /etc/envvars.merged
test -x /usr/bin/xeoma
test -L /usr/bin/xeoma
test "$(readlink /usr/local/Xeoma)" = /config
test "$(readlink /config/XeomaArchive)" = /archive
test -s /config/macs.txt
test "$(stat -c %a /etc/envvars.merged)" = 600
test "$(stat -c %u:%g /config)" = 12345:12346
test "$(stat -c %u:%g /archive)" = 12345:12346
pid=$(s6-svstat -o pid /run/service/svc-xeoma)
test "$(awk '/^Uid:/ {print $2}' /proc/$pid/status)" = 12345
test "$(awk '/^Gid:/ {print $2}' /proc/$pid/status)" = 12346
test "$(awk '/^Umask:/ {print $2}' /proc/$pid/status)" = 0007
. /etc/envvars.merged
case "$VERSION" in
  latest|latest_beta) crontab -u root -l | grep -F "# xeoma-auto-update"; pgrep -x cron ;;
  *) ! crontab -u root -l | grep -F "# xeoma-auto-update" ;;
esac
''')
        fingerprint = self.docker("exec", container, "cat", "/files/xeoma/last_installed_version.txt").stdout
        self.assertRegex(fingerprint, r"^[0-9a-f]{32}$")
        self.docker("exec", container, "bash", "-c", "echo preserved > /config/test-persistence")
        # Exercise the actual supervisor restart operation used after an update.
        old_pid = self.docker("exec", container, "s6-svstat", "-o", "pid", "/run/service/svc-xeoma").stdout
        self.docker("exec", container, "s6-svc", "-r", "/run/service/svc-xeoma")
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            new_pid = self.docker("exec", container, "s6-svstat", "-o", "pid", "/run/service/svc-xeoma").stdout
            if new_pid.strip() not in ("0", "-1", "") and new_pid != old_pid:
                break
            time.sleep(1)
        self.assertNotEqual(old_pid, new_pid, "s6 did not restart Xeoma within 60 seconds")
        self.wait_for_server(container)
        self.docker("restart", container)
        self.wait_for_server(container)
        self.assertEqual(self.docker("exec", container, "cat", "/config/test-persistence").stdout, "preserved\n")
        self.assertEqual(
            self.docker("exec", container, "cat", "/files/xeoma/last_installed_version.txt").stdout, fingerprint
        )

        fallback = self.docker(
            "create", "--label", "xeoma.test-suite=true",
            "-e", "PASSWORD=xeoma-fallback-test-password",
            "-e", f"VERSION={os.environ.get('XEOMA_TEST_VERSION', 'latest')}", image,
        ).stdout.strip()
        self.addCleanup(self.docker, "rm", "-f", "-v", fallback)
        self.docker("start", fallback)
        self.wait_for_server(fallback)
        logs = self.docker("logs", fallback)
        self.assertIn("PASSWORD is set in the environment", logs.stdout + logs.stderr)
        self.assertNotIn("xeoma-fallback-test-password", logs.stdout + logs.stderr)

        generated = self.docker(
            "create", "--label", "xeoma.test-suite=true",
            "-e", "PUID=12345", "-e", "PGID=12346", image,
        ).stdout.strip()
        self.addCleanup(self.docker, "rm", "-f", "-v", generated)
        self.docker("start", generated)
        self.assertNotEqual(self.docker("wait", generated, timeout=30).stdout.strip(), "0")
        # Inspect and fill the generated files using a short-lived helper sharing only test volumes.
        self.docker("run", "--rm", "--volumes-from", generated, "--entrypoint", "/bin/bash", image, "-ec", '''
test -f /config/xeoma_password
test ! -s /config/xeoma_password
test "$(stat -c %a /config/xeoma_password)" = 600
test "$(stat -c %u:%g /config/xeoma_password)" = 12345:12346
! grep -q '^PASSWORD_FILE=' /config/xeoma.conf
printf '%s\\n\\n' 'test-$literal-!hash#' > /config/xeoma_password
''')
        self.docker("start", generated)
        self.wait_for_server(generated)
        self.docker("exec", generated, "bash", "-ec", '''
. /etc/envvars.merged
test "$PASSWORD" = 'test-$literal-!hash#'
''')

        # Bind only disposable test data from the daemon host, including a nested read-only file.
        volume = f"xeoma-mount-test-{uuid.uuid4().hex[:12]}"
        self.docker("volume", "create", volume)
        self.addCleanup(self.docker, "volume", "rm", volume)
        self.docker("run", "--rm", "-v", f"{volume}:/test-data", "--entrypoint", "/bin/bash", image,
                    "-ec", "mkdir /test-data/config; printf '%s\\n' mount-test-password > /test-data/password; chmod 600 /test-data/password")
        source = self.docker("volume", "inspect", "--format", "{{.Mountpoint}}", volume).stdout.strip()
        for parent_mount in (False, True):
            mounts = ["--mount", f"type=bind,src={source}/password,dst=/config/xeoma_password,readonly"]
            if parent_mount:
                mounts += ["--mount", f"type=bind,src={source}/config,dst=/config"]
            mounted = self.docker("create", "--label", "xeoma.test-suite=true", *mounts, image).stdout.strip()
            self.addCleanup(self.docker, "rm", "-f", "-v", mounted)
            self.docker("start", mounted)
            self.wait_for_server(mounted)
            self.docker("exec", mounted, "bash", "-ec", '''
mountpoint -q /config/xeoma_password
. /etc/envvars.merged
test "$PASSWORD" = mount-test-password
test "$(stat -c %u:%g /config/xeoma_password)" = 0:0
! touch /config/xeoma_password
''')
