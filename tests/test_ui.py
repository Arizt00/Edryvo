#!/usr/bin/env python3
"""UI smoke test against a real Python server and a disposable project.

Dependency: pip install playwright; playwright install chromium.
Default transport is normal browser navigation. --transport bridge is provided
for restricted renderers, and explicitly does not verify browser HTTP loading.
"""
from __future__ import annotations
import argparse
import json
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.server import Application, LumenServer
from ui_harness import prepare


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=("direct", "bridge"), default="direct")
    parser.add_argument("--chromium", help="Optional browser executable path")
    parser.add_argument("--screenshots", type=Path, default=ROOT / "reports/screenshots")
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright, expect
    args.screenshots.mkdir(parents=True, exist_ok=True)
    checks = []
    def passed(message):
        checks.append(message)
        print("PASS", message, flush=True)
    with tempfile.TemporaryDirectory(prefix="lumen-ui-") as folder:
        workspace = Path(folder) / "MyProject"
        shutil.copytree(ROOT / "workspace/MyProject", workspace, ignore=shutil.ignore_patterns(".lumen"))
        app = Application(ROOT, workspace, data_dir=Path(folder)/"settings")
        server = LumenServer(0, app)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with sync_playwright() as playwright:
                opts = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
                if args.chromium: opts["executable_path"] = args.chromium
                browser = playwright.chromium.launch(**opts)
                page = browser.new_page(viewport={"width": 1648, "height": 928}, device_scale_factor=1)
                page.set_default_timeout(6500)
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                if args.transport == "bridge": prepare(page, base)
                else: page.goto(base)
                page.wait_for_function("window.lumen?.platformReady", timeout=20000)
                passed("Application boot and real workspace bootstrap")
                expect(page.locator("#file-tabs .file-tab")).to_have_count(3)
                assert page.evaluate("lumen.activeFile") == "Assets/Scripts/TopDownAvatarController.cs"
                passed("Three real file tabs; controller is active")
                for key, theme in (("1", "day"), ("2", "dark"), ("3", "forest")):
                    page.keyboard.press("Control+Alt+" + key)
                    page.wait_for_function("lumen.theme === '" + theme + "'")
                    page.wait_for_timeout(300)
                    page.screenshot(path=str(args.screenshots / (theme + ".png")))
                passed("Three theme hotkeys and application screenshots")
                boxes = {name: page.locator(selector).bounding_box() for name, selector in {
                    "editor": "#editor-panel", "assistant": "#assistant-panel", "tree": "#project-panel", "terminal": "#terminal-panel"}.items()}
                assert abs(boxes["editor"]["x"] - 404) < 1
                assert 418 < boxes["assistant"]["width"] < 425
                assert page.evaluate("document.documentElement.scrollWidth === innerWidth")
                passed("Lumen reference geometry at 1648 x 928; no horizontal page overflow")
                page.locator('[data-tab="Assets/Scripts/Player.cs"]').click()
                page.wait_for_function("lumen.activeFile.endsWith('/Player.cs')")
                passed("File tab switching")
                page.keyboard.press("Control+p")
                page.locator("#palette-input").fill("TopDownAvatar")
                expect(page.locator(".palette-result").first).to_contain_text("TopDownAvatarController.cs")
                page.keyboard.press("Enter")
                page.wait_for_function("lumen.activeFile.endsWith('/TopDownAvatarController.cs')")
                passed("Fuzzy file search opens an existing document")
                page.keyboard.press("Control+Shift+f")
                page.locator("#project-search").fill("MovePosition")
                expect(page.locator("#project-search-results")).to_contain_text("TopDownAvatarController.cs")
                page.locator("#project-search-results .search-result").first.click()
                passed("Content search returns actual file and line")
                page.locator('.rail-item[data-view="explorer"]').click()
                page.keyboard.press("Control+Shift+p")
                page.locator("#palette-input").fill(">Nuevo archivo")
                expect(page.locator(".palette-result").first).to_contain_text("Nuevo archivo")
                page.keyboard.press("Enter")
                page.locator("#new-file-name").fill("Examples/qa_temp.py")
                page.locator('#new-file-form button[type="submit"]').click()
                page.wait_for_function("lumen.activeFile === 'Examples/qa_temp.py'")
                assert (workspace / "Examples/qa_temp.py").is_file()
                passed("New file form creates a real file without page reload")
                if page.evaluate("lumen.editorKind") == "base":
                    content = 'print("LUMEN_UI_OK")\n'
                    page.locator(".code-input").fill(content)
                    expect(page.locator('.file-tab.active .dirty-dot')).to_have_count(1)
                    page.keyboard.press("Control+s")
                    expect(page.locator('.file-tab.active .dirty-dot')).to_have_count(0)
                    assert (workspace / "Examples/qa_temp.py").read_text() == content
                    passed("Base editor input, dirty state, Ctrl+S and real disk persistence")
                    page.locator(".code-input").focus()
                    page.keyboard.press("Control+f")
                    page.locator('.editor-find input').fill("LUMEN_UI_OK")
                    expect(page.locator('.editor-find')).to_be_visible()
                    page.locator('.find-close').click()
                    passed("In-file text search")
                else:
                    raise RuntimeError("This authored regression suite targets the built-in editor. Test Monaco separately.")
                page.keyboard.press("F5")
                expect(page.locator("#modal-title")).to_contain_text("Confías")
                assert not app.workspace.trusted
                page.locator("#confirm-yes").click()
                expect(page.locator("#terminal-log")).to_contain_text("LUMEN_UI_OK")
                expect(page.locator("#terminal-log")).to_contain_text("Process exited with code 0")
                assert app.workspace.trusted
                passed("Trust prompt and real Python task execution")
                page.locator("#terminal-input").fill("help")
                page.locator("#terminal-input").press("Enter")
                expect(page.locator("#terminal-log")).to_contain_text("local command console")
                page.locator("#terminal-input").fill("cd Examples")
                page.locator("#terminal-input").press("Enter")
                expect(page.locator("#prompt-path")).to_contain_text("/Examples")
                passed("Console submit and workspace-scoped directory changes")
                page.keyboard.press("Control+j")
                assert not page.locator("#terminal-panel").is_visible()
                page.keyboard.press("Control+j")
                page.keyboard.press("Control+b")
                assert not page.locator("#project-panel").is_visible()
                page.keyboard.press("Control+b")
                passed("Panel visibility shortcuts")
                previous = page.locator("#project-panel").bounding_box()["width"]
                page.locator("#tree-resizer").focus()
                page.keyboard.press("ArrowRight")
                assert page.locator("#project-panel").bounding_box()["width"] >= previous + 9
                passed("Accessible keyboard pane resizing")
                page.keyboard.press("Control+,")
                page.locator('[data-setting-category="editor"]').click()
                page.locator("#pref-editor-minimap").uncheck()
                assert not page.locator(".code-minimap").is_visible()
                page.locator("#pref-editor-minimap").check()
                page.keyboard.press("Escape")
                page.keyboard.press("Control+Alt+l")
                page.locator("#layout-reset-all").click()
                page.keyboard.press("Escape")
                assert page.locator(".code-minimap").is_visible()
                passed("Editor preferences and independent layout reset")
                page.locator('[data-ai-action="explain"]').click()
                expect(page.locator("#ai-input")).not_to_be_empty()
                page.locator(".send-button").click()
                expect(page.locator("#settings-content .provider-grid")).to_be_visible()
                assert not app.features.ai.prefs.get("ai.model")
                page.keyboard.press("Escape")
                passed("Unconnected AI opens settings rather than fabricating a response")
                page.set_viewport_size({"width": 1366, "height": 768})
                page.wait_for_timeout(200)
                assert page.evaluate("document.documentElement.scrollWidth === innerWidth")
                page.screenshot(path=str(args.screenshots / "responsive-1366.png"))
                page.set_viewport_size({"width": 1100, "height": 768})
                page.wait_for_timeout(200)
                assert page.evaluate("document.documentElement.scrollWidth === innerWidth")
                passed("Responsive layout at 1366 and 1100 px without page overflow")
                assert errors == [], errors
                passed("Zero unhandled browser JavaScript errors")
                browser.close()
                result = {"transport": args.transport, "checks": len(checks), "passed": checks, "errors": errors,
                    "geometry": boxes, "native": app.native.name, "limitations": ["Base editor tested", "Babylon engine not executed by this suite", "Bridge mode is not a browser transport / CSP test"]}
                (args.screenshots / "ui-results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
                print(json.dumps({"passed": len(checks), "errors": errors, "transport": args.transport}), flush=True)
        finally:
            app.features.shutdown()
            app.runner.shutdown()
            server.shutdown()
            server.server_close()


if __name__ == "__main__": main()
