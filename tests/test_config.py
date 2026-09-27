"""Exercise configuration startup in a temporary filesystem, without a container."""

from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="xeoma-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.config_dir = self.root / "config"
        self.config_dir.mkdir()
        self.config_file = self.config_dir / "xeoma.conf"
        self.environment_file = self.root / "environment.sh"
        self.merged_file = self.root / "merged.sh"
        self.template = self.root / "templates" / "xeoma.conf.default"
        self.template.parent.mkdir()
        self.template.write_bytes((ROOT / "xeoma.conf.default").read_bytes())
        self.script = self.root / "parse_config_file.sh"

        # Redirect only filesystem locations; execute the production shell logic unchanged.
        source = (ROOT / "parse_config_file.sh").read_text()
        assignments = {
            "TEMPLATE_CONFIG_FILE=/files/xeoma.conf.default": ("TEMPLATE_CONFIG_FILE", self.template),
            "CONFIG_PATH=/config": ("CONFIG_PATH", self.config_dir),
            "ENV_VARS=/etc/container_environment.sh": ("ENV_VARS", self.environment_file),
            "MERGED_ENV_VARS=/etc/envvars.merged": ("MERGED_ENV_VARS", self.merged_file),
        }
        for original, (variable, path) in assignments.items():
            self.assertEqual(source.count(original + "\n"), 1)
            source = source.replace(original + "\n", f"{variable}={shlex.quote(str(path))}\n")
        self.script.write_text(source)
        # Avoid inheriting real PASSWORD/VERSION values; keep temporary config copies in the fixture.
        self.environment = {"PATH": os.defpath, "TMPDIR": str(self.root)}

    def run_config(self, settings=None, config=None):
        self.environment_file.write_text(
            "".join(f"export {key}={shlex.quote(value)}\n" for key, value in (settings or {}).items())
        )
        if config is not None:
            self.config_file.write_bytes(config.encode())
        return subprocess.run(
            ["/bin/bash", str(self.script)], env=self.environment, capture_output=True, text=True, timeout=10
        )

    def assert_settings(self, password, version="latest", mac_address=""):
        result = subprocess.run(
            [
                "/bin/bash", "-c",
                '. "$1"; printf "%s\\0" "$PASSWORD" "$VERSION" "$MAC_ADDRESS"',
                "bash", str(self.merged_file),
            ],
            env=self.environment, capture_output=True, text=True, check=True, timeout=10,
        )
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout.split("\0")[:-1], [password, version, mac_address])

    def test_environment_only_writes_merged_settings_and_defaults(self):
        password = "test secret with 'quotes' and $dollars"
        result = self.run_config({"PASSWORD": password})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_settings(password)
        self.assertFalse(self.config_file.exists())
        self.assertNotIn(password, result.stdout + result.stderr)

    def test_environment_only_preserves_explicit_settings(self):
        result = self.run_config({"PASSWORD": "secret", "VERSION": "25.8.22", "MAC_ADDRESS": "02:00:00:00:00:01"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_settings("secret", "25.8.22", "02:00:00:00:00:01")

    def test_environment_only_replaces_stale_merged_settings(self):
        self.merged_file.write_text("export PASSWORD=old VERSION=old MAC_ADDRESS=old\n")
        result = self.run_config({"PASSWORD": "new secret"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_settings("new secret")

    def test_environment_only_leaves_existing_config_untouched(self):
        config = "PASSWORD='file secret'\nVERSION=25.8.22\n"
        result = self.run_config({"PASSWORD": "environment secret"}, config)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_settings("environment secret")
        self.assertEqual(self.config_file.read_text(), config)

    def test_config_file_settings(self):
        result = self.run_config(config="PASSWORD='file secret'\nVERSION=25.8.22\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_settings("file secret", "25.8.22")

    def test_environment_overrides_file_and_accepts_windows_line_endings(self):
        config = "PASSWORD='file secret'\r\nVERSION=25.8.22\r\nMAC_ADDRESS=02:00:00:00:00:01\r\n"
        result = self.run_config({"VERSION": "latest_beta"}, config)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_settings("file secret", "latest_beta", "02:00:00:00:00:01")
        self.assertEqual(self.config_file.read_bytes(), config.encode())

    def test_empty_version_uses_default(self):
        result = self.run_config(config="PASSWORD=secret\nVERSION=''\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_settings("secret")

    def test_missing_password_does_not_write_merged_settings(self):
        result = self.run_config(config="PASSWORD=''\nVERSION=latest\n")
        self.assertIn("Missing required settings", result.stdout)
        self.assertFalse(self.merged_file.exists())

    def test_first_run_creates_template_and_stops(self):
        result = self.run_config()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.config_file.read_bytes(), self.template.read_bytes())
        self.assertFalse(self.merged_file.exists())

    def test_unedited_template_stops(self):
        result = self.run_config(config=self.template.read_text())
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertFalse(self.merged_file.exists())

    def test_template_copy_failure_stops(self):
        self.template.unlink()
        result = self.run_config()
        self.assertEqual(result.returncode, 4)
        self.assertIn("Could not copy template config file", result.stdout)
        self.assertFalse(self.merged_file.exists())


if __name__ == "__main__":
    unittest.main()
