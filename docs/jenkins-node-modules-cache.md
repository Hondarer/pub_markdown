# Jenkins での node_modules キャッシュ

## 背景

`bin/pub_markdown_core.sh` は `node_modules/.bin` が存在しない場合に自動で `npm ci` を実行する。  
コンテナー CI では毎回クリーンなワークスペースが作られるため、毎回 `npm ci` が走り時間がかかる。

さらに `bin/package.json` には `puppeteer ^24` が含まれており、`npm ci` の postinstall で  
**Chrome for Testing (Linux 版約 282MB)** が `$HOME/.cache/puppeteer/` にダウンロードされる。  
コンテナー内のホーム ディレクトリが毎回リセットされる環境では、この Chrome ダウンロードも  
毎ビルドで発生する。また `node_modules` キャッシュがヒットして `npm ci` がスキップされると  
postinstall も走らないため、Chrome キャッシュが空のままでは headless レンダリングが失敗する。

GitHub Actions では `actions/cache` が利用できるが、Jenkins には同等の標準機能がない。  
ここでは **固定エージェントおよびコンテナー エージェント** を対象に、  
ホストのファイル システムを活用した `node_modules` と **Chrome キャッシュ** の永続化方式を説明する。

## キャッシュ方式の概要

### node_modules キャッシュ

| 項目 | 内容 |
|---|---|
| **キャッシュ キー** | `package-lock.json` の MD5 ハッシュ |
| **キャッシュ場所** | `/var/cache/docsfw-node-modules/<hash>/node_modules` (ホスト側) |
| **ヒット時の動作** | シンボリック リンクで `bin/node_modules` に接続し、`npm ci` をスキップ |
| **ミス時の動作** | `pub_markdown_core.sh` が自動で `npm ci` を実行 → 完了後キャッシュに保存 |
| **清掃** | 現在のハッシュ以外の古いキャッシュをビルド後に削除 |

`package-lock.json` が変更されるとハッシュが変わり、自動的にキャッシュが無効化される。

### Headless Chrome (Puppeteer) キャッシュ

| 項目 | 内容 |
|---|---|
| **既定の保存先** | コンテナー内 `$HOME/.cache/puppeteer/chrome/` および `$HOME/.cache/puppeteer/chrome-headless-shell/` |
| **ホスト永続化先 (例)** | `/var/cache/docsfw-puppeteer/` をコンテナーの `$HOME/.cache/puppeteer` にマウント |
| **無効化トリガー** | `package-lock.json` の変更 (puppeteer バージョン更新 → Chrome バージョンも変わるため) |
| **node_modules との関係** | node_modules キャッシュ ヒット時は `npm ci` がスキップされるため、Chrome キャッシュが空だと headless レンダリングが失敗する |

`node_modules` のキャッシュだけでは不十分なため、**両方を永続化する必要がある**。

## 前提条件

- Jenkins エージェントが固定 (ホストのファイル システムが永続する)  
  コンテナー エージェントの場合はホスト側の永続ディレクトリをマウントして代替する
- Jenkins の実行ユーザーが `/var/cache/docsfw-node-modules/` および `/var/cache/docsfw-puppeteer/` への書き込み権限を持つ
- エージェントの OS・ディストリビューションが統一されている  
  (`node_modules` 内のバイナリはビルド環境に依存するため。Chrome も同様にプラットフォーム固有のバイナリ)

## Jenkinsfile サンプル

```groovy
pipeline {
    agent any

    environment {
        DOCSFW_BIN              = "${WORKSPACE}/framework/docsfw/bin"
        NODE_MODULES_CACHE_BASE = '/var/cache/docsfw-node-modules'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                sh 'git submodule update --init --recursive'
            }
        }

        stage('Restore node_modules cache') {
            steps {
                script {
                    // package-lock.json の MD5 からキャッシュキーを生成
                    def lockHash = sh(
                        script: "md5sum '${env.DOCSFW_BIN}/package-lock.json' | awk '{print \$1}'",
                        returnStdout: true
                    ).trim()
                    env.NODE_MODULES_CACHE_KEY = lockHash

                    def cacheDir = "${env.NODE_MODULES_CACHE_BASE}/${lockHash}/node_modules"

                    if (fileExists("${cacheDir}/.bin")) {
                        echo "node_modules cache hit: ${cacheDir}"
                        // キャッシュをシンボリックリンクで参照
                        // → pub_markdown_core.sh が node_modules を検出し npm ci をスキップする
                        sh "ln -sfn '${cacheDir}' '${env.DOCSFW_BIN}/node_modules'"
                        env.NODE_MODULES_CACHE_HIT = 'true'
                    } else {
                        echo "node_modules cache miss: will run npm ci"
                        env.NODE_MODULES_CACHE_HIT = 'false'
                    }
                }
            }
        }

        stage('Generate docs') {
            steps {
                sh """
                    bash '${env.DOCSFW_BIN}/pub_markdown_core.sh' \\
                        --workspaceFolder='${WORKSPACE}'
                """
            }
        }

        stage('Save node_modules cache') {
            // キャッシュミスのときだけ保存する
            when {
                expression { env.NODE_MODULES_CACHE_HIT == 'false' }
            }
            steps {
                script {
                    def cacheDir = "${env.NODE_MODULES_CACHE_BASE}/${env.NODE_MODULES_CACHE_KEY}"
                    sh """
                        mkdir -p '${cacheDir}'
                        cp -a '${env.DOCSFW_BIN}/node_modules' '${cacheDir}/node_modules'
                    """
                    echo "node_modules cached to: ${cacheDir}"
                }
            }
        }
    }

    post {
        always {
            script {
                // 現在のハッシュ以外の古いキャッシュを削除する
                if (env.NODE_MODULES_CACHE_KEY) {
                    sh """
                        find '${env.NODE_MODULES_CACHE_BASE}' -mindepth 1 -maxdepth 1 -type d \\
                            ! -name '${env.NODE_MODULES_CACHE_KEY}' \\
                            -exec rm -rf {} + 2>/dev/null || true
                    """
                }
            }
        }
    }
}
```

## フリースタイル ジョブ (スクリプト記述) サンプル

Jenkinsfile を使わない **フリースタイル プロジェクト** では、「ビルド」セクションの  
「**シェルの実行**」ステップを複数追加して同等の処理を実現する。

各ステップは独立したサブシェルで動くため、変数の受け渡しにはワークスペース上の  
一時ファイル (`${WORKSPACE}/.node_modules_cache_state`) を使う。

---

### ステップ 1 — キャッシュ復元 (ビルド前)

「シェルの実行」に以下を記述する。

```bash
#!/bin/bash
set -e

DOCSFW_BIN="${WORKSPACE}/framework/docsfw/bin"
NODE_MODULES_CACHE_BASE='/var/cache/docsfw-node-modules'
STATE_FILE="${WORKSPACE}/.node_modules_cache_state"

# package-lock.json の MD5 からキャッシュキーを生成
LOCK_HASH=$(md5sum "${DOCSFW_BIN}/package-lock.json" | awk '{print $1}')
CACHE_DIR="${NODE_MODULES_CACHE_BASE}/${LOCK_HASH}/node_modules"

# 後続ステップに渡す状態ファイルを初期化
echo "NODE_MODULES_CACHE_KEY=${LOCK_HASH}"  > "${STATE_FILE}"
echo "NODE_MODULES_CACHE_HIT=false"        >> "${STATE_FILE}"

if [ -d "${CACHE_DIR}/.bin" ]; then
    echo "node_modules cache hit: ${CACHE_DIR}"
    # キャッシュをシンボリックリンクで参照
    # → pub_markdown_core.sh が node_modules を検出し npm ci をスキップする
    ln -sfn "${CACHE_DIR}" "${DOCSFW_BIN}/node_modules"
    sed -i 's/NODE_MODULES_CACHE_HIT=false/NODE_MODULES_CACHE_HIT=true/' "${STATE_FILE}"
else
    echo "node_modules cache miss: npm ci will run in next step"
fi
```

### ステップ 2 — ドキュメント生成

「シェルの実行」に以下を記述する。

```bash
#!/bin/bash
set -e

DOCSFW_BIN="${WORKSPACE}/framework/docsfw/bin"

# node_modules がなければ pub_markdown_core.sh が自動で npm ci を実行する
bash "${DOCSFW_BIN}/pub_markdown_core.sh" \
    --workspaceFolder="${WORKSPACE}"
```

### ステップ 3 — キャッシュ保存 (キャッシュ ミス時のみ)

「シェルの実行」に以下を記述する。

```bash
#!/bin/bash
set -e

DOCSFW_BIN="${WORKSPACE}/framework/docsfw/bin"
NODE_MODULES_CACHE_BASE='/var/cache/docsfw-node-modules'
STATE_FILE="${WORKSPACE}/.node_modules_cache_state"

# ステップ 1 が作成した状態ファイルを読み込む
if [ ! -f "${STATE_FILE}" ]; then
    echo "State file not found, skipping cache save."
    exit 0
fi
# shellcheck disable=SC1090
source "${STATE_FILE}"

if [ "${NODE_MODULES_CACHE_HIT}" = "true" ]; then
    echo "Cache was hit, no save needed."
    exit 0
fi

# キャッシュミス: npm ci で生成された node_modules をキャッシュに保存
CACHE_DIR="${NODE_MODULES_CACHE_BASE}/${NODE_MODULES_CACHE_KEY}"
mkdir -p "${CACHE_DIR}"
cp -a "${DOCSFW_BIN}/node_modules" "${CACHE_DIR}/node_modules"
echo "node_modules cached to: ${CACHE_DIR}"
```

---

### ポスト ビルド アクション — 古いキャッシュの清掃

「ビルド後の処置」→「**スクリプトの実行**」、またはビルド ステップの末尾に追加する。

```bash
#!/bin/bash

NODE_MODULES_CACHE_BASE='/var/cache/docsfw-node-modules'
STATE_FILE="${WORKSPACE}/.node_modules_cache_state"

if [ -f "${STATE_FILE}" ]; then
    # shellcheck disable=SC1090
    source "${STATE_FILE}"
fi

# 現在のハッシュ以外の古いキャッシュを削除する
if [ -n "${NODE_MODULES_CACHE_KEY:-}" ]; then
    find "${NODE_MODULES_CACHE_BASE}" -mindepth 1 -maxdepth 1 -type d \
        ! -name "${NODE_MODULES_CACHE_KEY}" \
        -exec rm -rf {} + 2>/dev/null || true
fi

# 状態ファイルを削除
rm -f "${STATE_FILE}"
```

---

### フリースタイル ジョブの設定概要

| # | ビルド ステップ | 内容 |
|---|---|---|
| 1 | シェルの実行 | キャッシュ復元 (シンボリック リンク作成 or スキップ) |
| 2 | シェルの実行 | `pub_markdown_core.sh` 実行 |
| 3 | シェルの実行 | キャッシュ保存 (ミス時のみ) |
| — | ビルド後の処置 | 古いキャッシュ削除・状態ファイル削除 |

## Headless Chrome キャッシュの永続化 (podman / コンテナー エージェント)

### Chrome のデフォルト ダウンロード位置

`puppeteer ^24` は `npm ci` の postinstall で以下のパスに Chrome for Testing をダウンロードする。

```text
$HOME/.cache/puppeteer/chrome/linux-<バージョン>/chrome-linux64/chrome
$HOME/.cache/puppeteer/chrome-headless-shell/linux-<バージョン>/chrome-headless-shell-linux64/chrome-headless-shell
```

`bin/chrome-wrapper.sh` もこのディレクトリ構造を前提に代替バージョンを探索する。  
`.puppeteerrc.cjs` は配置していないため、環境変数 `PUPPETEER_CACHE_DIR` を明示しない限り  
`os.homedir()/.cache/puppeteer` がデフォルトになる。

コンテナー CI でホームが毎回リセットされる場合は、ホスト側の永続ディレクトリをマウントして引き継ぐ。

### podman / docker でホスト側にマウントする例

```bash
# ホスト側に永続ディレクトリを用意 (初回のみ)
sudo mkdir -p /var/cache/docsfw-puppeteer
sudo chown 1000:1000 /var/cache/docsfw-puppeteer  # コンテナー内ユーザーの uid に合わせる

# Jenkins エージェント コンテナ起動例
podman run --rm \
    -v "${WORKSPACE}:/workspace" \
    -v /var/cache/docsfw-puppeteer:/home/jenkins/.cache/puppeteer:Z \
    -w /workspace \
    docsfw-agent:latest \
    bash framework/docsfw/bin/pub_markdown_core.sh --workspaceFolder=/workspace
```

- `:Z` は SELinux 環境向け。Ubuntu 等では不要な場合は外す。
- コンテナー内ユーザーのホームが `/home/jenkins` 以外の場合は、実際のホーム配下の `.cache/puppeteer` を指す。
- または環境変数で明示する方法も利用できる。

```bash
podman run --rm \
    -v "${WORKSPACE}:/workspace" \
    -v /var/cache/docsfw-puppeteer:/cache/puppeteer:Z \
    -e PUPPETEER_CACHE_DIR=/cache/puppeteer \
    -w /workspace \
    docsfw-agent:latest \
    bash framework/docsfw/bin/pub_markdown_core.sh --workspaceFolder=/workspace
```

### Jenkinsfile コンテナー エージェントでの宣言例

Docker / Podman プラグインを使うコンテナー エージェントでは、`args` でマウントを宣言する。

```groovy
pipeline {
    agent {
        docker {
            image 'docsfw-agent:latest'
            args  '-v /var/cache/docsfw-puppeteer:/home/jenkins/.cache/puppeteer'
        }
    }

    stages {
        stage('Generate docs') {
            steps {
                sh "bash framework/docsfw/bin/pub_markdown_core.sh --workspaceFolder='${WORKSPACE}'"
            }
        }
    }
}
```

`node_modules` キャッシュも引き続き利用する場合は、`args` に両マウントを追加する。

```groovy
args '-v /var/cache/docsfw-node-modules:/cache/node-modules ' +
     '-v /var/cache/docsfw-puppeteer:/home/jenkins/.cache/puppeteer'
```

### node_modules キャッシュ ヒット時の整合性

node_modules キャッシュがヒットすると `npm ci` がスキップされる。  
このとき Chrome キャッシュが空だと、headless レンダリング (Mermaid 変換等) が失敗する。

以下のコマンドでビルド前に Chrome の存在を確認できる。

```bash
ls "${PUPPETEER_CACHE_DIR:-$HOME/.cache/puppeteer}/chrome" 2>/dev/null \
    || echo "Chrome not cached — puppeteer postinstall or manual download required"
```

`package-lock.json` が更新されると node_modules キャッシュが無効化され `npm ci` が再実行される。  
このとき puppeteer の対応 Chrome バージョンも変わる可能性があるため、ホスト永続ディレクトリを  
手動または CI 手順でクリアして Chrome を再取得させること。

### 初回投入・オフライン環境

オフライン環境で Chrome を事前配置する手順は [puppeteer-offline-chrome.md](puppeteer-offline-chrome.md) を参照。  
ダウンロード済みの `chrome/` および `chrome-headless-shell/` をホスト永続ディレクトリに配置すれば、  
コンテナー起動時にそのままマウントされて利用できる。

## 補足

### キャッシュが複数プロジェクトで競合する場合

同一エージェントで複数プロジェクトが `docsfw` を使う場合は、キャッシュ パスにプロジェクト識別子を加える。

```groovy
NODE_MODULES_CACHE_BASE = "/var/cache/${JOB_NAME.replaceAll('[^a-zA-Z0-9_-]', '_')}-node-modules"
```

### キャッシュ保存先ディレクトリの権限設定

Jenkins ユーザー (例: `jenkins`) に書き込み権限を付与する。

```bash
sudo mkdir -p /var/cache/docsfw-node-modules
sudo chown jenkins:jenkins /var/cache/docsfw-node-modules

sudo mkdir -p /var/cache/docsfw-puppeteer
sudo chown jenkins:jenkins /var/cache/docsfw-puppeteer
```

コンテナー エージェントで UID が `jenkins` と異なる場合は `chown <uid>:<gid>` で合わせる。

### GitHub Actions との比較

| 項目 | GitHub Actions | Jenkins Jenkinsfile | Jenkins フリースタイル |
|---|---|---|---|
| キャッシュ機構 | `actions/cache` (標準) | ホスト ファイル システム | ホスト ファイル システム |
| キャッシュ キー | `hashFiles(...)` | `md5sum` | `md5sum` |
| 有効期限管理 | 自動 (7 日) | `post` ブロックで削除 | ビルド後の処置で削除 |
| ステップ間変数渡し | 環境変数 | `env.` で設定 | 一時ファイル経由 |
| 動的エージェント対応 | 〇 | △ (固定エージェントのみ) | △ (固定エージェントのみ) |
| **Chrome キャッシュ** | `actions/cache` で `~/.cache/puppeteer` をキャッシュ | ホスト永続ディレクトリをコンテナーにマウント | ホスト永続ディレクトリをコンテナーにマウント |
