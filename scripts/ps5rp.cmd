@echo off
REM ps5rp - run from the repository without installing anything.
REM Usage: scripts\ps5rp.cmd precheck   (or any other subcommand)
setlocal
set "PYTHONPATH=%~dp0"
where python >nul 2>nul && ( set "PY=python" ) || ( set "PY=py -3" )
%PY% -m ps5rp %*
exit /b %ERRORLEVEL%
