"""Run the hourly updater with the real installer and a harmless restart recorder."""

import shlex
import sys

from xeoma_fixture import ROOT, XeomaFixture, redirect


class UpdateTests(XeomaFixture):
    def setUp(self):
        super().setUp()
        self.start_server()
        self.stable = self.archive_bytes("stable")
        self.metadata()
        self.serve("/stable.tgz", self.stable)
        self.mock_command("pkill", 'printf "%s\\n" "$@" >> "$CALLS/restarts"\n')
        self.updater = self.root / "update.sh"
        installer_command = f"{shlex.quote(sys.executable)} -B {shlex.quote(str(self.installer))}"
        self.updater.write_text(redirect((ROOT / "update_xeoma.sh").read_text(), {
            "/files/xeoma": self.install,
            "/etc/envvars.merged": self.merged,
            "/etc/my_init.d/40_install_xeoma.py": installer_command,
        }))

    def run_update(self):
        return self.run_command("/bin/bash", str(self.updater))

    def test_changed_version_installs_and_requests_restart(self):
        self.assertEqual(self.run_installer().returncode, 0)
        updated = self.archive_bytes("updated")
        self.metadata(stable="25.9.1", stable_path="/updated.tgz")
        self.serve("/updated.tgz", updated)
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed(updated, "updated")
        self.assertEqual((self.calls / "restarts").read_text(), "xeoma\n")

    def test_unchanged_version_does_not_restart(self):
        self.assertEqual(self.run_installer().returncode, 0)
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed(self.stable, "stable")
        self.assertFalse((self.calls / "restarts").exists())

    def test_first_install_requests_restart(self):
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed(self.stable, "stable")
        self.assertEqual((self.calls / "restarts").read_text(), "xeoma\n")

    def test_failed_download_preserves_install_and_does_not_restart(self):
        self.assertEqual(self.run_installer().returncode, 0)
        self.metadata(stable="25.9.1", stable_path="/unavailable.tgz")
        self.serve("/unavailable.tgz", b"unavailable", status=503)
        result = self.run_update()
        self.assertIn("HTTP Error 503", result.stderr)
        self.assert_installed(self.stable, "stable")
        self.assertFalse((self.calls / "restarts").exists())

    def test_pinned_version_does_not_follow_latest(self):
        self.set_version("25.8.22")
        self.serve("/versions/2025-08-22/linux/xeoma_linux64.tgz", self.stable)
        self.assertEqual(self.run_installer().returncode, 0)
        self.metadata(stable="25.9.1")
        self.server.requests.clear()
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed(self.stable, "stable")
        self.assertEqual(self.server.requests, [])
        self.assertFalse((self.calls / "restarts").exists())

    def test_latest_beta_installs_and_requests_restart(self):
        self.set_version("latest_beta")
        beta = self.archive_bytes("beta")
        self.metadata(beta="25.9.1")
        self.serve("/beta.tgz", beta)
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed(beta, "beta")
        self.assertEqual((self.calls / "restarts").read_text(), "xeoma\n")

    def test_pinned_and_custom_versions_skip_installer_even_without_installation(self):
        for version in ("25.8.22", f"{self.url}/stable.tgz"):
            with self.subTest(version=version):
                self.set_version(version)
                result = self.run_update()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Skipping auto-update", result.stdout)
                self.assertEqual(self.server.requests, [])
                self.assertFalse(self.breadcrumb.exists())
                self.assertFalse((self.calls / "restarts").exists())

    def test_invalid_saved_settings_cannot_fall_back_to_inherited_latest(self):
        self.environment["VERSION"] = "latest"
        for contents in (None, "", "export VERSION=''\n", "export VERSION='latest\n", "return 1\n"):
            with self.subTest(contents=contents):
                if contents is None:
                    self.merged.unlink()
                else:
                    self.merged.write_text(contents)
                result = self.run_update()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Cannot read saved VERSION", result.stderr)
                self.assertEqual(self.server.requests, [])
                self.assertFalse(self.breadcrumb.exists())
                self.assertFalse((self.calls / "restarts").exists())
