@echo off
cd /d "%~dp0"
py -3 -c "import cryptography" >nul 2>&1
if errorlevel 1 py -3 -m pip install -r requirements.txt
if errorlevel 1 goto failed
py -3 giai_ma.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo Can cai Python 3 co Tcl/Tk va Python Launcher, sau do mo lai cong cu.
pause
exit /b 1
