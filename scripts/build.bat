@echo off

:: move to project root
cd ..

:: build
call python -m build

:: return to scripts directory
cd scripts
