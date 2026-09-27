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
        path = "/versions/2025-08-22/linux/xeoma_linux64.tgz"
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

    def test_pinned_version_pads_both_month_and_day(self):
        self.set_version("26.2.3")
        path = "/versions/2026-02-03/linux/xeoma_linux64.tgz"
        self.serve(path, self.stable)
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed(self.stable, "stable")
        self.assertEqual(self.server.requests, [path])

    def test_http_errors_use_versioned_fallback(self):
        self.set_version("latest_beta")
        alternate = "/versions/2025-09-01/linux/xeoma_linux64.tgz"
        self.serve(alternate, self.beta)
        for status in (404, 503):
            with self.subTest(status=status):
                self.server.requests.clear()
                self.serve("/beta.tgz", b"download unavailable", status=status)
                cached = self.downloads / "xeoma_25.9.1.tgz"
                if cached.exists():
                    cached.unlink()
                result = self.run_installer()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assert_installed(self.beta, "beta")
                self.assertEqual(self.server.requests, ["/version.xml", "/beta.tgz", alternate])
                self.assertFalse((self.downloads / "xeoma_temp.tgz").exists())

    def test_http_failure_without_fallback_exits_cleanly(self):
        self.set_version(f"{self.url}/missing.tgz")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HTTP Error 404", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.server.requests, ["/missing.tgz"])
        self.assertFalse(self.binary.exists())

    def test_incomplete_download_uses_fallback(self):
        self.serve("/stable.tgz", self.stable[:10], content_length=len(self.stable))
        alternate = "/versions/2025-08-22/linux/xeoma_linux64.tgz"
        self.serve(alternate, self.stable)
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed(self.stable, "stable")
        self.assertEqual(self.server.requests, ["/version.xml", "/stable.tgz", alternate])
        self.assertFalse((self.downloads / "xeoma_temp.tgz").exists())

    def test_incomplete_download_without_fallback_cleans_partial_file(self):
        self.set_version(f"{self.url}/truncated.tgz")
        self.serve("/truncated.tgz", self.stable[:10], content_length=len(self.stable))
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse((self.downloads / "xeoma_temp.tgz").exists())
        self.assertFalse((self.downloads / "xeoma_from_url.tgz").exists())
        self.assertFalse(self.breadcrumb.exists())

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
        alternate = "/versions/2025-09-01/linux/xeoma_linux64.tgz"
        self.serve(alternate, self.beta)
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed(self.beta, "beta")
        self.assertEqual(self.server.requests, ["/version.xml", "/beta.tgz", alternate])

    def test_both_download_locations_missing_fail_without_install(self):
        self.serve("/stable.tgz", b"file not found")
        self.serve("/versions/2025-08-22/linux/xeoma_linux64.tgz", b"file not found")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.breadcrumb.exists())
        self.assertFalse(self.binary.exists())
        self.assertFalse((self.downloads / "xeoma_temp.tgz").exists())

    def test_http_failure_does_not_install(self):
        self.serve("/stable.tgz", b"server unavailable", status=503)
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(
            self.server.requests, ["/version.xml", "/stable.tgz", "/versions/2025-08-22/linux/xeoma_linux64.tgz"]
        )
        self.assertFalse(self.breadcrumb.exists())
        self.assertFalse((self.downloads / "xeoma_temp.tgz").exists())

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
