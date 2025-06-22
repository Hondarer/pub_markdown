@echo off

setlocal
rem @set "spaces=    "
rem @echo %spaces%^> rsvg-convert %* >&2
node "%~dp0\rsvg-convert.js" %*
endlocal
