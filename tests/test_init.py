"""Exercise startup cron registration with isolated paths and recorded setup steps."""

from xeoma_fixture import ROOT, XeomaFixture, redirect


class InitTests(XeomaFixture):
    def setUp(self):
        super().setUp()
        self.runtime = self.root / "runtime"
        self.hourly = self.root / "hourly"
        self.hourly.mkdir()
        self.job = self.root / "crontabs" / "root"
        self.installed_crontab = self.calls / "crontab"
        self.updater = self.mock_command("updater", "exit 0\n")
        self.parser = self.mock_command("parser", 'exit "${CONFIG_EXIT_CODE:-0}"\n')
        self.setup_step = self.mock_command("setup", "exit 0\n")
        self.mock_command("crontab", 'if [[ "$3" == -l ]]; then cat "$CALLS/crontab" 2>/dev/null; else cp "$3" "$CALLS/crontab"; fi\n')
        self.mock_command("id", 'echo 911\n')
        self.environment.update(PUID="911", PGID="911", UMASK="022", VERSION="latest")
        self.script = self.root / "init.sh"
        self.script.write_text(redirect((ROOT / "init-xeoma.sh").read_text(), {
            "/run/xeoma": self.runtime,
            "/etc/cron.hourly/update_xeoma": self.hourly / "update_xeoma",
            "/etc/crontabs": self.job.parent,
            "/etc/envvars.merged": self.merged,
            "/config/xeoma.conf": self.config / "xeoma.conf",
            "/config/xeoma_password": self.config / "xeoma_password",
            "/usr/local/lib/xeoma/parse_config_file.sh": self.parser,
            "/usr/local/lib/xeoma/install_xeoma.py": self.setup_step,
            "/usr/local/lib/xeoma/configure_xeoma.sh": self.setup_step,
            "/usr/local/lib/xeoma/update_xeoma.sh": self.updater,
        }))

    def run_init(self):
        return self.run_command("/bin/bash", str(self.script))

    def test_registration_tracks_resolved_version_across_restarts(self):
        # The inherited VERSION remains latest; only the saved settings should count.
        for version in ("latest", "latest", "25.8.22", "latest_beta", "https://example.test/xeoma.tgz"):
            with self.subTest(version=version):
                self.set_version(version)
                result = self.run_init()
                self.assertEqual(result.returncode, 0, result.stderr)
                # Simulate LinuxServer importing the generated file after our init step.
                self.installed_crontab.write_text(self.job.read_text())
                if version in ("latest", "latest_beta"):
                    self.assertEqual(self.job.read_text().count("# xeoma-auto-update"), 1)
                    self.assertIn(str(self.updater), self.job.read_text())
                else:
                    self.assertNotIn("# xeoma-auto-update", self.job.read_text())

    def test_failed_configuration_removes_stale_registration(self):
        self.assertEqual(self.run_init().returncode, 0)
        self.installed_crontab.write_text(self.job.read_text())
        self.environment["CONFIG_EXIT_CODE"] = "1"
        result = self.run_init()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("# xeoma-auto-update", self.installed_crontab.read_text())
        self.assertFalse((self.runtime / "ready").exists())

    def test_unrelated_root_jobs_are_preserved(self):
        other = "0 1 * * * /usr/local/bin/backup\n"
        self.installed_crontab.write_text(other + "17 * * * * /old-updater # xeoma-auto-update\n")
        self.set_version("25.8.22")
        self.assertEqual(self.run_init().returncode, 0)
        self.assertEqual(self.job.read_text(), other)
        self.assertEqual(self.installed_crontab.read_text(), other)
