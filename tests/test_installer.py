"""Installer integration tests using real HTTP, archive extraction, and symlinks."""

from xeoma_fixture import XeomaFixture


class InstallerTests(XeomaFixture):
    def setUp(self):
        super().setUp()
        self.start_server()
        self.stable = self.archive_bytes("stable")
        self.beta = self.archive_bytes("beta")
        self.metadata(beta="25.9.1")
        self.serve("/stable.tgz", self.stable)
        self.serve("/beta.tgz", self.beta)

    def test_latest_stable_installs_and_creates_fingerprint_and_symlink(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed(self.stable, "stable")
        self.assertEqual(self.server.requests, ["/version.xml", "/stable.tgz"])

    def test_empty_version_defaults_to_latest(self):
        self.set_version("")
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed(self.stable, "stable")

    def test_latest_beta(self):
        self.set_version("latest_beta")
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed(self.beta, "beta")
        self.assertEqual(self.server.requests, ["/version.xml", "/beta.tgz"])

    def test_missing_beta_uses_stable(self):
        self.set_version("latest_beta")
        self.metadata()
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed(self.stable, "stable")

    def test_pinned_version_skips_metadata(self):
        self.set_version("25.8.22")
        path = "/versions/2025-8-22/linux/xeoma_linux64.tgz"
        self.serve(path, self.stable)
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed(self.stable, "stable")
        self.assertEqual(self.server.requests, [path])

    def test_custom_url_skips_metadata(self):
        self.set_version(f"{self.url}/custom.tgz")
        self.serve("/custom.tgz", self.stable)
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed(self.stable, "stable")
        self.assertTrue((self.downloads / "xeoma_from_url.tgz").exists())
        self.assertEqual(self.server.requests, ["/custom.tgz"])

    def test_unchanged_version_uses_cache_and_skips_extraction(self):
        self.assertEqual(self.run_installer().returncode, 0)
        installed = self.install / "xeoma.app"
        installed.write_text("sentinel: this must not be overwritten")
        self.server.requests.clear()
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Skipping installation", result.stderr)
        self.assertEqual(installed.read_text(), "sentinel: this must not be overwritten")
        self.assertEqual(self.server.requests, ["/version.xml"])

    def test_new_version_replaces_install_and_removes_old_download(self):
        self.assertEqual(self.run_installer().returncode, 0)
        unrelated = self.downloads / "keep.txt"
        unrelated.write_text("keep")
        self.metadata(stable="25.9.1", stable_path="/beta.tgz")
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed(self.beta, "beta")
        self.assertFalse((self.downloads / "xeoma_25.8.22.tgz").exists())
        self.assertTrue((self.downloads / "xeoma_25.9.1.tgz").exists())
        self.assertEqual(unrelated.read_text(), "keep")

    def test_vendor_missing_file_response_uses_alternate_url(self):
        self.set_version("latest_beta")
        self.serve("/beta.tgz", b"file not found")
        alternate = "/versions/25-9-1/linux/xeoma_linux64.tgz"
        self.serve(alternate, self.beta)
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed(self.beta, "beta")
        self.assertEqual(self.server.requests, ["/version.xml", "/beta.tgz", alternate])

    def test_both_download_locations_missing_fail_without_install(self):
        self.serve("/stable.tgz", b"file not found")
        self.serve("/versions/25-8-22/linux/xeoma_linux64.tgz", b"file not found")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.breadcrumb.exists())
        self.assertFalse(self.binary.exists())
        self.assertFalse((self.downloads / "xeoma_temp.tgz").exists())

    def test_http_failure_does_not_install(self):
        self.serve("/stable.tgz", b"server unavailable", status=503)
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.breadcrumb.exists())

    def test_malformed_metadata_does_not_install(self):
        self.serve("/version.xml", b"not XML")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.server.requests, ["/version.xml"])
        self.assertFalse(self.breadcrumb.exists())

    def test_invalid_archive_preserves_existing_install_fingerprint(self):
        self.assertEqual(self.run_installer().returncode, 0)
        self.metadata(stable="25.9.1", stable_path="/broken.tgz")
        self.serve("/broken.tgz", b"not an archive")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assert_installed(self.stable, "stable")
