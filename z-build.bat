echo off
rem The main dev environment was 3.6.1, but pyinstaller worked only with python 3.5 at the time of writing.
rem This batch file switches temporarily to python 3.5 env, runs pyinstaller, and switches back
call activate py35
rmdir /q /s dist
rmdir /q /s build
call pyinstaller -F -w --icon ui\img\icon.ico pygrid.py
rem call pyinstaller -w --icon ui\img\icon.ico pygrid.py
call deactivate
echo on