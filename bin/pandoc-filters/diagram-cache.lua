-- diagram-cache.lua
-- インライン PlantUML / Mermaid が docx 出力用に生成する画像の共有キャッシュ。
--
-- 画像のファイル名は図のソースのハッシュだけで決まり、言語や詳細度に依存しない。
-- そのため、発行先 (pages/<バリアント>/html) ではなく発行対象外の 1 か所へ集約すれば、
-- バリアントと実行をまたいで再利用できる。
--
-- 生成は最大 MAX_PARALLEL 個の pandoc プロセスが並行して行うため、
-- 作業用のパスへ生成してから os.rename で最終パスへ確定する。
-- 最終パスには完成品しか存在しないため、存在確認をそのまま完成の判定として使用できる。

local M = {}

-- Windows で非 ASCII を含むパスを扱うための変換関数。
-- 呼び出し側のフィルターが持つ実装を init で受け取る。
local to_cp = function(text) return text end

local initialized = false
local final_dir = nil   -- 完成した画像の格納先 (絶対パス)。キャッシュ無効時は nil
local tmp_dir = nil     -- 作業用ディレクトリ。キャッシュ無効時は nil
local hits_path = nil   -- このプロセスの参照記録ファイル。記録しない場合は nil

local ensured_dirs = {}

local function is_windows()
    local os_name = os.getenv("OS")
    return (os_name and string.match(os_name:lower(), "windows")) and true or false
end

local function exists(path)
    if path == nil or path == "" then
        return false
    end
    local f = io.open(to_cp(path), "r")
    if f == nil then
        return false
    end
    f:close()
    return true
end

local function mkdir_p(path)
    local _path = to_cp(path)
    if is_windows() then
        os.execute("mkdir \"" .. string.gsub(_path, "/", "\\") .. "\" >nul 2>&1")
    else
        os.execute("mkdir -p \"" .. _path .. "\"")
    end
end

--- ディレクトリを作成する。プロセス内で作成済みのものは再実行しない。
local function ensure_dir(path)
    if path == nil or path == "" or ensured_dirs[path] then
        return
    end
    mkdir_p(path)
    ensured_dirs[path] = true
end

--- 並行プロセス間で衝突しない接尾辞を作る。
--- Lua 5.4 の math.random はプロセスごとに自動で種が変わる。
local function unique_suffix()
    return string.format("%d_%d", os.time(), math.random(100000000, 999999999))
end

local function strip_trailing_separator(path)
    return (path:gsub("[/\\]+$", ""))
end

--- キャッシュを初期化する。
--- to_cp_fn には呼び出し元の utf8_to_active_cp を渡す。
--- DOCSFW_DIAGRAM_CACHE_DIR が未設定の場合、キャッシュは無効になり、
--- 呼び出し元は --resource-path の先頭へ画像を生成する。
function M.init(to_cp_fn)
    if to_cp_fn then
        to_cp = to_cp_fn
    end
    if initialized then
        return
    end
    initialized = true

    local root = os.getenv("DOCSFW_DIAGRAM_CACHE_DIR")
    if root == nil or root == "" then
        return
    end
    root = strip_trailing_separator(root)

    -- 画像はキャッシュ ルート直下に置く。tmp と hits はディレクトリなので混ざらない。
    final_dir = root
    tmp_dir = root .. "/tmp"
    ensure_dir(final_dir)
    ensure_dir(tmp_dir)

    local hits_dir = os.getenv("DOCSFW_DIAGRAM_CACHE_HITS_DIR")
    if hits_dir ~= nil and hits_dir ~= "" then
        hits_dir = strip_trailing_separator(hits_dir)
        ensure_dir(hits_dir)
        hits_path = hits_dir .. "/" .. unique_suffix() .. ".hits"
    end
end

--- 完成した画像の格納先を返す。キャッシュが無効な場合は nil を返す。
function M.dir()
    return final_dir
end

--- 作業用ファイルのパスを返す。
--- キャッシュが無効な場合は fallback_dir の配下に作る。
--- rename で確定するため、最終パスと同じファイル システム上である必要がある。
function M.tempfile(name, fallback_dir)
    local base = tmp_dir or fallback_dir or "."
    ensure_dir(base)
    return base .. "/" .. name .. ".tmp." .. unique_suffix()
end

--- 作業用ディレクトリを作成して返す。破棄は呼び出し側が remove_dir で行う。
function M.tempdir(fallback_dir)
    local base = tmp_dir or fallback_dir or "."
    ensure_dir(base)
    local path = base .. "/work." .. unique_suffix()
    mkdir_p(path)
    return path
end

function M.remove_dir(path)
    if path == nil or path == "" then
        return
    end
    local _path = to_cp(path)
    if is_windows() then
        os.execute("rmdir /s /q \"" .. string.gsub(_path, "/", "\\") .. "\" >nul 2>&1")
    else
        os.execute("rm -rf \"" .. _path .. "\"")
    end
end

--- 作業用ファイルを最終パスへ確定する。
--- POSIX の rename は不可分に置換するため、読み取り側が途中状態を参照することはない。
--- Windows の rename は既存ファイルがあると失敗するので、
--- 競合した別プロセスが先に完成させていた場合は、その結果を採用する。
function M.commit(temp_path, final_path)
    if not exists(temp_path) then
        return false
    end
    if os.rename(to_cp(temp_path), to_cp(final_path)) then
        return true
    end
    if exists(final_path) then
        os.remove(to_cp(temp_path))
        return true
    end
    os.remove(to_cp(temp_path))
    return false
end

--- 参照した画像を記録する。
--- 実行の最後にまとめて mtime を更新することで、
--- 一定期間参照されなかった画像だけが prune の対象になる。
function M.hit(final_path)
    if hits_path == nil or final_dir == nil or final_path == nil then
        return
    end
    local prefix = final_dir .. "/"
    if final_path:sub(1, #prefix) ~= prefix then
        return
    end
    local f = io.open(to_cp(hits_path), "a")
    if f == nil then
        return
    end
    f:write(final_path:sub(#prefix + 1), "\n")
    f:close()
end

return M
