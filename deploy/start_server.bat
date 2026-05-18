@echo off
cd /d "%USERPROFILE%\src\simpleWorkReporter"
"%USERPROFILE%\src\simpleWorkReporter\.venv\Scripts\python.exe" start_server >> "%USERPROFILE%\.simpleWorkReporter\server.log" 2>&1
