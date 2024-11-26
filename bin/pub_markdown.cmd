@echo off
setlocal enabledelayedexpansion

:: 実行中のバッチファイルがあるディレクトリを取得
set "binFolder=%~dp0"

:: 初期化
set "workspaceFolder="
set "relativeFile="

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

:: 次の引数へ
shift
goto :parse_args

:end_parse

:: 引数が指定されていない場合のエラーメッセージ
if "%workspaceFolder%"=="" (
    echo "/workspaceFolder" が指定されていません。
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

:: デバッグ用出力
rem echo Escaped Bin Folder: !escapedBinFolder!
rem echo Escaped Workspace Folder: !escapedWorkspaceFolder!
rem echo Escaped Relative File: !escapedRelativeFile!

:: bash.exe のパスを検索
for /f "delims=" %%A in ('where git.exe') do (
    set "gitDir=%%~dpA"
    goto :gotgitdir
)

echo Not found Git for Windows.
exit

:gotgitdir
set "gitBin=%gitDir%..\bin"

:: bash.exe に渡す
if "!escapedRelativeFile!"=="" (
    rem relativeFile が与えられていない場合
    echo "%gitBin%\bash.exe" -i "%escapedBinFolder%pub_markdown_core.sh" --workspaceFolder="!escapedWorkspaceFolder!"
    "%gitBin%\bash.exe" -i "%escapedBinFolder%pub_markdown_core.sh" --workspaceFolder="!escapedWorkspaceFolder!"
) else (
    rem relativeFile が与えられている場合
    echo "%gitBin%\bash.exe" -i "%escapedBinFolder%pub_markdown_core.sh" --workspaceFolder="!escapedWorkspaceFolder!" --relativeFile="!escapedRelativeFile!"
    "%gitBin%\bash.exe" -i "%escapedBinFolder%pub_markdown_core.sh" --workspaceFolder="!escapedWorkspaceFolder!" --relativeFile="!escapedRelativeFile!"
)

endlocal
