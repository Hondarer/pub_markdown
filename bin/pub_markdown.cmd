@echo off
setlocal enabledelayedexpansion

:: このバッチファイルがあるディレクトリを取得
set "binFolder=%~dp0"

:: 初期化
set "workspaceFolder="
set "relativeFile="
set "configFile="
set "options="

:: 引数解析
:parse_args
set "arg=%~1"
if not defined arg goto :end_parse

:: /workspaceFolder: の場合
echo !arg! | findstr /b /c:"/workspaceFolder:" >nul && (
    set "workspaceFolder=!arg:/workspaceFolder:=!"
    set "workspaceFolder=!workspaceFolder:"=!"
)

:: /relativeFile: の場合
echo !arg! | findstr /b /c:"/relativeFile:" >nul && (
    set "relativeFile=!arg:/relativeFile:=!"
    set "relativeFile=!relativeFile:"=!"
)

:: /configFile: の場合
echo !arg! | findstr /b /c:"/configFile:" >nul && (
    set "configFile=!arg:/configFile:=!"
    set "configFile=!configFile:"=!"
)

:: /details: の場合
echo !arg! | findstr /b /c:"/details:" >nul && (
    set "options=%options%--details=!arg:/details:=! "
)

:: 次の引数へ
shift
goto :parse_args

:end_parse

:: 引数が指定されていない場合のエラーメッセージ
if "!workspaceFolder!"=="" (
    echo Error: workspaceFolder does not set. Exiting.
    exit /b 1
)

:: フォルダ区切り記号をエスケープ
:: Git bash にファイルパスを渡す際、区切り文字を変換してから処理しないと
:: エスケープされてしまうため、Windows 側にて置換する
set "escapedBinFolder=!binFolder:\=/!"
set "escapedWorkspaceFolder=!workspaceFolder:\=/!"
if not "!relativeFile!"=="" (
    set "escapedRelativeFile=!relativeFile:\=/!"
)
if not "!configFile!"=="" (
    set "escapedConfigFile=!configFile:\=/!"
)

:: デバッグ用出力
rem echo Escaped Bin Folder: !escapedBinFolder!
rem echo Escaped Workspace Folder: !escapedWorkspaceFolder!
rem echo Escaped Relative File: !escapedRelativeFile!
rem echo Escaped Config File: !escapedConfigFile!
rem echo Options: !options!

:: git.exe のパスを検索
for /f "delims=" %%A in ('where git.exe 2^>nul') do (
    set "gitDir=%%~dpA"
    goto :gotgitdir
)

echo Error: Git for Windows ^(Git Bash^) does not found. Exiting.
exit /b 1

:gotgitdir
:: git.exe のパスから、bash.exe のパスを組み立て
set "gitBin=!gitDir!..\bin"

:: コマンドの組み立て
set "command="!gitBin!\bash.exe" -i "!escapedBinFolder!pub_markdown_core.sh" --workspaceFolder="!escapedWorkspaceFolder!""

if not "!relativeFile!"=="" (
    set "command=!command! --relativeFile="!escapedRelativeFile!""
)

if not "!configFile!"=="" (
    set "command=!command! --configFile="!escapedConfigFile!""
)

if not "!options!"=="" (
    set "command=!command! !options!"
)

:: 実行内容を出力
rem echo !command!

:: コマンドを実行し戻り値を取得
!command!
set "returnCode=!ERRORLEVEL!"

:: 戻り値を保持し終了
endlocal & exit /b !returnCode!
