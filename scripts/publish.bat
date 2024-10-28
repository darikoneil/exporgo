@echo off

:: build
call build.bat

:: upload to pypi
python -m twine upload --repository pypi dist/* --config-file .pypirc
