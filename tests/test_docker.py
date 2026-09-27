"""Opt-in smoke test of the actual image and vendor binary on a Docker server."""

import os
import subprocess
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
            if self.docker("exec", container, "python3", "-c", probe, check=False).returncode == 0:
                return
            time.sleep(2)
        logs = self.docker("logs", container, check=False)
        self.fail("Xeoma did not start listening on port 8090.\n" + logs.stdout + logs.stderr)

    def test_real_install_configuration_and_restart(self):
        image = f"coppit/xeoma-test:suite-{uuid.uuid4().hex[:12]}"
        self.addCleanup(self.docker, "image", "rm", image, check=False)
        self.docker("buildx", "build", "--platform", "linux/amd64", "--load", "-t", image, ".", timeout=600)
        # Anonymous volumes belong only to this test. No host mounts or published ports are used.
        container = self.docker(
            "create", "--platform", "linux/amd64",
            "--label", "xeoma.test-suite=true",
            "-e", "PASSWORD=xeoma-test-only-password",
            "-e", f"VERSION={os.environ.get('XEOMA_TEST_VERSION', 'latest')}",
            image,
        ).stdout.strip()
        self.addCleanup(self.docker, "rm", "-f", "-v", container)
        self.docker("start", container)
        self.wait_for_server(container)
        self.docker("exec", container, "bash", "-ec", '''
test -s /etc/envvars.merged
test -x /usr/bin/xeoma
test -L /usr/bin/xeoma
test "$(readlink /usr/local/Xeoma)" = /config
test "$(readlink /config/XeomaArchive)" = /archive
test -s /config/macs.txt
run-parts --test /etc/cron.hourly | grep -Fx /etc/cron.hourly/update-permissions
''')
        fingerprint = self.docker("exec", container, "cat", "/files/xeoma/last_installed_version.txt").stdout
        self.assertRegex(fingerprint, r"^[0-9a-f]{32}$")
        self.docker("exec", container, "bash", "-c", "echo preserved > /config/test-persistence")
        self.docker("restart", container)
        self.wait_for_server(container)
        self.assertEqual(self.docker("exec", container, "cat", "/config/test-persistence").stdout, "preserved\n")
        self.assertEqual(
            self.docker("exec", container, "cat", "/files/xeoma/last_installed_version.txt").stdout, fingerprint
        )
