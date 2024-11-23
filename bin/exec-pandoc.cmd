@echo off
setlocal

rem Git bash にファイルパスを渡す際、区切り文字を変換してから処理しないと
rem エスケープされてしまうため、Windows 側にて置換する処理

rem 引数からファイル名を取得
set "filename=%~1"

rem ファイル名のパス区切り文字を置換
set "unescaped=%filename:\=/%"

rem Git for windows がインストールされているものとして相対的に bash.exe が存在するディレクトリを得る
rem TODO: WSL がインストールされている環境であれば、WSL の bash を利用できるはずだが、未実装。必要時はここでパスを得る。

rem bash.exe のパスを検索
for /f "delims=" %%A in ('where git.exe') do (
    set "gitDir=%%~dpA"
    goto :gotgitdir
)

echo Not found Git for Windows.
exit

:gotgitdir
set "gitBin=%gitDir%..\bin"

rem echo The directory of git-bin (in bash.exe) is: %gitBin%
rem exit

if "%filename%"=="" (
    rem 引数が与えられていない場合
    "%gitBin%\bash.exe" -i bin/exec-pandoc.sh
) else (
    rem 引数が与えられている場合
    "%gitBin%\bash.exe" -i bin/exec-pandoc.sh --target="%unescaped%"
)

endlocal