@echo off
cd /d "%USERPROFILE%\src\simpleWorkReporter"
"%USERPROFILE%\src\simpleWorkReporter\.venv\Scripts\python.exe" swr start >> "%USERPROFILE%\.simpleWorkReporter\server.log" 2>&1
