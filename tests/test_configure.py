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
  exit "${PASSWORD_EXIT_CODE:-0}"
fi
''')
        self.script = self.root / "configure.sh"
        self.script.write_text(redirect((ROOT / "50_configure_xeoma.sh").read_text(), {
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
            ["-core", "-setpassword", self.password, "-showpassword"],
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
        self.assertEqual(
            (self.calls / "xeoma").read_bytes().decode().split("\0")[:-1],
            ["-core", "-setpassword", self.password],
        )
