#!/usr/bin/env python3
"""Git 単一ページ リンクの解決に関する単体テスト。"""

import os
import subprocess
import sys
import tempfile
import unittest

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
sys.path.insert(0, BIN_DIR)

from git_link import (  # noqa: E402
    GitLinkResolver,
    build_blob_url,
    detect_provider,
    normalize_remote_url,
    parse_host_provider_map,
)


class NormalizeRemoteUrlTest(unittest.TestCase):
    """``get_file_git_url.sh`` の normalize_remote_url と同じ結果になること。"""

    def test_https(self):
        self.assertEqual(
            normalize_remote_url("https://github.com/owner/repo.git"),
            ("https://github.com/owner/repo", "github.com"),
        )

    def test_http_keeps_scheme(self):
        self.assertEqual(
            normalize_remote_url("http://git.example.com/owner/repo/"),
            ("http://git.example.com/owner/repo", "git.example.com"),
        )

    def test_ssh_removes_user_and_port(self):
        self.assertEqual(
            normalize_remote_url("ssh://git@git.example.com:2222/owner/repo.git"),
            ("https://git.example.com/owner/repo", "git.example.com"),
        )

    def test_scp_like(self):
        self.assertEqual(
            normalize_remote_url("git@github.com:owner/repo.git"),
            ("https://github.com/owner/repo", "github.com"),
        )

    def test_context_path_is_kept(self):
        self.assertEqual(
            normalize_remote_url("https://host.example.com/gitbucket/owner/repo.git"),
            ("https://host.example.com/gitbucket/owner/repo", "host.example.com"),
        )

    def test_unsupported(self):
        self.assertEqual(normalize_remote_url("/var/repos/local.git"), (None, None))
        self.assertEqual(normalize_remote_url(""), (None, None))


class DetectProviderTest(unittest.TestCase):
    """host からの provider 判定と、設定マッピングの優先順。"""

    def test_known_hosts(self):
        self.assertEqual(detect_provider("github.com"), ("github", None))
        self.assertEqual(detect_provider("gitlab.com"), ("gitlab", None))
        self.assertEqual(detect_provider("gitlab.example.com"), ("gitlab", None))
        self.assertEqual(detect_provider("gitbucket.example.com"), ("gitbucket", None))

    def test_unknown_host_is_generic(self):
        self.assertEqual(detect_provider("scm.example.com"), ("git", None))

    def test_mapping_wins(self):
        mapping = parse_host_provider_map("scm.example.com=gitlab")
        self.assertEqual(detect_provider("scm.example.com", mapping), ("gitlab", None))

    def test_mapping_with_webhost(self):
        mapping = parse_host_provider_map("cba.example.com=gitlab@www.example.com")
        self.assertEqual(
            detect_provider("cba.example.com", mapping), ("gitlab", "www.example.com")
        )

    def test_mapping_ignores_broken_entries(self):
        self.assertEqual(parse_host_provider_map("noequals host=  =gitlab"), {})


class BuildBlobUrlTest(unittest.TestCase):
    """provider ごとの blob URL 形式。"""

    def test_github_style(self):
        self.assertEqual(
            build_blob_url("https://github.com/owner/repo", "github", "abc123", "docs/a.md"),
            "https://github.com/owner/repo/blob/abc123/docs/a.md",
        )

    def test_gitlab_style(self):
        self.assertEqual(
            build_blob_url("https://gitlab.com/owner/repo", "gitlab", "abc123", "docs/a.md"),
            "https://gitlab.com/owner/repo/-/blob/abc123/docs/a.md",
        )

    def test_path_is_encoded_but_keeps_separator(self):
        self.assertEqual(
            build_blob_url("https://github.com/o/r", "github", "abc", "docs/日本語 と.md"),
            "https://github.com/o/r/blob/abc/docs/%E6%97%A5%E6%9C%AC%E8%AA%9E%20%E3%81%A8.md",
        )


def _git(repo, *args):
    subprocess.run(["git", "-C", repo] + list(args), check=True,
                   capture_output=True, text=True)


class ResolverTest(unittest.TestCase):
    """一時リポジトリでの解決条件 (追跡済み / 未追跡 / .gitignore 対象)。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = os.path.realpath(self.tmp.name)
        _git(self.repo, "init", "-q", "-b", "main")
        _git(self.repo, "config", "user.email", "test@example.com")
        _git(self.repo, "config", "user.name", "test")
        _git(self.repo, "remote", "add", "origin", "git@github.com:owner/repo.git")

        os.makedirs(os.path.join(self.repo, "docs"))
        self._write("docs/tracked.md", "# tracked\n")
        self._write(".gitignore", "docs/generated.md\n")
        self._write("docs/generated.md", "# generated\n")
        _git(self.repo, "add", "docs/tracked.md", ".gitignore")
        _git(self.repo, "add", "-f", "docs/generated.md")
        _git(self.repo, "commit", "-q", "-m", "init")
        self._write("docs/untracked.md", "# untracked\n")

        self.head = subprocess.run(
            ["git", "-C", self.repo, "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, relative, text):
        with open(os.path.join(self.repo, relative), "w", encoding="utf-8") as handle:
            handle.write(text)

    def _resolve(self, relative):
        return GitLinkResolver().resolve(os.path.join(self.repo, relative))

    def test_tracked_file(self):
        url, provider = self._resolve("docs/tracked.md")
        self.assertEqual(provider, "github")
        self.assertEqual(
            url, "https://github.com/owner/repo/blob/{}/docs/tracked.md".format(self.head)
        )

    def test_untracked_file_has_no_link(self):
        self.assertEqual(self._resolve("docs/untracked.md"), (None, None))

    def test_gitignored_but_tracked_file_keeps_link(self):
        # git check-ignore は索引にあるパスを無視対象として報告しないため、
        # 強制追加された .gitignore 対象にはリンクが付く。
        # get_file_git_url.sh も同じ結果になる (docs/livedocs-design.md を参照)。
        url, _provider = self._resolve("docs/generated.md")
        self.assertIn("/blob/{}/docs/generated.md".format(self.head), url)

    def test_gitignored_and_untracked_file_has_no_link(self):
        # doxyfw の生成 md はこの経路で除外される。
        self._write("docs/ignored.md", "# ignored\n")
        with open(os.path.join(self.repo, ".gitignore"), "a", encoding="utf-8") as handle:
            handle.write("docs/ignored.md\n")
        self.assertEqual(self._resolve("docs/ignored.md"), (None, None))

    def test_missing_remote_has_no_link(self):
        _git(self.repo, "remote", "remove", "origin")
        self.assertEqual(self._resolve("docs/tracked.md"), (None, None))

    def test_outside_repository_has_no_link(self):
        with tempfile.TemporaryDirectory() as outside:
            path = os.path.join(outside, "a.md")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("# a\n")
            self.assertEqual(GitLinkResolver().resolve(path), (None, None))

    def test_webhost_mapping_replaces_host(self):
        _git(self.repo, "remote", "set-url", "origin", "git@cba.example.com:owner/repo.git")
        resolver = GitLinkResolver(parse_host_provider_map("cba.example.com=gitlab@www.example.com"))
        url, provider = resolver.resolve(os.path.join(self.repo, "docs/tracked.md"))
        self.assertEqual(provider, "gitlab")
        self.assertTrue(url.startswith("https://www.example.com/owner/repo/-/blob/"))

    def test_generic_provider_is_rounded_to_git(self):
        _git(self.repo, "remote", "set-url", "origin", "https://scm.example.com/owner/repo.git")
        url, provider = self._resolve("docs/tracked.md")
        self.assertEqual(provider, "git")
        self.assertTrue(url.startswith("https://scm.example.com/owner/repo/blob/"))

    def test_last_commit_follows_the_newest_change(self):
        self._write("docs/tracked.md", "# tracked 2\n")
        _git(self.repo, "commit", "-q", "-am", "update")
        head = subprocess.run(
            ["git", "-C", self.repo, "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        url, _provider = self._resolve("docs/tracked.md")
        self.assertIn("/blob/{}/".format(head), url)


if __name__ == "__main__":
    unittest.main()
