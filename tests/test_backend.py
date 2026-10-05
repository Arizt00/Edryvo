"""Regression tests. Uses temporary workspaces, never the bundled demo."""
from __future__ import annotations
import base64
import hashlib
import http.cookiejar
import io
import json
import os
import platform
import random
import shutil
import sys
import tarfile
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.native import NativeCore
from backend.workspace import Workspace, ConflictError, MAX_FILE
from backend.runner import Runner
from backend.server import Application, LumenServer
from backend.ai import LocalAssistant
from tools import setup_assets


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        self.ws = Workspace(self.root, NativeCore(ROOT))
        (self.root / "hello.py").write_text('print("Hola")\n', encoding="utf-8")

    def test_read_reports_content_revision_stats(self):
        item = self.ws.read("hello.py")
        self.assertEqual(item["content"], 'print("Hola")\n')
        self.assertEqual(item["revision"], hashlib.sha256((self.root / "hello.py").read_bytes()).hexdigest())
        self.assertEqual(item["stats"]["lines"], 2)

    def test_read_parent_traversal_rejected(self):
        with self.assertRaises(PermissionError): self.ws.read("../secret.txt")

    def test_write_parent_traversal_rejected(self):
        with self.assertRaises(PermissionError): self.ws.save("../escape.txt", "no", None, create=True)
        self.assertFalse((self.root.parent / "escape.txt").exists())

    def test_absolute_external_path_rejected(self):
        with self.assertRaises(PermissionError): self.ws.resolve(str(self.root.parent / "outside"), must_exist=False)

    def test_backslash_traversal_rejected(self):
        with self.assertRaises(PermissionError): self.ws.resolve("..\\outside", must_exist=False)

    def test_symlink_rejected(self):
        try: (self.root / "link.py").symlink_to(self.root / "hello.py")
        except OSError: self.skipTest("Symbolic links are not permitted on this host")
        with self.assertRaises(PermissionError): self.ws.read("link.py")
        self.assertNotIn("link.py", self.ws.files())

    def test_binary_rejected(self):
        (self.root / "binary").write_bytes(b"ABC\x00DEF")
        with self.assertRaises(ValueError): self.ws.read("binary")

    def test_non_utf8_rejected(self):
        (self.root / "latin").write_bytes(b"\xff\xfe")
        with self.assertRaises(ValueError): self.ws.read("latin")

    def test_oversize_read_and_write_rejected(self):
        (self.root / "large").write_bytes(b"x" * (MAX_FILE + 1))
        with self.assertRaises(ValueError): self.ws.read("large")
        with self.assertRaises(ValueError): self.ws.save("new", "x" * (MAX_FILE + 1), None, create=True)

    def test_atomic_save_and_backup(self):
        first = self.ws.read("hello.py")
        saved = self.ws.save("hello.py", "print(42)\n", first["revision"])
        self.assertEqual(saved["content"], "print(42)\n")
        backups = list((self.root / ".lumen/backups").iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), first["content"])
        self.assertEqual(list(self.root.glob(".lumen-save-*")), [])

    def test_conflict_preserves_external_changes(self):
        original = self.ws.read("hello.py")
        (self.root / "hello.py").write_text("external\n")
        with self.assertRaises(ConflictError): self.ws.save("hello.py", "overwrite", original["revision"])
        self.assertEqual((self.root / "hello.py").read_text(), "external\n")

    def test_deleted_open_file_requires_explicit_recreation(self):
        original = self.ws.read("hello.py")
        (self.root / "hello.py").unlink()
        with self.assertRaises(ConflictError): self.ws.save("hello.py", "recreate", original["revision"])

    def test_new_file_and_duplicate(self):
        item = self.ws.save("nested/a.py", "pass\n", None, create=True)
        self.assertEqual(item["path"], "nested/a.py")
        with self.assertRaises(ConflictError): self.ws.save("nested/a.py", "no", None, create=True)

    def test_crlf_and_bom_roundtrip(self):
        (self.root / "windows.txt").write_bytes(b"\xef\xbb\xbfuno\r\ndos\r\n")
        item = self.ws.read("windows.txt")
        self.assertEqual(item["content"], "uno\ndos\n")
        self.assertEqual(item["newline"], "CRLF")
        self.assertTrue(item["bom"])
        self.ws.save("windows.txt", item["content"] + "tres\n", item["revision"], newline=item["newline"], bom=item["bom"])
        self.assertEqual((self.root / "windows.txt").read_bytes(), b"\xef\xbb\xbfuno\r\ndos\r\ntres\r\n")

    def test_tree_hides_private_folders_and_environment(self):
        for name in (".lumen", ".git", "node_modules"):
            (self.root / name).mkdir()
            (self.root / name / "private").write_text("no")
        (self.root / ".env").write_text("secret")
        self.assertEqual(self.ws.files(), ["hello.py"])

    def test_fuzzy_and_content_search(self):
        self.assertEqual(self.ws.search("hpy")[0]["path"], "hello.py")
        hit = self.ws.search("HOLA", content=True)[0]
        self.assertEqual((hit["path"], hit["line"]), ("hello.py", 1))
        self.assertEqual(self.ws.search("does-not-exist"), [])

    def test_check_does_not_claim_compilation(self):
        self.assertIn("not a compiler build", self.ws.check())


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = NativeCore(ROOT)
        cls.fallback = NativeCore(Path(tempfile.gettempdir()) / "lumen-missing-library")

    def test_stats_parity_unicode_empty_random(self):
        rng = random.Random(9281648)
        texts = ["", "a", "\n", "\n\n", "café 🌲\nαβ\t final", "\r\n", "\x00\x00"]
        texts += ["".join(rng.choice("abé🌲 \n\t\r") for _ in range(rng.randrange(1000))) for _ in range(200)]
        for text in texts:
            with self.subTest(length=len(text)):
                native, fallback = self.core.stats(text), self.fallback.stats(text)
                for key in ("bytes", "characters", "lines", "words"):
                    self.assertEqual(native[key], fallback[key])

    def test_fuzzy_native_matches_fallback(self):
        candidates = ["Assets/Scripts/TopDownAvatarController.cs", "src/main.cpp", "a" * 300 + "z", "README.md", "", "lumen_studio"]
        for candidate in candidates:
            for query in ("", "a", "z", "asc", "ts", "main", "README", "zzzzz"):
                with self.subTest(candidate=candidate, query=query):
                    self.assertEqual(self.core.fuzzy(query, candidate), self.fallback.fuzzy(query, candidate))

    def test_non_ascii_fuzzy_remains_available(self):
        self.assertGreaterEqual(self.core.fuzzy("á", "código_área.py"), 0)
        self.assertEqual(self.core.fuzzy("不存在", "main.cpp"), -1)

    def test_assembly_loaded_when_built_on_linux_x64(self):
        if not self.core.lib: self.skipTest("Optional native core has not been compiled")
        if sys.platform.startswith("linux") and platform.machine().lower() in ("x86_64", "amd64"):
            self.assertIn("ASM x86-64", self.core.name)
        self.assertEqual(self.core.lib.lumen_count_newlines(b"a\nb\nc\n", 6), 3)
        self.assertEqual(self.core.lib.lumen_count_newlines(b"a\nb\nc\n", 0), 0)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / "workspace/MyProject/Examples", self.root / "Examples")
        self.ws = Workspace(self.root, NativeCore(ROOT))
        self.runner = Runner()
        self.addCleanup(self.runner.shutdown)

    def wait(self, response):
        if "job" not in response: return response.get("output", "")
        job = self.runner.jobs[response["job"]]
        deadline = time.monotonic() + 25
        while not job.done and time.monotonic() < deadline: time.sleep(.025)
        self.assertTrue(job.done, "Local process did not finish in 25 seconds")
        self.assertEqual(job.code, 0, job.output)
        return job.output

    def test_execution_requires_explicit_trust(self):
        with self.assertRaises(PermissionError): self.runner.task(self.ws, "Examples/hello.py")

    def test_python_execution_and_syntax(self):
        self.ws.trusted = True
        output = self.wait(self.runner.task(self.ws, "Examples/hello.py"))
        self.assertIn("5.0", output)
        self.assertIn("syntax check passed", self.wait(self.runner.task(self.ws, "Examples/hello.py", check=True)))

    @unittest.skipUnless(shutil.which("node"), "Node.js is not installed")
    def test_javascript_execution(self):
        self.ws.trusted = True
        output = self.wait(self.runner.task(self.ws, "Examples/hello.js"))
        self.assertIn("Process exited with code 0", output)

    @unittest.skipUnless(shutil.which("gcc"), "gcc is not installed")
    def test_c_compile_and_execute(self):
        self.ws.trusted = True
        output = self.wait(self.runner.task(self.ws, "Examples/hello.c"))
        self.assertIn("Process exited with code 0", output)
        self.wait(self.runner.task(self.ws, "Examples/hello.c", check=True))

    @unittest.skipUnless(shutil.which("g++"), "g++ is not installed")
    def test_cpp_compile_and_execute(self):
        self.ws.trusted = True
        self.assertIn("50", self.wait(self.runner.task(self.ws, "Examples/hello.cpp")))

    @unittest.skipUnless(shutil.which("gcc") and sys.platform.startswith("linux") and platform.machine().lower() in ("x86_64", "amd64"), "ASM demo requires Linux x86-64 + gcc")
    def test_assembly_compile_and_execute(self):
        self.ws.trusted = True
        self.assertIn("Assembly x86-64", self.wait(self.runner.task(self.ws, "Examples/hello.S")))

    def test_stop_running_process(self):
        (self.root / "sleep.py").write_text('import time\nprint("started", flush=True)\ntime.sleep(60)\n')
        self.ws.trusted = True
        response = self.runner.task(self.ws, "sleep.py")
        job = self.runner.jobs[response["job"]]
        deadline = time.monotonic() + 5
        while "started" not in job.output and time.monotonic() < deadline: time.sleep(.025)
        job.cancel()
        while not job.done and time.monotonic() < deadline: time.sleep(.025)
        self.assertTrue(job.done)
        self.assertEqual(job.code, -1)
        self.assertIn("Task stopped", job.output)

    def test_protected_console_and_read_commands(self):
        self.assertIn("local command console", self.runner.console(self.ws, "help")["output"])
        self.assertIn(str(self.root), self.runner.console(self.ws, "pwd")["output"])
        self.assertIn("Examples/", self.runner.console(self.ws, "ls")["output"])
        self.assertEqual(self.runner.console(self.ws, "cd Examples")["cwd"], "Examples")
        self.assertIn("backend", self.runner.console(self.ws, "stats Examples/hello.py")["output"])
        self.assertTrue(self.runner.console(self.ws, "clear")["clear"])
        with self.assertRaises(ValueError): self.runner.console(self.ws, "echo arbitrary")
        with self.assertRaises(PermissionError): self.runner.console(self.ws, "cd ..")

    def test_shell_requires_both_flags_and_trust(self):
        runner = Runner(allow_shell=True)
        with self.assertRaises(ValueError): runner.console(self.ws, "echo LUMEN")
        self.ws.trusted = True
        response = runner.console(self.ws, "echo LUMEN")
        job = runner.jobs[response["job"]]
        deadline = time.monotonic() + 5
        while not job.done and time.monotonic() < deadline: time.sleep(.025)
        self.assertEqual(job.code, 0)
        self.assertIn("LUMEN", job.output)
        runner.shutdown()

    def test_csharp_has_no_fake_unity_executor(self):
        (self.root / "test.cs").write_text("class Example {}")
        self.ws.trusted = True
        with self.assertRaisesRegex(ValueError, "Unity"): self.runner.task(self.ws, "test.cs")


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        (root / "test.txt").write_text("original\n")
        cls.app = Application(ROOT, root, data_dir=Path(cls.temp.name)/"settings")
        cls.server = LumenServer(0, cls.app)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.app.features.shutdown()
        cls.app.runner.shutdown()
        cls.server.shutdown()
        cls.server.server_close()
        cls.temp.cleanup()

    def setUp(self):
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.token = ""

    def request(self, path, body=None, headers=None):
        final = {"Origin": self.base}
        if self.token: final["X-Lumen-Token"] = self.token
        if body is not None: final["Content-Type"] = "application/json"
        if headers: final.update(headers)
        request = urllib.request.Request(self.base + path, data=None if body is None else json.dumps(body).encode(), headers=final)
        try:
            with self.opener.open(request, timeout=5) as response: return response.status, response.headers, response.read()
        except urllib.error.HTTPError as error: return error.code, error.headers, error.read()

    def login(self):
        self.assertEqual(self.request("/")[0], 200)
        status, _, data = self.request("/api/bootstrap")
        self.assertEqual(status, 200)
        self.token = json.loads(data)["token"]

    def test_requires_session_cookie(self):
        self.assertEqual(self.request("/api/bootstrap")[0], 403)

    def test_requires_csrf_token_beyond_bootstrap(self):
        self.login(); self.token = ""
        self.assertEqual(self.request("/api/tree")[0], 403)

    def test_rejects_foreign_origin_and_host(self):
        self.login()
        self.assertEqual(self.request("/api/tree", headers={"Origin": "http://evil.invalid"})[0], 403)
        self.assertEqual(self.request("/api/tree", headers={"Host": "evil.invalid"})[0], 403)
        self.assertEqual(self.request("/api/tree", headers={"Sec-Fetch-Site": "cross-site"})[0], 403)

    def test_static_serving_mime_and_security_headers(self):
        status, headers, data = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn("ZÉNIT".encode('utf-8'), data)
        self.assertIn("SameSite=Strict", headers["Set-Cookie"])
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("text/javascript", self.request("/src/app.js")[1]["Content-Type"])
        self.assertEqual(self.request("/../backend/server.py")[0], 404)

    def test_actual_read_save_and_conflict_over_http(self):
        self.login()
        status, _, data = self.request("/api/file?path=test.txt")
        self.assertEqual(status, 200)
        item = json.loads(data)
        status, _, saved = self.request("/api/save", {"path": "test.txt", "content": "saved\n", "revision": item["revision"]})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(saved)["content"], "saved\n")
        self.assertEqual(self.request("/api/save", {"path": "test.txt", "content": "bad", "revision": "wrong"})[0], 409)
        self.assertEqual(self.request("/api/file?path=../outside")[0], 403)

    def test_api_validation_and_nonexistent_resources(self):
        self.login()
        self.assertEqual(self.request("/api/unknown")[0], 404)
        self.assertEqual(self.request("/api/save", [1, 2, 3])[0], 400)
        self.assertEqual(self.request("/api/job?id=missing")[0], 404)
        self.assertEqual(self.request("/api/stats", {"content": "bosque\n"})[0], 200)

    def test_trust_and_state(self):
        self.login()
        self.assertEqual(self.request("/api/trust", {"trusted": True})[0], 200)
        self.assertTrue(json.loads(self.request("/api/state")[2])["trusted"])
        self.request("/api/trust", {"trusted": False})


class AssistantTests(unittest.TestCase):
    def test_only_loopback_urls(self):
        for url in ("http://localhost:11434", "http://127.0.0.1:11434/", "http://[::1]:11434"):
            self.assertTrue(LocalAssistant.validate_url(url).startswith("http://"))
        for url in ("https://localhost", "http://example.com", "http://127.0.0.1.evil.com", "http://a:b@localhost", "http://localhost/api/chat", "http://localhost/?x=1"):
            with self.subTest(url=url):
                with self.assertRaises(ValueError): LocalAssistant.validate_url(url)

    def test_disconnected_never_fakes_response(self):
        with self.assertRaisesRegex(ValueError, "Conecta"): LocalAssistant().chat("help", "x.py", "pass")

    def test_adapter_contract_with_explicit_mock(self):
        ai = LocalAssistant()
        with patch.object(ai, "_request", return_value={"models": [{"name": "mock-model"}]}):
            self.assertTrue(ai.connect("http://127.0.0.1:11434", "mock-model")["connected"])
        with patch.object(ai, "_request", return_value={"message": {"content": "MOCK, not a real inference"}}) as request:
            response = ai.chat("Explica", "x.py", "print(1)")
            self.assertEqual(response["text"], "MOCK, not a real inference")
            self.assertFalse(request.call_args.args[1]["stream"])
            self.assertIn("print(1)", request.call_args.args[1]["messages"][1]["content"])


class DependencyInstallerTests(unittest.TestCase):
    def archive(self, names):
        blob = io.BytesIO()
        with tarfile.open(fileobj=blob, mode="w:gz") as archive:
            for name, content in names.items():
                raw = content.encode()
                item = tarfile.TarInfo(name); item.size = len(raw)
                archive.addfile(item, io.BytesIO(raw))
        return blob.getvalue()

    def install_mock(self, tarball, *, digest=None):
        integrity = digest or base64.b64encode(hashlib.sha512(tarball).digest()).decode()
        metadata = {"name": "babylonjs", "version": setup_assets.PACKAGES["babylon"][1], "dist": {
            "tarball": "https://registry.npmjs.org/babylonjs/-/mock.tgz", "integrity": "sha512-" + integrity}}
        with patch.object(setup_assets, "fetch", side_effect=[json.dumps(metadata).encode(), tarball]):
            setup_assets.install("babylon")

    def test_integrity_allowlist_and_license_copy(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(setup_assets, "VENDOR", Path(folder)):
            self.install_mock(self.archive({"package/babylon.js": "/* mock fixture */", "package/LICENSE.md": "fixture license", "package/unrelated.txt": "ignore"}))
            self.assertTrue((Path(folder) / "babylon/babylon.js").is_file())
            self.assertTrue((Path(folder) / "babylon/LICENSE.md").is_file())
            self.assertFalse((Path(folder) / "babylon/unrelated.txt").exists())

    def test_bad_integrity_rejected_before_extracting(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(setup_assets, "VENDOR", Path(folder)):
            with self.assertRaisesRegex(ValueError, "SHA-512"):
                self.install_mock(self.archive({"package/babylon.js": "mock"}), digest="invalid")
            self.assertFalse((Path(folder) / "babylon").exists())

    def test_archive_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(setup_assets, "VENDOR", Path(folder)):
            with self.assertRaisesRegex(ValueError, "ruta no segura"):
                self.install_mock(self.archive({"package/babylon.js": "mock", "../../escape": "no"}))
            self.assertFalse((Path(folder) / "babylon").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
