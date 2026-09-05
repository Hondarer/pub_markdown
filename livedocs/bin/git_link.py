#!/usr/bin/env python3
"""Markdown ソースに対応する Git ホスティング上の単一ページ (blob ビュー) URL を解決する。

docsfw の ``bin/get_file_git_url.sh`` を Python へ移植したものです。
URL 形式、provider の判定、非表示の条件はシェル版と同じにします。

シェル版はファイルごとに ``git log -1`` を呼びますが、動的発行は発行対象すべてを
1 回のステージングで処理するため、リポジトリごとに次の情報を 1 度だけ集めます。

- ``git config --get remote.origin.url`` から web ベース URL と provider
- ``git ls-files`` による追跡済みパスの集合
- ``git log --name-only`` の 1 パスによるパス→最終コミット SHA の対応表

設計は docs/livedocs-design.md の「Git 単一ページ リンク」を参照。
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
    """1 つの Git リポジトリについて、URL 生成に必要な情報をまとめて保持する。"""

    def __init__(self, root, host_provider_map=None):
        self.root = root
        self.base = None
        self.provider = None
        self._tracked = set()
        self._last_commit = {}
        self._collect(host_provider_map)

    def _collect(self, host_provider_map):
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

        tracked = _run_git(self.root, ["ls-files", "-z"])
        if tracked:
            self._tracked = {path for path in tracked.split("\0") if path}

        self._collect_last_commits()

    def _collect_last_commits(self):
        """``git log --name-only`` の 1 パスでパス→最終コミット SHA を作る。

        逆時系列で走査するため、パスが最初に現れたコミットが最終更新です。
        コミット行は ``%x01`` (SOH) を先頭に置いて区別します。パス名には現れません。
        マージ コミットはファイル名を列挙しないため、``git log -1 -- <path>`` と
        結果が食い違う可能性があります。対応表に無いパスは ``last_commit()`` が
        ファイル単位の問い合わせへフォールバックします。
        """
        log = _run_git(self.root, ["log", "--format=%x01%H", "--name-only", "HEAD"])
        if not log:
            return

        current = None
        for line in log.split("\n"):
            if line.startswith("\x01"):
                current = line[1:].strip()
                continue
            path = line.strip()
            if not path or current is None:
                continue
            self._last_commit.setdefault(path, current)

    def is_linkable(self, relative_path):
        """リンクを出せるパスかどうかを返す。

        条件は追跡済みであることだけです。``get_file_git_url.sh`` は追跡確認の後に
        ``git check-ignore`` も行いますが、``git check-ignore`` は既定で索引にある
        パスを無視対象として報告しないため、追跡済みのパスに対しては常に「対象外」
        を返します。doxyfw の生成 md のような ``.gitignore`` 対象の除外は、それらが
        未追跡であることによって成立しています。
        """
        if self.base is None:
            return False
        return relative_path in self._tracked

    def last_commit(self, relative_path):
        """最終コミット SHA を返す。対応表に無ければ 1 ファイルだけ問い合わせる。"""
        sha = self._last_commit.get(relative_path)
        if sha:
            return sha
        output = _run_git(self.root, ["log", "-1", "--format=%H", "--", relative_path])
        sha = (output or "").strip()
        if sha:
            self._last_commit[relative_path] = sha
        return sha or None


class GitLinkResolver:
    """実体パスから blob URL を解決する。リポジトリ単位で結果を再利用する。"""

    def __init__(self, host_provider_map=None):
        self._host_provider_map = host_provider_map or {}
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
            repo = RepoInfo(root, self._host_provider_map)
            self._repo_by_root[root_key] = repo
        self._repo_by_dir[key] = repo
        return repo

    def resolve(self, path):
        """``(url, provider)`` を返す。リンクを出さない場合は ``(None, None)``。

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
        if repo is None or repo.base is None:
            return None, None

        try:
            relative = os.path.relpath(real_path, repo.root)
        except ValueError:
            return None, None
        relative = relative.replace(os.sep, "/")
        if relative.startswith("../"):
            return None, None

        if not repo.is_linkable(relative):
            return None, None

        ref = repo.last_commit(relative)
        if not ref:
            return None, None

        return build_blob_url(repo.base, repo.provider, ref, relative), repo.provider
