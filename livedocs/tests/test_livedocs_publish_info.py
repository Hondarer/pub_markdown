#!/usr/bin/env python3
"""発行者と発行日時の解決と整形に関する単体テスト。

静的発行の ``bin/get_file_author.sh`` / ``bin/get_file_date.sh`` と同じ文字列に
なることが要件のため、それらを実際に実行して突き合わせる試験も持ちます。
"""

import email.utils
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
sys.path.insert(0, BIN_DIR)

from git_link import GitLinkResolver, PublishFacts  # noqa: E402
from publish_info import (  # noqa: E402
    build_author,
    build_date,
    build_publish_info,
    format_author,
)

DOCSFW_BIN = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "bin")
)


def _git(repo, *args):
    subprocess.run(["git", "-C", repo] + list(args), check=True,
                   capture_output=True, text=True)


class FormatAuthorTest(unittest.TestCase):
    """``set-meta.lua`` と同じ人数別の整形になること。"""

    def test_single(self):
        self.assertEqual(format_author(["a"]), "a")

    def test_pair(self):
        self.assertEqual(format_author(["a", "b"]), "a, b")

    def test_three_or_more_keeps_first_and_last(self):
        self.assertEqual(format_author(["a", "b", "c"]), "a, c et al.")
        self.assertEqual(format_author(["a", "b", "c", "d"]), "a, d et al.")

    def test_empty(self):
        self.assertEqual(format_author([]), "")
        self.assertEqual(format_author(None), "")
        self.assertEqual(format_author(["", ""]), "")


class BuildAuthorTest(unittest.TestCase):
    """未追跡と未コミット差分の扱い。"""

    def test_untracked_is_empty(self):
        facts = PublishFacts(tracked=False, authors=["a"], user_name="me")
        self.assertEqual(build_author(facts), "")

    def test_clean_uses_history_only(self):
        facts = PublishFacts(tracked=True, dirty=False, authors=["a", "b"], user_name="me")
        self.assertEqual(build_author(facts), "a, b")

    def test_dirty_appends_current_user(self):
        facts = PublishFacts(tracked=True, dirty=True, authors=["a"], user_name="me")
        self.assertEqual(build_author(facts), "a, me")

    def test_dirty_moves_current_user_to_the_end(self):
        # get_file_author.sh は名前を足してから重複排除するため、既出でも末尾へ移る。
        facts = PublishFacts(tracked=True, dirty=True, authors=["me", "b"], user_name="me")
        self.assertEqual(build_author(facts), "b, me")


class BuildDateTest(unittest.TestCase):
    """``get_file_date.sh`` と同じ 3 分岐になること。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "a.md")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("# a\n")
        self.mtime = email.utils.formatdate(os.path.getmtime(self.path), localtime=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_tracked_and_clean(self):
        facts = PublishFacts(
            tracked=True, dirty=False,
            committer_date="Sat, 06 Sep 2026 12:34:56 +0900", short_sha="5927f1d",
        )
        self.assertEqual(
            build_date(self.path, facts), "Sat, 06 Sep 2026 12:34:56 +0900 5927f1d"
        )

    def test_tracked_and_dirty_uses_mtime_and_marks_plus(self):
        facts = PublishFacts(
            tracked=True, dirty=True,
            committer_date="Sat, 06 Sep 2026 12:34:56 +0900", short_sha="5927f1d",
        )
        self.assertEqual(build_date(self.path, facts), "{} 5927f1d+".format(self.mtime))

    def test_untracked_uses_mtime_without_sha(self):
        self.assertEqual(build_date(self.path, PublishFacts()), self.mtime)

    def test_missing_file_is_empty(self):
        self.assertEqual(build_date(os.path.join(self.tmp.name, "none.md"), PublishFacts()), "")


class BuildPublishInfoTest(unittest.TestCase):
    """``autoSetAuthor`` / ``autoSetDate`` の無効化が個別に効くこと。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "a.md")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("# a\n")
        self.facts = PublishFacts(
            tracked=True, dirty=False, authors=["a"],
            committer_date="Sat, 06 Sep 2026 12:34:56 +0900", short_sha="5927f1d",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_both_enabled(self):
        author, date = build_publish_info(self.path, self.facts)
        self.assertEqual(author, "a")
        self.assertEqual(date, "Sat, 06 Sep 2026 12:34:56 +0900 5927f1d")

    def test_author_disabled(self):
        author, date = build_publish_info(self.path, self.facts, auto_author=False)
        self.assertEqual(author, "")
        self.assertTrue(date)

    def test_date_disabled(self):
        author, date = build_publish_info(self.path, self.facts, auto_date=False)
        self.assertTrue(author)
        self.assertEqual(date, "")


class ResolvePublishFactsTest(unittest.TestCase):
    """一時リポジトリでの事実収集。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = os.path.realpath(self.tmp.name)
        _git(self.repo, "init", "-q", "-b", "main")
        _git(self.repo, "config", "user.email", "first@example.com")
        _git(self.repo, "config", "user.name", "first")
        _git(self.repo, "remote", "add", "origin", "git@github.com:owner/repo.git")

        os.makedirs(os.path.join(self.repo, "docs"))
        self._write("docs/a.md", "# a\n")
        self._write("docs/b.md", "# b\n")
        _git(self.repo, "add", "docs/a.md", "docs/b.md")
        _git(self.repo, "commit", "-q", "-m", "init")

        _git(self.repo, "config", "user.name", "second")
        self._write("docs/a.md", "# a 2\n")
        _git(self.repo, "commit", "-q", "-am", "update a")

        self._write("docs/untracked.md", "# untracked\n")

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, relative, text):
        with open(os.path.join(self.repo, relative), "w", encoding="utf-8") as handle:
            handle.write(text)

    def _facts(self, relative, resolver=None):
        resolver = resolver or GitLinkResolver()
        return resolver.resolve_publish_facts(os.path.join(self.repo, relative))

    def test_authors_are_oldest_first_and_deduplicated(self):
        facts = self._facts("docs/a.md")
        self.assertTrue(facts.tracked)
        self.assertFalse(facts.dirty)
        self.assertEqual(facts.authors, ["first", "second"])

    def test_single_author(self):
        self.assertEqual(self._facts("docs/b.md").authors, ["first"])

    def test_duplicate_committer_appears_once(self):
        _git(self.repo, "config", "user.name", "first")
        self._write("docs/a.md", "# a 3\n")
        _git(self.repo, "commit", "-q", "-am", "update a again")
        self.assertEqual(self._facts("docs/a.md").authors, ["first", "second"])

    def test_last_commit_is_the_newest(self):
        facts = self._facts("docs/a.md")
        expected = subprocess.run(
            ["git", "-C", self.repo, "log", "-1", "--format=%h%x02%cD", "--", "docs/a.md"],
            capture_output=True, text=True, check=True,
        ).stdout.strip().split("\x02")
        self.assertEqual(facts.short_sha, expected[0])
        self.assertEqual(facts.committer_date, expected[1])

    def test_uncommitted_change_is_dirty(self):
        self._write("docs/b.md", "# b 2\n")
        facts = self._facts("docs/b.md")
        self.assertTrue(facts.dirty)
        self.assertEqual(facts.user_name, "second")
        self.assertEqual(build_author(facts), "first, second")

    def test_untracked_file(self):
        facts = self._facts("docs/untracked.md")
        self.assertFalse(facts.tracked)
        self.assertEqual(build_author(facts), "")

    def test_outside_repository(self):
        with tempfile.TemporaryDirectory() as outside:
            path = os.path.join(outside, "a.md")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("# a\n")
            facts = GitLinkResolver().resolve_publish_facts(path)
            self.assertFalse(facts.tracked)

    def test_missing_remote_still_resolves(self):
        # 発行者と発行日時は remote に依存しない。RepoInfo._collect() が remote を
        # 解決できないときに追跡集合とコミット索引の収集を飛ばさないこと。
        _git(self.repo, "remote", "remove", "origin")
        resolver = GitLinkResolver()
        facts = self._facts("docs/a.md", resolver)
        self.assertTrue(facts.tracked)
        self.assertEqual(facts.authors, ["first", "second"])
        self.assertTrue(facts.short_sha)
        # 同じ resolver で blob URL は出ない。
        self.assertEqual(
            resolver.resolve(os.path.join(self.repo, "docs/a.md")), (None, None)
        )


@unittest.skipIf(shutil.which("bash") is None, "bash が無いため静的発行の実装を実行できません")
class StaticPublishingParityTest(unittest.TestCase):
    """静的発行のシェル実装と同じ文字列になること (本機能の合否判定)。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = os.path.realpath(self.tmp.name)
        _git(self.repo, "init", "-q", "-b", "main")
        _git(self.repo, "config", "user.email", "first@example.com")
        _git(self.repo, "config", "user.name", "first")

        os.makedirs(os.path.join(self.repo, "docs"))
        self._write("docs/clean.md", "# clean\n")
        self._write("docs/dirty.md", "# dirty\n")
        _git(self.repo, "add", "docs/clean.md", "docs/dirty.md")
        _git(self.repo, "commit", "-q", "-m", "init")

        _git(self.repo, "config", "user.name", "second")
        self._write("docs/clean.md", "# clean 2\n")
        _git(self.repo, "commit", "-q", "-am", "update")

        self._write("docs/dirty.md", "# dirty 2\n")
        self._write("docs/untracked.md", "# untracked\n")

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, relative, text):
        with open(os.path.join(self.repo, relative), "w", encoding="utf-8") as handle:
            handle.write(text)

    def _shell(self, script, relative):
        path = os.path.join(DOCSFW_BIN, script)
        if not os.path.isfile(path):
            self.skipTest("{} が見つかりません".format(script))
        result = subprocess.run(
            ["bash", path, os.path.join(self.repo, relative)],
            capture_output=True, text=True, check=True,
        )
        return result.stdout

    def _assert_same(self, relative):
        facts = GitLinkResolver().resolve_publish_facts(
            os.path.join(self.repo, relative)
        )
        expected_names = [
            line.strip() for line in self._shell("get_file_author.sh", relative).split("\n")
            if line.strip()
        ]
        self.assertEqual(
            build_author(facts), format_author(expected_names),
            "発行者が静的発行と異なります: {}".format(relative),
        )
        self.assertEqual(
            build_date(os.path.join(self.repo, relative), facts),
            self._shell("get_file_date.sh", relative).strip(),
            "発行日時が静的発行と異なります: {}".format(relative),
        )

    def test_tracked_and_clean(self):
        self._assert_same("docs/clean.md")

    def test_tracked_and_dirty(self):
        self._assert_same("docs/dirty.md")

    def test_untracked(self):
        self._assert_same("docs/untracked.md")


if __name__ == "__main__":
    unittest.main()
