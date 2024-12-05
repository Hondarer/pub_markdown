@echo off
setlocal enabledelayedexpansion

:: 実行中のバッチファイルがあるディレクトリを取得
set "binFolder=%~dp0"

:: 初期化
set "workspaceFolder="
set "relativeFile="
set "configFile="

:: 引数解析
:parse_args
if "%~1"=="" goto :end_parse
set "arg=%~1"

:: /workspaceFolder: の場合
echo !arg! | findstr /b /c:"/workspaceFolder:" >nul && (
    set "workspaceFolder=!arg:/workspaceFolder:=!"
)

:: /relativeFile: の場合
echo !arg! | findstr /b /c:"/relativeFile:" >nul && (
    set "relativeFile=!arg:/relativeFile:=!"
)

:: /configFile: の場合
echo !arg! | findstr /b /c:"/configFile:" >nul && (
    set "c=!arg:/configFile:=!"
)

:: 次の引数へ
shift
goto :parse_args

:end_parse

:: 引数が指定されていない場合のエラーメッセージ
:: NOTE: 単一ファイルモードの場合、ここでチェックアウトされる。
if "%workspaceFolder%"=="" (
    echo "Error: workspaceFolder does not set. Exiting."
    exit /b 1
)

:: フォルダ区切り記号をエスケープ
:: Git bash にファイルパスを渡す際、区切り文字を変換してから処理しないと
:: エスケープされてしまうため、Windows 側にて置換する
set "escapedBinFolder=%binFolder:\=\\%"
set "escapedWorkspaceFolder=%workspaceFolder:\=\\%"
if not "%relativeFile%"=="" (
    set "escapedRelativeFile=%relativeFile:\=\\%"
)
if not "%configFile%"=="" (
    set "escapedConfigFile=%configFile:\=\\%"
)

:: デバッグ用出力
rem echo Escaped Bin Folder: !escapedBinFolder!
rem echo Escaped Workspace Folder: !escapedWorkspaceFolder!
rem echo Escaped Relative File: !escapedRelativeFile!
rem echo Escaped Config File: !escapedConfigFile!

:: git.exe のパスを検索
for /f "delims=" %%A in ('where git.exe') do (
    set "gitDir=%%~dpA"
    goto :gotgitdir
)

echo "Error: Git for Windows (Git Bash) does not found. Exiting."
exit /b 1

:gotgitdir
:: git.exe のパスから、bash.exe のパスを組み立て
set "gitBin=%gitDir%..\bin"

:: コマンドの組み立て
set command="%gitBin%\bash.exe" -i "%escapedBinFolder%pub_markdown_core.sh" --workspaceFolder="!escapedWorkspaceFolder!"

if "!escapedRelativeFile!"=="" (
    rem relativeFile が与えられていない場合
) else (
    rem relativeFile が与えられている場合
    set command=!command! --relativeFile="!escapedRelativeFile!"
)

if "!escapedConfigFile!"=="" (
    rem configFile が与えられていない場合
) else (
    rem configFile が与えられている場合
    set command=!command! --configFile="!escapedConfigFile!"
)

:: 実行内容を出力
rem echo !command!

:: コマンドを実行し戻り値を取得
!command!
set "returnCode=%ERRORLEVEL%"

:: 戻り値を呼び出し元に返す
endlocal & exit /b %returnCode%