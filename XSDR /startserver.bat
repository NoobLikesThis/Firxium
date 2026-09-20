@echo off
cls

echo Starting injector setup...

echo.
echo Loading, please wait...
for /L %%i in (1,1,3) do (
    <nul set /p =.
    ping -n 2 127.0.0.1 >NUL
)

cls

echo Checking Python dependencies...


echo.
py -c "import flask" 2>NUL || py -m pip install flask
py -c "import requests" 2>NUL || py -m pip install requests
py -c "import pymem" 2>NUL || py -m pip install pymem
py -c "import psutil" 2>NUL || py -m pip install psutil
py -c "import subprocess" 2>NUL || py -m pip install subprocess


echo.
echo Launching Injector.py...
py Injector.py
pause
