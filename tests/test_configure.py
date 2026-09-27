"""Apply Xeoma configuration to real temporary symlinks and recorded commands."""

import shlex

from xeoma_fixture import ROOT, XeomaFixture, redirect


class ConfigureTests(XeomaFixture):
    def setUp(self):
        super().setUp()
        self.legacy = self.root / "legacy"
        self.current = self.root / "local" / "Xeoma"
        self.current.parent.mkdir()
        self.network = self.root / "network" / "eth0"
        self.network.mkdir(parents=True)
        (self.network / "address").write_text("02:00:00:00:00:01\n")
        self.password = "test secret 'with quotes' $and dollars"
        self.settings()
        self.mock_command("ip", '''printf '%s\\n' "$*" >> "$CALLS/ip"
if [[ "$1" == route ]]; then
  echo 'default via 192.0.2.1 dev eth0'
fi
''')
        self.mock_command("xeoma", '''printf '%s\\0' "$@" >> "$CALLS/xeoma"
if [[ "$*" == *-setpassword* ]]; then
  printf "%s\\n" "$*" >&2
  exit "${PASSWORD_EXIT_CODE:-0}"
fi
''')
        self.mock_command("s6-setuidgid", 'shift; exec "$@"\n')
        self.mock_command("chown", 'printf "%s\\n" "$*" >> "$CALLS/ownership"\nexit "${CHOWN_EXIT_CODE:-0}"\n')
        self.mock_command("id", 'if [[ "$1" == -u ]]; then echo "${PUID:-911}"; else echo "${PGID:-911}"; fi\n')
        self.script = self.root / "configure.sh"
        self.script.write_text(redirect((ROOT / "configure_xeoma.sh").read_text(), {
            "/config": self.config,
            "/archive": self.archive,
            "/.config": self.legacy,
            "/usr/local/Xeoma": self.current,
            "/etc/envvars.merged": self.merged,
            "/usr/bin/xeoma": self.binary,
            "/sys/class/net": self.network.parent,
        }))

    def settings(self, mac=""):
        self.merged.write_text(
            f"export PASSWORD={shlex.quote(self.password)}\nexport MAC_ADDRESS={shlex.quote(mac)}\n"
        )

    def run_configure(self):
        return self.run_command("/bin/bash", str(self.script))

    def assert_links(self):
        for link, target in [
            (self.legacy / "Xeoma", self.config),
            (self.current, self.config),
            (self.config / "XeomaArchive", self.archive),
        ]:
            self.assertTrue(link.is_symlink(), link)
            self.assertEqual(link.resolve(), target)

    def test_sets_password_creates_storage_links_and_logs_mac(self):
        result = self.run_configure()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_links()
        self.assertEqual(
            (self.calls / "xeoma").read_bytes().decode().split("\0")[:-1],
            ["-setpassword", self.password, "-showpassword"],
        )
        self.assertIn("eth0 02:00:00:00:00:01", (self.config / "macs.txt").read_text())
        self.assertEqual((self.calls / "ip").read_text(), "route show default\n")
        self.assertNotIn(self.password, result.stdout + result.stderr)

    def test_explicit_mac_is_applied(self):
        self.settings(mac="02:00:00:00:00:02")
        result = self.run_configure()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (self.calls / "ip").read_text(),
            "link set eth0 address 02:00:00:00:00:02\nroute show default\n",
        )

    def test_repeated_configuration_preserves_data_and_links(self):
        sentinel = self.config / "settings.dat"
        sentinel.write_text("existing camera settings")
        for _ in range(2):
            result = self.run_configure()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assert_links()
        self.assertEqual(sentinel.read_text(), "existing camera settings")
        self.assertFalse((self.config / "config").exists())
        self.assertEqual(len((self.config / "macs.txt").read_text().splitlines()), 2)

    def test_stale_symlinks_are_replaced(self):
        self.legacy.mkdir()
        for link in (self.legacy / "Xeoma", self.current, self.config / "XeomaArchive", self.config / "config"):
            link.symlink_to(self.root / "missing")
        result = self.run_configure()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_links()
        self.assertFalse((self.config / "config").is_symlink())

    def test_password_failure_stops_configuration(self):
        self.environment["PASSWORD_EXIT_CODE"] = "7"
        result = self.run_configure()
        self.assertEqual(result.returncode, 7)
        self.assertIn("Xeoma's password-setting command failed (exit status 7). Startup stopped.", result.stderr)
        self.assertIn("then restart the container", result.stderr)
        self.assertNotIn(self.password, result.stdout + result.stderr)
        self.assertEqual(
            (self.calls / "xeoma").read_bytes().decode().split("\0")[:-1],
            ["-setpassword", self.password],
        )

    def recursive_ownership_calls(self):
        return [line for line in (self.calls / "ownership").read_text().splitlines() if line.startswith("-hR ")]

    def test_ownership_migration_runs_once_and_repeats_for_changed_ids(self):
        marker = self.config / ".xeoma-ownership"
        self.assertEqual(self.run_configure().returncode, 0)
        self.assertTrue(marker.read_text().startswith("v2:911:911:"))
        self.assertEqual(self.run_configure().returncode, 0)
        self.assertEqual(len(self.recursive_ownership_calls()), 1)
        for key, value in (("PUID", "99"), ("PGID", "100")):
            self.environment[key] = value
            self.assertEqual(self.run_configure().returncode, 0)
        self.assertTrue(marker.read_text().startswith("v2:99:100:"))
        self.assertEqual(len(self.recursive_ownership_calls()), 3)
        marker.unlink()
        self.assertEqual(self.run_configure().returncode, 0)
        self.assertEqual(len(self.recursive_ownership_calls()), 4)

    def test_failed_ownership_migration_is_retried(self):
        marker = self.config / ".xeoma-ownership"
        marker.write_text("old marker")
        self.environment["CHOWN_EXIT_CODE"] = "1"
        self.assertNotEqual(self.run_configure().returncode, 0)
        self.assertFalse(marker.exists())
        self.environment.pop("CHOWN_EXIT_CODE")
        self.assertEqual(self.run_configure().returncode, 0)
        self.assertTrue(marker.read_text().startswith("v2:911:911:"))
        self.assertEqual(len(self.recursive_ownership_calls()), 1)

    def test_downgrade_and_reupgrade_repeats_migration(self):
        self.assertEqual(self.run_configure().returncode, 0)
        self.assertEqual(self.run_configure().returncode, 0)
        self.assertEqual(len(self.recursive_ownership_calls()), 1)
        # A legacy image appends its startup entry without updating the breadcrumb.
        with (self.config / "macs.txt").open("a") as history:
            history.write("[legacy image start] eth0 02:00:00:00:00:01\n")
        self.assertEqual(self.run_configure().returncode, 0)
        self.assertEqual(len(self.recursive_ownership_calls()), 2)
        self.assertEqual(self.run_configure().returncode, 0)
        self.assertEqual(len(self.recursive_ownership_calls()), 2)
