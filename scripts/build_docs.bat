@echo off

:: move to project root
cd ..

:: build docs
call docs\build_docs_build

:: build requirements for readthedocs
call docs\build_rtd_requirements
