@echo off
setlocal enabledelayedexpansion

:: ���s���̃o�b�`�t�@�C��������f�B���N�g�����擾
set "binFolder=%~dp0"

:: ������
set "workspaceFolder="
set "relativeFile="
set "configFile="

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

:: /configFile: �̏ꍇ
echo !arg! | findstr /b /c:"/configFile:" >nul && (
    set "c=!arg:/configFile:=!"
)

:: ���̈�����
shift
goto :parse_args

:end_parse

:: �������w�肳��Ă��Ȃ��ꍇ�̃G���[���b�Z�[�W
:: NOTE: �P��t�@�C�����[�h�̏ꍇ�A�����Ń`�F�b�N�A�E�g�����B
if "%workspaceFolder%"=="" (
    echo "Error: workspaceFolder does not set. Exiting."
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
if not "%configFile%"=="" (
    set "escapedConfigFile=%configFile:\=\\%"
)

:: �f�o�b�O�p�o��
rem echo Escaped Bin Folder: !escapedBinFolder!
rem echo Escaped Workspace Folder: !escapedWorkspaceFolder!
rem echo Escaped Relative File: !escapedRelativeFile!
rem echo Escaped Config File: !escapedConfigFile!

:: git.exe �̃p�X������
for /f "delims=" %%A in ('where git.exe') do (
    set "gitDir=%%~dpA"
    goto :gotgitdir
)

echo "Error: Git for Windows (Git Bash) does not found. Exiting."
exit /b 1

:gotgitdir
:: git.exe �̃p�X����Abash.exe �̃p�X��g�ݗ���
set "gitBin=%gitDir%..\bin"

:: �R�}���h�̑g�ݗ���
set command="%gitBin%\bash.exe" -i "%escapedBinFolder%pub_markdown_core.sh" --workspaceFolder="!escapedWorkspaceFolder!"

if "!escapedRelativeFile!"=="" (
    rem relativeFile ���^�����Ă��Ȃ��ꍇ
) else (
    rem relativeFile ���^�����Ă���ꍇ
    set command=!command! --relativeFile="!escapedRelativeFile!"
)

if "!escapedConfigFile!"=="" (
    rem configFile ���^�����Ă��Ȃ��ꍇ
) else (
    rem configFile ���^�����Ă���ꍇ
    set command=!command! --configFile="!escapedConfigFile!"
)

:: ���s���e���o��
rem echo !command!

:: �R�}���h�����s���߂�l���擾
!command!
set "returnCode=%ERRORLEVEL%"

:: �߂�l���Ăяo�����ɕԂ�
endlocal & exit /b %returnCode%