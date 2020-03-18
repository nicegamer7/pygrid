echo off

rmdir /q /s dist
rmdir /q /s build

pyinstaller -w --icon ui\img\icon.ico pygrid.py

cd dist
"C:\Program Files\7-Zip\7z.exe" a pygrid.zip pygrid

rmdir /q /s pygrid
cd ..
rmdir /q /s build
del /q pygrid.spec
