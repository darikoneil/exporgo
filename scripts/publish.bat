@echo off

:: move to project root
cd ..

:: upload to pypi
python -m twine upload --repository pypi dist/* --config-file .pypirc