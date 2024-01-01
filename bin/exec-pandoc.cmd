@echo off
setlocal

REM Git bash にファイルパスを渡す際、区切り文字を変換してから処理しないと
REM エスケープされてしまうため、Windows 側にて置換する処理

REM 引数からファイル名を取得
set "filename=%~1"

REM ファイル名のパス区切り文字を置換
set "unescaped=%filename:\=/%"

REM Git Bash がインストールされていて WSL がセットアップされていない環境における警告メッセージの回避
REM
REM Linux 用 Windows サブシステムには、ディストリビューションがインストールされていません。

REM bash.exeのパスを検索
for /f "delims=" %%a in ('where bash.exe') do set "bashpath=%%a"

REM C:\Windows\System32\bash.exe が最初に見つかるかどうか確認
if "%bashpath%"=="C:\Windows\System32\bash.exe" (
    REM echo Found only C:\Windows\System32\bash.exe
) else (
    REM 他のパスが見つかった場合、そのパスを使用
    REM echo Found another bash.exe: %bashpath%
)

if "%filename%"=="" (
    REM 引数が与えられていない場合
    "%bashpath%" -i bin/exec-pandoc.sh
) else (
    REM 引数が与えられている場合
    "%bashpath%" -i bin/exec-pandoc.sh --target="%unescaped%"
)

endlocal