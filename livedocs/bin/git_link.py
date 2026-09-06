#!/usr/bin/env python3
"""Markdown ソースに対応する Git 由来のページ情報を解決する。

解決する情報は次の 3 つで、いずれも同じリポジトリ走査から導出します。

- 単一ページ (blob ビュー) の URL と provider (``bin/get_file_git_url.sh`` の移植)
- 発行者となるコミッター名の並び (``bin/get_file_author.sh`` の移植)
- 発行日時と最終コミット ID の素材 (``bin/get_file_date.sh`` の移植)

URL 形式、provider の判定、非表示の条件はシェル版と同じにします。
発行者と発行日時の文字列への整形は ``publish_info.py`` が持ちます。

シェル版はファイルごとに ``git log -1`` を呼びますが、動的発行は発行対象すべてを
1 回のステージングで処理するため、リポジトリごとに次の情報を 1 度だけ集めます。

- ``git config --get remote.origin.url`` から web ベース URL と provider
- ``git ls-files`` による追跡済みパスの集合
- ``git diff --name-only HEAD`` による未コミット差分のパス集合
- ``git config user.name`` による現在のユーザー名
- ``git log --name-only`` の 1 パスによる、パス→最終コミットとコミッター名の並び

設計は docs/livedocs-design.md の「Git 単一ページ リンク」と「発行者と発行日時」を参照。
"""

from __future__ import annotations

import os
import subprocess
import urllib.parse

# アイコンを持つ provider。これ以外は汎用 git へ丸める
# (pub_markdown_core.sh の build_git_link_metadata_args と同じ)。
ICON_PROVIDERS = ("github", "gitlab", "gitbucket")


def _run_git(repo, args, stdin_text=None):
    """``git -C <repo> <args>`` を実行し、標準出力を返す。失敗時は ``None``。"""
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotePath=false", "-C", repo] + list(args),
            input=stdin_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except (OSError, ValueError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def normalize_remote_url(url):
    """remote URL を web ベース URL へ正規化し ``(base, host)`` を返す。

    対応する形式は ``get_file_git_url.sh`` の ``normalize_remote_url`` と同じです。
    解決できない場合は ``(None, None)`` を返します。
    """
    if not url:
        return None, None

    url = url.strip()
    if url.endswith(".git"):
        url = url[: -len(".git")]
    url = url.rstrip("/")

    if url.startswith(("https://", "http://")):
        rest = url.split("://", 1)[1]
        return url, rest.split("/", 1)[0]

    if url.startswith("ssh://"):
        rest = url[len("ssh://"):]
        if "@" in rest:
            rest = rest.split("@", 1)[1]
        if "/" not in rest:
            return None, None
        host, _, path = rest.partition("/")
        host = host.split(":", 1)[0]  # web では port が異なるため除去する
        return "https://{}/{}".format(host, path), host

    # git@host:owner/repo (scp ライク)
    if "@" in url and ":" in url.split("@", 1)[1] and "/" not in url.split("@", 1)[0]:
        rest = url.split("@", 1)[1]
        host, _, path = rest.partition(":")
        if not host or not path:
            return None, None
        return "https://{}/{}".format(host, path), host

    return None, None


def parse_host_provider_map(spec):
    """``host=provider[@webhost]`` のスペース区切り指定を辞書へ読み出す。"""
    mapping = {}
    for entry in (spec or "").split():
        if "=" not in entry:
            continue
        host, _, value = entry.partition("=")
        provider, _, webhost = value.partition("@")
        host = host.strip()
        provider = provider.strip()
        if not host or not provider:
            continue
        mapping[host] = (provider, webhost.strip() or None)
    return mapping


def detect_provider(host, mapping=None):
    """host から ``(provider, webhost)`` を判定する。

    設定マッピングを最優先し、次に既知の公開ホストを自動判定します。
    判定できないホストは汎用 ``git`` 扱いです。
    """
    if mapping and host in mapping:
        return mapping[host]

    lowered = (host or "").lower()
    if lowered == "github.com":
        return "github", None
    if lowered == "gitlab.com" or "gitlab" in lowered:
        return "gitlab", None
    if "gitbucket" in lowered:
        return "gitbucket", None
    return "git", None


def build_blob_url(base, provider, ref, relative_path):
    """provider に応じた blob URL を組み立てる。"""
    encoded = urllib.parse.quote(relative_path, safe="/")
    if provider == "gitlab":
        return "{}/-/blob/{}/{}".format(base, ref, encoded)
    # github / gitbucket / gitea / git (汎用) は /blob/ 形式
    return "{}/blob/{}/{}".format(base, ref, encoded)


class RepoInfo:
    """1 つの Git リポジトリについて、ページ情報の生成に必要な情報をまとめて保持する。"""

    def __init__(self, root, host_provider_map=None):
        self.root = root
        self.base = None
        self.provider = None
        self.user_name = ""
        self._tracked = set()
        self._dirty = set()
        self._last_commit = {}
        self._authors = {}
        self._collect(host_provider_map)

    def _collect(self, host_provider_map):
        """リポジトリ単位の情報を集める。

        remote URL を解決できないリポジトリでも、発行者と発行日時は静的発行と同じ
        値を出します。このため remote の解決可否は ``base`` と ``provider`` だけの
        条件とし、追跡済みパスとコミット索引の収集は必ず行います。
        """
        self._collect_remote(host_provider_map)

        tracked = _run_git(self.root, ["ls-files", "-z"])
        if tracked:
            self._tracked = {path for path in tracked.split("\0") if path}

        dirty = _run_git(self.root, ["diff", "--name-only", "-z", "HEAD"])
        if dirty:
            self._dirty = {path for path in dirty.split("\0") if path}

        self.user_name = (_run_git(self.root, ["config", "user.name"]) or "").strip()

        self._collect_commit_index()

    def _collect_remote(self, host_provider_map):
        """``remote.origin.url`` から web ベース URL と provider を決める。"""
        remote = _run_git(self.root, ["config", "--get", "remote.origin.url"])
        base, host = normalize_remote_url((remote or "").strip())
        if base is None:
            return

        provider, webhost = detect_provider(host, host_provider_map)
        if webhost:
            base = base.replace(host, webhost, 1)
        if provider not in ICON_PROVIDERS:
            provider = "git"

        self.base = base
        self.provider = provider

    def _collect_commit_index(self):
        """``git log --name-only`` の 1 パスで、パスごとの最終コミットと著者を作る。

        逆時系列で走査するため、パスが最初に現れたコミットが最終更新です。
        コミット行は ``%x01`` (SOH) を先頭に置いて区別し、項目は ``%x02`` (STX) で
        区切ります。どちらもパス名には現れません。

        コミッター名は ``get_file_author.sh`` の
        ``git log --reverse --format=%cn | awk '!seen[$0]++'`` と同じ「古い順・初出優先」
        にそろえます。ここでは新しい順に走査するため、既出の名前を取り除いてから
        末尾へ追加し、``authors()`` で反転します。これで各名前は最も古い出現位置に
        置かれ、重複も残りません。

        マージ コミットはファイル名を列挙しないため、``git log -1 -- <path>`` と結果が
        食い違う可能性があります。対応表に無いパスは ``last_commit_info()`` が
        ファイル単位の問い合わせへフォールバックします。
        """
        log = _run_git(
            self.root,
            ["log", "--format=%x01%H%x02%h%x02%cD%x02%cn", "--name-only", "HEAD"],
        )
        if not log:
            return

        current = None
        committer = None
        for line in log.split("\n"):
            if line.startswith("\x01"):
                fields = line[1:].split("\x02")
                if len(fields) != 4:
                    current = None
                    committer = None
                    continue
                sha, short_sha, committer_date, committer = (
                    field.strip() for field in fields
                )
                current = (sha, short_sha, committer_date)
                continue
            path = line.strip()
            if not path or current is None:
                continue
            self._last_commit.setdefault(path, current)
            if committer:
                names = self._authors.setdefault(path, [])
                if committer in names:
                    names.remove(committer)
                names.append(committer)

    def is_linkable(self, relative_path):
        """リンクを出せるパスかどうかを返す。

        条件は remote URL を解決できていることと、追跡済みであることです。
        ``get_file_git_url.sh`` は追跡確認の後に ``git check-ignore`` も行いますが、
        ``git check-ignore`` は既定で索引にあるパスを無視対象として報告しないため、
        追跡済みのパスに対しては常に「対象外」を返します。doxyfw の生成 md のような
        ``.gitignore`` 対象の除外は、それらが未追跡であることによって成立しています。
        """
        if self.base is None:
            return False
        return self.is_tracked(relative_path)

    def is_tracked(self, relative_path):
        """追跡済みのパスかどうかを返す。"""
        return relative_path in self._tracked

    def is_dirty(self, relative_path):
        """未コミット差分を持つパスかどうかを返す。"""
        return relative_path in self._dirty

    def last_commit_info(self, relative_path):
        """``(SHA, 短縮 SHA, コミッター日時)`` を返す。無ければ ``None``。

        対応表に無ければ 1 ファイルだけ問い合わせます。
        """
        info = self._last_commit.get(relative_path)
        if info:
            return info
        output = _run_git(
            self.root,
            ["log", "-1", "--format=%H%x02%h%x02%cD", "--", relative_path],
        )
        fields = (output or "").strip().split("\x02")
        if len(fields) != 3 or not fields[0]:
            return None
        info = tuple(field.strip() for field in fields)
        self._last_commit[relative_path] = info
        return info

    def last_commit(self, relative_path):
        """最終コミット SHA を返す。取得できなければ ``None``。"""
        info = self.last_commit_info(relative_path)
        return info[0] if info else None

    def authors(self, relative_path):
        """コミッター名を古い順・重複排除で返す。

        対応表に無ければ 1 ファイルだけ問い合わせます。
        """
        names = self._authors.get(relative_path)
        if names is not None:
            return list(reversed(names))

        output = _run_git(
            self.root, ["log", "--reverse", "--format=%cn", "--", relative_path]
        )
        ordered = []
        for line in (output or "").split("\n"):
            name = line.strip()
            if name and name not in ordered:
                ordered.append(name)
        # 反転した形で保持し、``authors()`` の戻り値と表現をそろえる。
        self._authors[relative_path] = list(reversed(ordered))
        return ordered


class PublishFacts:
    """1 ファイルについて、発行者と発行日時の材料をまとめて運ぶ。

    整形は ``publish_info.py`` が行います。ここでは git から読んだ事実だけを持ちます。
    """

    def __init__(self, tracked=False, dirty=False, authors=(), committer_date=None,
                 short_sha=None, user_name=""):
        self.tracked = tracked
        self.dirty = dirty
        self.authors = list(authors)
        self.committer_date = committer_date
        self.short_sha = short_sha
        self.user_name = user_name


class GitLinkResolver:
    """実体パスから blob URL と発行情報を解決する。リポジトリ単位で結果を再利用する。"""

    def __init__(self, host_provider_map=None, on_repo_collect=None):
        self._host_provider_map = host_provider_map or {}
        self._on_repo_collect = on_repo_collect
        self._repo_by_dir = {}
        self._repo_by_root = {}

    def _repo_for(self, directory):
        """ディレクトリが属するリポジトリの ``RepoInfo`` を返す。無ければ ``None``。"""
        key = os.path.normcase(directory)
        if key in self._repo_by_dir:
            return self._repo_by_dir[key]

        output = _run_git(directory, ["rev-parse", "--show-toplevel"])
        root = (output or "").strip()
        if not root:
            self._repo_by_dir[key] = None
            return None

        root = os.path.normpath(root)
        root_key = os.path.normcase(root)
        repo = self._repo_by_root.get(root_key)
        if repo is None:
            # ``RepoInfo`` の ``git log --name-only`` の前に出す。長い収集の無応答を避ける。
            if self._on_repo_collect is not None:
                self._on_repo_collect(root)
            repo = RepoInfo(root, self._host_provider_map)
            self._repo_by_root[root_key] = repo
        self._repo_by_dir[key] = repo
        return repo

    def _locate(self, path):
        """``(RepoInfo, リポジトリ ルートからの相対パス)`` を返す。無ければ ``(None, None)``。

        シンボリック リンクは実体へ解決します。``.agents/skills`` のように
        リンク経由で発行されるファイルを、実体側のリポジトリで解決するためです。
        """
        if not path:
            return None, None

        real_path = os.path.realpath(path)
        directory = os.path.dirname(real_path)
        if not os.path.isdir(directory):
            return None, None

        repo = self._repo_for(directory)
        if repo is None:
            return None, None

        try:
            relative = os.path.relpath(real_path, repo.root)
        except ValueError:
            return None, None
        relative = relative.replace(os.sep, "/")
        if relative.startswith("../"):
            return None, None

        return repo, relative

    def resolve_publish_facts(self, path):
        """発行者と発行日時の材料を ``PublishFacts`` で返す。

        remote URL を解決できないリポジトリでも値を返します。静的発行の
        ``get_file_author.sh`` と ``get_file_date.sh`` が remote を見ないためです。
        Git 管理外のパスは、追跡済みでない ``PublishFacts`` を返します。
        """
        repo, relative = self._locate(path)
        if repo is None:
            return PublishFacts()

        if not repo.is_tracked(relative):
            return PublishFacts(user_name=repo.user_name)

        info = repo.last_commit_info(relative)
        authors = repo.authors(relative)
        return PublishFacts(
            tracked=True,
            dirty=repo.is_dirty(relative),
            authors=authors,
            committer_date=info[2] if info else None,
            short_sha=info[1] if info else None,
            user_name=repo.user_name,
        )

    def resolve(self, path):
        """``(url, provider)`` を返す。リンクを出さない場合は ``(None, None)``。"""
        repo, relative = self._locate(path)
        if repo is None or repo.base is None:
            return None, None

        if not repo.is_linkable(relative):
            return None, None

        ref = repo.last_commit(relative)
        if not ref:
            return None, None

        return build_blob_url(repo.base, repo.provider, ref, relative), repo.provider
