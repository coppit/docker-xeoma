"""Isolated filesystem and local HTTP fixtures for the startup scripts."""

from functools import partial
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[1]


def redirect(source, replacements):
    """Replace paths in one pass so replacement paths are never rewritten."""
    pattern = "|".join(re.escape(path) for path in sorted(replacements, key=len, reverse=True))
    return re.sub(r"(?<![\w/.-])(?:" + pattern + ")", lambda match: str(replacements[match.group()]), source)


class FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.requests.append(self.path)
        status, body = self.server.responses.get(self.path, (404, b"not found"))
        self.send_response(status)
        self.send_header("Content-Length", str(self.server.content_lengths.get(self.path, len(body))))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class XeomaFixture(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="xeoma-runtime-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.config = self.root / "config"
        self.downloads = self.config / "downloads"
        self.install = self.root / "installed"
        self.bin = self.root / "bin"
        self.archive = self.root / "archive"
        for path in (self.config, self.bin, self.archive):
            path.mkdir()
        self.merged = self.root / "envvars.merged"
        self.binary = self.bin / "xeoma"
        self.breadcrumb = self.install / "last_installed_version.txt"
        self.calls = self.root / "calls"
        self.calls.mkdir()
        self.environment = {
            "PATH": f"{self.bin}{os.pathsep}{os.defpath}",
            "HOME": str(self.root),
            "TMPDIR": str(self.root),
            "CALLS": str(self.calls),
            "NO_PROXY": "127.0.0.1",
        }
        self.set_version("latest")

    def start_server(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        self.server.responses = {}
        self.server.content_lengths = {}
        self.server.requests = []
        thread = threading.Thread(target=partial(self.server.serve_forever, poll_interval=0.01), daemon=True)
        thread.start()

        def stop():
            self.server.shutdown()
            thread.join(timeout=5)
            self.server.server_close()

        self.addCleanup(stop)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        source = (ROOT / "install_xeoma.py").read_text()
        self.installer = self.root / "install.py"
        self.installer.write_text(redirect(source, {
            "/config/downloads": self.downloads,
            "/files/xeoma": self.install,
            "/usr/bin/xeoma": self.binary,
            "/etc/envvars.merged": self.merged,
            "http://felenasoft.com/xeoma/downloads/version3.xml": f"{self.url}/version.xml",
            "https://felenasoft.com/xeoma/downloads/": f"{self.url}/versions/",
        }))

    def set_version(self, version):
        self.merged.write_text(f"export VERSION={shlex.quote(version)}\n")

    def serve(self, path, body, status=200, content_length=None):
        self.server.responses[path] = (status, body)
        self.server.content_lengths[path] = len(body) if content_length is None else content_length

    def metadata(self, stable="25.8.22", beta=None, stable_path="/stable.tgz", beta_path="/beta.tgz"):
        def entry(version, path):
            return f'<version>{version}</version><platform name="linux64"><url>{self.url}{path}</url></platform>'

        xml = "<root>" + entry(stable, stable_path)
        if beta:
            xml += "<beta>" + entry(beta, beta_path) + "</beta>"
        self.serve("/version.xml", (xml + "</root>").encode())

    def archive_bytes(self, version="stable"):
        # A tiny executable stands in for the proprietary binary; tar extraction is real.
        payload = f"#!/bin/sh\necho {shlex.quote(version)}\n".encode()
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            member = tarfile.TarInfo("xeoma.app")
            member.mode = 0o755
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
        return buffer.getvalue()

    def run_command(self, *command):
        return subprocess.run(
            command, env=self.environment, cwd=self.root, capture_output=True, text=True, timeout=20
        )

    def run_installer(self):
        return self.run_command(sys.executable, "-B", str(self.installer))

    def assert_installed(self, archive, version):
        self.assertTrue(self.binary.is_symlink())
        self.assertEqual(self.binary.resolve(), self.install / "xeoma.app")
        self.assertEqual(self.breadcrumb.read_text(), hashlib.md5(archive).hexdigest())
        self.assertTrue(os.access(self.binary, os.X_OK))
        result = self.run_command("/bin/sh", str(self.binary))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), version)

    def mock_command(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/bash\n" + body)
        path.chmod(0o755)
        return path
