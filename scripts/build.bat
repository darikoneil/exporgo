@echo off

:: move to project root
cd ..

:: remove dist directory
rm -rf dist

:: re-add dist directory
mkdir dist

:: build
call python -m build

:: return to scripts directory
cd scripts
