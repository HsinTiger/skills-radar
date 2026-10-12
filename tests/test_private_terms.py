import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

import check_privacy  # noqa: E402
from private_terms import ENV_VAR, PrivateTermsError, load_private_terms, terms_path  # noqa: E402


# 只用假的字；真的清單只在 owner 的機器上
FAKE = {"banned": ["ExampleCorp", r"\b9999\.TW\b"], "redact": [["ExampleCorp|OtherFab", "某 IC 廠"]]}


def write_terms(folder, data):
    path = Path(folder) / "private_terms.json"
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return path


class LoadPrivateTermsTests(unittest.TestCase):
    def test_banned_is_case_sensitive_and_redact_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            banned, redact = load_private_terms(write_terms(tmp, FAKE))
        self.assertTrue(banned[0].search("built by ExampleCorp"))
        self.assertIsNone(banned[0].search("built by examplecorp"))
        pattern, replacement = redact[0]
        self.assertEqual(pattern.sub(replacement, "examplecorp and OTHERFAB"), "某 IC 廠 and 某 IC 廠")

    def test_env_var_picks_the_file(self):
        with patch.dict(os.environ, {ENV_VAR: "/elsewhere/terms.json"}):
            self.assertEqual(terms_path(), Path("/elsewhere/terms.json"))

    def test_missing_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PrivateTermsError) as ctx:
                load_private_terms(Path(tmp) / "absent.json")
        self.assertIn("not found", str(ctx.exception))

    def test_unusable_lists_fail_closed_without_echoing_a_term(self):
        cases = {
            "not json": "{ExampleCorp",
            "not an object": ["ExampleCorp"],
            "empty banned": {"banned": [], "redact": FAKE["redact"]},
            "empty redact": {"banned": ["ExampleCorp"], "redact": []},
            "blank pattern": {"banned": ["ExampleCorp", ""], "redact": FAKE["redact"]},
            "bad banned regex": {"banned": ["(ExampleCorp"], "redact": FAKE["redact"]},
            "bad redact regex": {"banned": ["ExampleCorp"], "redact": [["(ExampleCorp", "x"]]},
            "blank replacement": {"banned": ["ExampleCorp"], "redact": [["ExampleCorp", ""]]},
        }
        for label, data in cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(PrivateTermsError) as ctx:
                    load_private_terms(write_terms(tmp, data))
                self.assertNotIn("ExampleCorp", str(ctx.exception))


class CheckPrivacyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.repo = self.tmp / "repo"
        (self.repo / "docs").mkdir(parents=True)
        (self.repo / "corpus" / "wiki").mkdir(parents=True)
        env = patch.dict(os.environ, {ENV_VAR: str(write_terms(self.tmp, FAKE))})
        env.start()
        self.addCleanup(env.stop)

    def run_main(self):
        out = io.StringIO()
        with patch.object(check_privacy, "ROOT", str(self.repo)), redirect_stdout(out):
            rc = check_privacy.main()
        return rc, out.getvalue()

    def test_hit_reports_place_and_rule_number_but_not_the_text(self):
        (self.repo / "docs" / "index.html").write_text("ok\nmade by ExampleCorp\n", encoding="utf-8")
        (self.repo / "README.md").write_text("ticker 9999.TW\n", encoding="utf-8")
        rc, out = self.run_main()
        self.assertEqual(rc, 1)
        self.assertIn("docs/index.html:2 規則 #1", out)
        self.assertIn("README.md:1 規則 #2", out)
        self.assertNotIn("ExampleCorp", out)
        self.assertNotIn("9999", out)

    def test_third_party_corpus_is_not_scanned_on_any_os(self):
        (self.repo / "corpus" / "wiki" / "page.md").write_text("ExampleCorp\n", encoding="utf-8")
        (self.repo / "docs" / "index.html").write_text("clean\n", encoding="utf-8")
        rc, out = self.run_main()
        self.assertEqual(rc, 0)
        self.assertIn("通過", out)

    def test_missing_list_stops_instead_of_passing(self):
        with patch.dict(os.environ, {ENV_VAR: str(self.tmp / "absent.json")}):
            rc, out = self.run_main()
        self.assertEqual(rc, 2)
        self.assertIn("STOP", out)
        self.assertNotIn("通過", out)


class BuildSiteTermsTests(unittest.TestCase):
    def test_build_site_reads_vendor_names_from_the_local_list(self):
        source = (ROOT / "bin" / "build_site.py").read_text(encoding="utf-8")
        self.assertNotIn("VENDOR_REDACT = [", source)
        self.assertIn("load_private_terms()", source)


@unittest.skipUnless(terms_path().is_file(), "the private term list only exists on the owner's machine")
class OwnerMachineGuardTests(unittest.TestCase):
    def test_code_templates_and_docs_hold_no_private_term(self):
        banned, redact = load_private_terms()
        patterns = banned + [pattern for pattern, _ in redact]
        files = [path for folder in ("bin", "tests", "index")
                 for path in (ROOT / folder).rglob("*")
                 if path.is_file() and "__pycache__" not in path.parts]
        files += sorted(ROOT.glob("*.md"))
        hits = []
        for path in files:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for number, pattern in enumerate(patterns, 1):
                if pattern.search(text):
                    # 只回報位置和規則編號，失敗訊息裡不帶原字
                    hits.append(f"{path.relative_to(ROOT).as_posix()} 規則 #{number}")
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
