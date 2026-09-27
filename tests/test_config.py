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
        self.password_file = self.config_dir / "xeoma_password"
        self.template.write_text((ROOT / "xeoma.conf.default").read_text().replace(
            "/config/xeoma_password", str(self.password_file)
        ))
        self.script = self.root / "parse_config_file.sh"

        # Redirect only filesystem locations; execute the production shell logic unchanged.
        source = (ROOT / "parse_config_file.sh").read_text()
        assignments = {
            "TEMPLATE_CONFIG_FILE=/files/xeoma.conf.default": ("TEMPLATE_CONFIG_FILE", self.template),
            "CONFIG_PATH=/config": ("CONFIG_PATH", self.config_dir),
            "ENV_VARS=/run/xeoma/environment.sh": ("ENV_VARS", self.environment_file),
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
        self.assertIn("PASSWORD is set in the environment", result.stderr)
        self.assertNotIn(password, result.stdout + result.stderr)

    def test_password_file_overrides_password_and_keeps_contents_literal(self):
        secret = self.password_file
        password = "file 'secret' $dollars $(not-a-command)"
        secret.write_text(password + "\n")
        result = self.run_config({"PASSWORD": "ignored"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_settings(password)
        self.assertEqual(self.merged_file.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(password, result.stdout + result.stderr)

    def test_invalid_password_file_falls_back_to_environment(self):
        secret = self.password_file
        for contents in (None, "", "\n"):
            with self.subTest(contents=contents):
                if contents is not None:
                    secret.write_text(contents)
                result = self.run_config({"PASSWORD": "fallback secret"})
                self.assertEqual(result.returncode, 0, result.stderr)
                if contents is not None:
                    self.assertIn("falling back", result.stderr)
                self.assertIn("PASSWORD is set in the environment", result.stderr)
                self.assertNotIn("fallback secret", result.stdout + result.stderr)
                self.assert_settings("fallback secret")

    def test_invalid_password_file_falls_back_to_config(self):
        self.password_file.write_text("")
        result = self.run_config(
            {}, "PASSWORD='config secret'\nVERSION=25.8.22\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("falling back", result.stderr)
        self.assertNotIn("PASSWORD is set in the environment", result.stderr)
        self.assert_settings("config secret", "25.8.22")

    def test_invalid_password_file_without_fallback_uses_first_run_setup(self):
        self.password_file.write_text("")
        result = self.run_config()
        self.assertEqual(result.returncode, 1)
        self.assertIn("falling back", result.stderr)
        self.assertEqual(self.config_file.read_bytes(), self.template.read_bytes())
        self.assertFalse(self.merged_file.exists())

    def test_password_file_only_does_not_warn_about_environment_password(self):
        secret = self.password_file
        secret.write_text("file secret")
        result = self.run_config()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assert_settings("file secret")

    def test_environment_only_preserves_explicit_settings(self):
        result = self.run_config({"PASSWORD": "secret", "VERSION": "25.8.22", "MAC_ADDRESS": "02:00:00:00:00:01"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_settings("secret", "25.8.22", "02:00:00:00:00:01")

    def test_environment_only_replaces_stale_merged_settings(self):
        self.merged_file.write_text("export PASSWORD=old VERSION=old MAC_ADDRESS=old\n")
        result = self.run_config({"PASSWORD": "new secret"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_settings("new secret")

    def test_environment_password_merges_existing_config_without_rewriting_it(self):
        config = "PASSWORD='file secret'\nVERSION=25.8.22\n"
        result = self.run_config({"PASSWORD": "environment secret"}, config)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_settings("environment secret", "25.8.22")
        self.assertEqual(self.config_file.read_text(), config)

    def test_password_file_merges_config_and_environment_settings(self):
        self.password_file.write_text("secret from environment file")
        config = "PASSWORD='legacy secret'\nVERSION=25.8.22\nMAC_ADDRESS=02:00:00:00:00:01\n"
        result = self.run_config({"VERSION": "latest_beta"}, config)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_settings("secret from environment file", "latest_beta", "02:00:00:00:00:01")

    def test_config_password_file_still_takes_precedence_over_merged_password(self):
        self.password_file.write_text("file secret")
        result = self.run_config({"PASSWORD": "environment secret"},
                                 self.template.read_text())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_settings("file secret")

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
        self.assertIn("ERROR: No password is set. Startup stopped.", result.stderr)
        self.assertFalse(self.merged_file.exists())

    def test_first_run_creates_template_and_stops(self):
        result = self.run_config()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.config_file.read_bytes(), self.template.read_bytes())
        self.assertFalse(self.merged_file.exists())

    def test_generated_password_file_is_private_and_empty(self):
        result = self.run_config()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.password_file.read_bytes(), b"")
        self.assertEqual(self.password_file.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("read -r PASSWORD", self.config_file.read_text())

    def test_immediate_restart_after_generation_requires_password(self):
        self.assertEqual(self.run_config().returncode, 1)
        for contents in ("", "\n\n"):
            with self.subTest(contents=contents):
                self.password_file.write_text(contents)
                result = self.run_config()
                self.assertEqual(result.returncode, 1)
                self.assertIn("ERROR: No password is set. Startup stopped.", result.stderr)
                self.assertIn("/config/xeoma_password", result.stderr)
                self.assertFalse(self.merged_file.exists())
        result = self.run_config({"PASSWORD": "legacy-secret"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_settings("legacy-secret", "latest", "")

    def test_generated_config_accepts_literal_password_without_config_edits(self):
        self.assertEqual(self.run_config().returncode, 1)
        password = "  quotes '\" backslash \\ $dollars `literal` $(touch should-not-exist) # tail  "
        self.password_file.write_text(password + "\n\n\n")
        result = self.run_config()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_settings(password)
        self.assertFalse((self.root / "should-not-exist").exists())
        self.assertNotIn(password, result.stdout + result.stderr)

    def test_password_file_preserves_echo_options_whitespace_and_internal_newlines(self):
        for password in ("-n", "-e", "  ", "first\nsecond"):
            with self.subTest(password=password):
                self.password_file.write_text(password + "\n\n")
                result = self.run_config()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assert_settings(password)

    def test_default_password_file_works_without_config(self):
        self.password_file.write_text("existing secret")
        self.assertEqual(self.run_config().returncode, 0)
        self.assertEqual(self.password_file.read_text(), "existing secret")
        self.assert_settings("existing secret")

    def test_config_password_file_preserves_version_and_mac(self):
        self.password_file.write_text("literal password")
        config = self.template.read_text().replace("VERSION='latest'", "VERSION='25.8.22'")
        config = config.replace("MAC_ADDRESS=", "MAC_ADDRESS=02:00:00:00:00:01")
        result = self.run_config(config=config)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_settings("literal password", "25.8.22", "02:00:00:00:00:01")

    def test_unedited_template_without_password_stops(self):
        result = self.run_config(config=self.template.read_text())
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(self.merged_file.exists())

    def test_template_copy_failure_stops(self):
        self.template.unlink()
        result = self.run_config()
        self.assertEqual(result.returncode, 4)
        self.assertIn("Could not copy template config file", result.stdout)
        self.assertFalse(self.merged_file.exists())


if __name__ == "__main__":
    unittest.main()
