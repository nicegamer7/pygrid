echo off
rem This batch file installs into python 3.5 env all packages required to run pygrid
call activate py35
call conda install qt pyqt pyserial pywin32 py
call pip install wmi pyinstaller
call deactivate
echo on