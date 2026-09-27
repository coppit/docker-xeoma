"""Check build and publish commands without invoking Docker."""

from pathlib import Path
import os
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BuildTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="xeoma-build-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.calls = self.root / "docker-arguments"
        docker = self.root / "docker"
        docker.write_text(
            '#!/bin/bash\nprintf "%s\\0" "$@" >> "$DOCKER_CALLS"\nexit "${DOCKER_EXIT_CODE:-0}"\n'
        )
        docker.chmod(0o755)
        self.environment = {"PATH": f"{self.root}{os.pathsep}{os.defpath}", "DOCKER_CALLS": str(self.calls)}

    def run_build(self, *arguments):
        return subprocess.run(
            ["/bin/bash", str(ROOT / "build.sh"), *arguments],
            cwd=self.root, env=self.environment, capture_output=True, text=True, timeout=10,
        )

    def assert_docker_arguments(self, output, tag):
        self.assertEqual(
            self.calls.read_bytes().decode().split("\0")[:-1],
            ["buildx", "build", "--platform", "linux/amd64", output, "-t", tag, "."],
        )

    def test_default_build_loads_test_image(self):
        result = self.run_build()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_docker_arguments("--load", "coppit/xeoma-test")

    def test_publish_pushes_release_image(self):
        result = self.run_build("--publish")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_docker_arguments("--push", "coppit/xeoma")

    def test_help_does_not_invoke_docker(self):
        for option in ("-h", "--help"):
            with self.subTest(option=option):
                result = self.run_build(option)
                self.assertEqual(result.returncode, 0)
                self.assertIn("Usage:", result.stdout)
                self.assertFalse(self.calls.exists())

    def test_invalid_arguments_do_not_invoke_docker(self):
        for arguments in [("--unknown",), ("--publish", "extra")]:
            with self.subTest(arguments=arguments):
                result = self.run_build(*arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Usage:", result.stderr)
                self.assertFalse(self.calls.exists())

    def test_docker_failure_is_reported(self):
        self.environment["DOCKER_EXIT_CODE"] = "42"
        for arguments in [(), ("--publish",)]:
            with self.subTest(arguments=arguments):
                self.assertEqual(self.run_build(*arguments).returncode, 42)


if __name__ == "__main__":
    unittest.main()
