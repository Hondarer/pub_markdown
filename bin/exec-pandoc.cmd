@echo off
setlocal

REM Git bash にファイルパスを渡す際、区切り文字を変換してから処理しないと
REM エスケープされてしまうため、Windows 側にて置換する処理

REM 引数からファイル名を取得
set "filename=%~1"

REM ファイル名のパス区切り文字を置換
set "unescaped=%filename:\=/%"

bash.exe -i bin/exec-pandoc.sh --target="%unescaped%"

endlocal