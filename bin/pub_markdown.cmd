@echo off
setlocal enabledelayedexpansion

:: ���̃o�b�`�t�@�C��������f�B���N�g�����擾
set "binFolder=%~dp0"

:: ������
set "workspaceFolder="
set "relativeFile="
set "configFile="
set "options="

:: �������
:parse_args
set "arg=%~1"
if not defined arg goto :end_parse

:: /workspaceFolder: �̏ꍇ
echo !arg! | findstr /b /c:"/workspaceFolder:" >nul && (
    set "workspaceFolder=!arg:/workspaceFolder:=!"
    set "workspaceFolder=!workspaceFolder:"=!"
)

:: /relativeFile: �̏ꍇ
echo !arg! | findstr /b /c:"/relativeFile:" >nul && (
    set "relativeFile=!arg:/relativeFile:=!"
    set "relativeFile=!relativeFile:"=!"
)

:: /configFile: �̏ꍇ
echo !arg! | findstr /b /c:"/configFile:" >nul && (
    set "configFile=!arg:/configFile:=!"
    set "configFile=!configFile:"=!"
)

:: /details: �̏ꍇ
echo !arg! | findstr /b /c:"/details:" >nul && (
    set "options=%options%--details=!arg:/details:=! "
)

:: /lang: �̏ꍇ
echo !arg! | findstr /b /c:"/lang:" >nul && (
    set "options=%options%--lang=!arg:/lang:=! "
)

:: /docx: �̏ꍇ
echo !arg! | findstr /b /c:"/docx:" >nul && (
    set "options=%options%--docx=!arg:/docx:=! "
)

:: ���̈�����
shift
goto :parse_args

:end_parse

:: �������w�肳��Ă��Ȃ��ꍇ�̃G���[���b�Z�[�W
if "!workspaceFolder!"=="" (
    echo Error: workspaceFolder does not set. Exiting.
    exit /b 1
)

:: �t�H���_��؂�L�����G�X�P�[�v
:: Git bash �Ƀt�@�C���p�X��n���ہA��؂蕶����ϊ����Ă��珈�����Ȃ���
:: �G�X�P�[�v����Ă��܂����߁AWindows ���ɂĒu������
set "escapedBinFolder=!binFolder:\=/!"
set "escapedWorkspaceFolder=!workspaceFolder:\=/!"
if not "!relativeFile!"=="" (
    set "escapedRelativeFile=!relativeFile:\=/!"
)
if not "!configFile!"=="" (
    set "escapedConfigFile=!configFile:\=/!"
)

:: �f�o�b�O�p�o��
rem echo Escaped Bin Folder: !escapedBinFolder!
rem echo Escaped Workspace Folder: !escapedWorkspaceFolder!
rem echo Escaped Relative File: !escapedRelativeFile!
rem echo Escaped Config File: !escapedConfigFile!
rem echo Options: !options!

:: git.exe �̃p�X������
for /f "delims=" %%A in ('where git.exe 2^>nul') do (
    set "gitDir=%%~dpA"
    goto :gotgitdir
)

echo Error: Git for Windows ^(Git Bash^) does not found. Exiting.
exit /b 1

:gotgitdir
:: git.exe �̃p�X����Abash.exe �̃p�X��g�ݗ���
set "gitBin=!gitDir!..\bin"

:: �R�}���h�̑g�ݗ���
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

:: ���s���e���o��
rem echo !command!

:: �R�}���h�����s���߂�l���擾
!command!
set "returnCode=!ERRORLEVEL!"

:: �߂�l��ێ����I��
endlocal & exit /b !returnCode!
