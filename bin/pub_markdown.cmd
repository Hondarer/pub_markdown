@echo off
setlocal enabledelayedexpansion

:: ���s���̃o�b�`�t�@�C��������f�B���N�g�����擾
set "binFolder=%~dp0"

:: ������
set "workspaceFolder="
set "relativeFile="

:: �������
:parse_args
if "%~1"=="" goto :end_parse
set "arg=%~1"

:: /workspaceFolder: �̏ꍇ
echo !arg! | findstr /b /c:"/workspaceFolder:" >nul && (
    set "workspaceFolder=!arg:/workspaceFolder:=!"
)

:: /relativeFile: �̏ꍇ
echo !arg! | findstr /b /c:"/relativeFile:" >nul && (
    set "relativeFile=!arg:/relativeFile:=!"
)

:: ���̈�����
shift
goto :parse_args

:end_parse

:: �������w�肳��Ă��Ȃ��ꍇ�̃G���[���b�Z�[�W
if "%workspaceFolder%"=="" (
    echo "/workspaceFolder" ���w�肳��Ă��܂���B
    exit /b 1
)

:: �t�H���_��؂�L�����G�X�P�[�v
:: Git bash �Ƀt�@�C���p�X��n���ہA��؂蕶����ϊ����Ă��珈�����Ȃ���
:: �G�X�P�[�v����Ă��܂����߁AWindows ���ɂĒu������
set "escapedBinFolder=%binFolder:\=\\%"
set "escapedWorkspaceFolder=%workspaceFolder:\=\\%"
if not "%relativeFile%"=="" (
    set "escapedRelativeFile=%relativeFile:\=\\%"
)

:: �f�o�b�O�p�o��
rem echo Escaped Bin Folder: !escapedBinFolder!
rem echo Escaped Workspace Folder: !escapedWorkspaceFolder!
rem echo Escaped Relative File: !escapedRelativeFile!

:: bash.exe �̃p�X������
for /f "delims=" %%A in ('where git.exe') do (
    set "gitDir=%%~dpA"
    goto :gotgitdir
)

echo Not found Git for Windows.
exit

:gotgitdir
set "gitBin=%gitDir%..\bin"

:: bash.exe �ɓn��
if "!escapedRelativeFile!"=="" (
    rem relativeFile ���^�����Ă��Ȃ��ꍇ
    echo "%gitBin%\bash.exe" -i "%escapedBinFolder%pub_markdown_core.sh" --workspaceFolder="!escapedWorkspaceFolder!"
    "%gitBin%\bash.exe" -i "%escapedBinFolder%pub_markdown_core.sh" --workspaceFolder="!escapedWorkspaceFolder!"
) else (
    rem relativeFile ���^�����Ă���ꍇ
    echo "%gitBin%\bash.exe" -i "%escapedBinFolder%pub_markdown_core.sh" --workspaceFolder="!escapedWorkspaceFolder!" --relativeFile="!escapedRelativeFile!"
    "%gitBin%\bash.exe" -i "%escapedBinFolder%pub_markdown_core.sh" --workspaceFolder="!escapedWorkspaceFolder!" --relativeFile="!escapedRelativeFile!"
)

endlocal
