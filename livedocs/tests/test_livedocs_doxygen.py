#!/usr/bin/env python3
"""Doxygen 静的サーブとリンク変換の純関数テスト。"""

import os
import sys
import tempfile
import unittest

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
sys.path.insert(0, BIN_DIR)

from livedocs_doxygen_hook import (  # noqa: E402
    dependency_page_template_to_livedocs,
    doxygen_page_url_to_livedocs,
    find_doxygen_root,
    guess_doxygen_content_type,
    is_doxygen_link_enabled,
    is_dependency_data_js_url,
    is_doxygen_url_path,
    resolve_doxygen_file,
    rewrite_dependency_data_for_livedocs,
    serve_doxygen,
    url_path_to_rel_parts,
)
from stage_livedocs import rewrite_doxygen_livedocs_links  # noqa: E402


class RewriteDoxygenLivedocsLinksTest(unittest.TestCase):
    def test_markdown_relative_link(self):
        text = "[cplat](../../../doxygen/cplat_public/index.html)"
        self.assertEqual(
            rewrite_doxygen_livedocs_links(text),
            "[cplat](/doxygen/cplat_public/index.html)",
        )

    def test_html_href_and_anchor(self):
        text = '<a href="../../../../doxygen/porter_internal/dependency/index.html#top">'
        self.assertEqual(
            rewrite_doxygen_livedocs_links(text),
            '<a href="/doxygen/porter_internal/dependency/index.html#top">',
        )

    def test_skips_fences_and_doxyfw_path(self):
        text = "\n".join(
            [
                "```text",
                "../../../doxygen/cplat_public/index.html",
                "```",
                "[usage](../../../framework/doxyfw/docs/makefile-usage.md)",
            ]
        )
        self.assertEqual(rewrite_doxygen_livedocs_links(text), text)


class DoxygenPageUrlTest(unittest.TestCase):
    def test_workspace_relative(self):
        self.assertEqual(
            doxygen_page_url_to_livedocs("pages/doxygen/calc_public/calc_8h.html"),
            "/doxygen/calc_public/calc_8h.html",
        )

    def test_already_livedocs_url(self):
        self.assertEqual(
            doxygen_page_url_to_livedocs("/doxygen/calc_public/calc_8h.html"),
            "/doxygen/calc_public/calc_8h.html",
        )

    def test_rejects_unrelated(self):
        self.assertIsNone(doxygen_page_url_to_livedocs("docs/README.md"))
        self.assertIsNone(doxygen_page_url_to_livedocs(""))
        self.assertIsNone(doxygen_page_url_to_livedocs(None))

    def test_windows_separators(self):
        self.assertEqual(
            doxygen_page_url_to_livedocs("pages\\doxygen\\calc_public\\calc_8h.html"),
            "/doxygen/calc_public/calc_8h.html",
        )


class DependencyPageLivedocsUrlTest(unittest.TestCase):
    def test_converts_published_template(self):
        self.assertEqual(
            dependency_page_template_to_livedocs(
                "../../../{variant}/html/c-platform/doxybook2_internal"
            ),
            "/c-platform/doxybook2_internal",
        )
        self.assertEqual(
            dependency_page_template_to_livedocs(
                "../../../{variant}/html/日本語/app docs/"
            ),
            "/日本語/app docs",
        )

    def test_rejects_unrecognized_or_unsafe_template(self):
        for value in (
            "",
            "/{variant}/html/calc/doxybook2",
            "../../../{variant}/html/../secret",
            "../../../{variant}/html/calc//doxybook2",
            "../../../{variant}/html/calc/doxybook2?x=1",
        ):
            self.assertIsNone(dependency_page_template_to_livedocs(value))

    def test_rewrites_dependency_data_js(self):
        source = (
            'window.DoxyfwDependencyData = {"pageUrlTemplate": '
            '"../../../{variant}/html/calc/doxybook2", "functions": []};\n'
        ).encode("utf-8")
        rewritten = rewrite_dependency_data_for_livedocs(source).decode("utf-8")
        self.assertIn('"livedocsPageUrlTemplate": "/calc/doxybook2"', rewritten)
        self.assertIn('"pageUrlTemplate": "../../../{variant}/html/calc/doxybook2"', rewritten)

    def test_keeps_malformed_and_unrecognized_data(self):
        samples = (
            b"not javascript",
            b"window.DoxyfwDependencyData = {broken};\n",
            b'window.DoxyfwDependencyData = {"pageUrlTemplate": ""};\n',
            b"\xff",
        )
        for source in samples:
            self.assertEqual(rewrite_dependency_data_for_livedocs(source), source)

    def test_identifies_dependency_data_url_only(self):
        self.assertTrue(
            is_dependency_data_js_url(
                "/doxygen/calc_internal/dependency/dependency-data.js"
            )
        )
        self.assertFalse(is_dependency_data_js_url("/doxygen/calc_internal/dependency/index.html"))
        self.assertFalse(is_dependency_data_js_url("/doxygen/dependency-data.js"))


class DoxygenLinkEnableTest(unittest.TestCase):
    def test_default_true(self):
        self.assertTrue(is_doxygen_link_enabled({}))
        self.assertTrue(is_doxygen_link_enabled({"doxygenLinkEnable": ""}))

    def test_false(self):
        self.assertFalse(is_doxygen_link_enabled({"doxygenLinkEnable": "false"}))


class ResolveDoxygenFileTest(unittest.TestCase):
    def test_url_prefix(self):
        self.assertTrue(is_doxygen_url_path("/doxygen"))
        self.assertTrue(is_doxygen_url_path("/doxygen/"))
        self.assertTrue(is_doxygen_url_path("/doxygen/a.html"))
        self.assertFalse(is_doxygen_url_path("/c-platform/"))
        self.assertFalse(is_doxygen_url_path("/doxygen-sample/"))
        self.assertFalse(is_doxygen_url_path("/doxygen/../site/index.html"))

    def test_rel_parts_index_and_file(self):
        self.assertEqual(url_path_to_rel_parts("/doxygen/"), ("index.html",))
        self.assertEqual(
            url_path_to_rel_parts("/doxygen/calc_public/calc_8h.html"),
            ("calc_public", "calc_8h.html"),
        )
        self.assertEqual(
            url_path_to_rel_parts("/doxygen/calc_public/"),
            ("calc_public", "index.html"),
        )
        self.assertIsNone(url_path_to_rel_parts("/doxygen"))
        self.assertIsNone(url_path_to_rel_parts("/other/"))

    def test_rel_parts_rejects_traversal(self):
        self.assertIsNone(url_path_to_rel_parts("/doxygen/foo/../../../etc/passwd"))
        self.assertIsNone(url_path_to_rel_parts("/doxygen/../secret.html"))
        self.assertEqual(
            url_path_to_rel_parts("/doxygen/foo/../bar.html"),
            ("bar.html",),
        )

    def test_resolve_under_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            target_dir = os.path.join(tmp, "calc_public")
            os.makedirs(target_dir)
            target = os.path.join(target_dir, "calc_8h.html")
            with open(target, "wb") as handle:
                handle.write(b"ok")
            resolved = resolve_doxygen_file(tmp, "/doxygen/calc_public/calc_8h.html")
            self.assertEqual(resolved, os.path.abspath(target))

    def test_resolve_stays_in_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside = os.path.abspath(os.path.join(tmp, os.pardir, "secret.html"))
            self.assertIsNone(resolve_doxygen_file(tmp, "/doxygen/../secret.html"))
            resolved = resolve_doxygen_file(tmp, "/doxygen/foo/../../../secret.html")
            if resolved is not None:
                self.assertTrue(
                    os.path.normcase(os.path.abspath(resolved)).startswith(
                        os.path.normcase(os.path.abspath(tmp)) + os.sep
                    )
                )
                self.assertNotEqual(os.path.abspath(resolved), outside)


class ServeDoxygenTest(unittest.TestCase):
    def _start_response(self):
        captured = {}

        def start_response(status, headers):
            captured["status"] = status
            captured["headers"] = dict(headers)

        return captured, start_response

    def test_serves_file_and_js_mime(self):
        with tempfile.TemporaryDirectory() as tmp:
            dep = os.path.join(tmp, "porter_internal", "dependency")
            os.makedirs(dep)
            html_path = os.path.join(dep, "index.html")
            js_path = os.path.join(dep, "dependency-data.js")
            with open(html_path, "wb") as handle:
                handle.write(b"<html>doxygen</html>")
            with open(js_path, "wb") as handle:
                handle.write(b"window.DoxyfwDependencyData = {};")

            captured, start_response = self._start_response()
            result = serve_doxygen(tmp, "/doxygen/porter_internal/dependency/", {}, start_response)
            try:
                body = b"".join(result)
            finally:
                close = getattr(result, "close", None)
                if close is not None:
                    close()
            self.assertTrue(captured["status"].startswith("200"))
            self.assertIn("text/html", captured["headers"]["Content-Type"])
            self.assertEqual(body, b"<html>doxygen</html>")

            captured, start_response = self._start_response()
            result = serve_doxygen(
                tmp,
                "/doxygen/porter_internal/dependency/dependency-data.js",
                {},
                start_response,
            )
            try:
                body = b"".join(result)
            finally:
                close = getattr(result, "close", None)
                if close is not None:
                    close()
            self.assertTrue(captured["status"].startswith("200"))
            self.assertEqual(captured["headers"]["Content-Type"], "application/javascript")
            self.assertIn(b"DoxyfwDependencyData", body)

    def test_rewrites_dependency_page_template_in_js_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            dep = os.path.join(tmp, "calc_internal", "dependency")
            os.makedirs(dep)
            js_path = os.path.join(dep, "dependency-data.js")
            with open(js_path, "wb") as handle:
                handle.write(
                    b'window.DoxyfwDependencyData = {"pageUrlTemplate": '
                    b'"../../../{variant}/html/calc/doxybook2_internal"};\n'
                )

            captured, start_response = self._start_response()
            result = serve_doxygen(
                tmp,
                "/doxygen/calc_internal/dependency/dependency-data.js",
                {},
                start_response,
            )
            body = b"".join(result)
            self.assertEqual(captured["status"], "200 OK")
            self.assertEqual(captured["headers"]["Content-Type"], "application/javascript")
            self.assertEqual(int(captured["headers"]["Content-Length"]), len(body))
            self.assertIn(b'"livedocsPageUrlTemplate": "/calc/doxybook2_internal"', body)

    def test_redirects_directory_and_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "calc_public"))
            with open(os.path.join(tmp, "calc_public", "index.html"), "wb") as handle:
                handle.write(b"idx")
            captured, start_response = self._start_response()
            serve_doxygen(tmp, "/doxygen/calc_public", {}, start_response)
            self.assertTrue(captured["status"].startswith("302"))
            self.assertEqual(captured["headers"]["Location"], "/doxygen/calc_public/")

            captured, start_response = self._start_response()
            serve_doxygen(tmp, "/doxygen", {}, start_response)
            self.assertTrue(captured["status"].startswith("302"))
            self.assertEqual(captured["headers"]["Location"], "/doxygen/")

    def test_missing_is_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            captured, start_response = self._start_response()
            body = b"".join(serve_doxygen(tmp, "/doxygen/missing.html", {}, start_response))
            self.assertTrue(captured["status"].startswith("404"))
            self.assertEqual(body, b"404 Not Found")

    def test_guess_js(self):
        self.assertEqual(guess_doxygen_content_type("x.js"), "application/javascript")


class FindDoxygenRootTest(unittest.TestCase):
    def test_missing_and_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(find_doxygen_root(tmp))
            os.makedirs(os.path.join(tmp, "pages", "doxygen"))
            found = find_doxygen_root(tmp)
            self.assertEqual(found, os.path.abspath(os.path.join(tmp, "pages", "doxygen")))


if __name__ == "__main__":
    unittest.main()
