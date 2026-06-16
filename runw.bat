
rem run via the virtual environment
wsl -e bash -c "cd /mnt/c/Users/josh/Docs/lab/OptionCalculator && PYTHONPATH=src OPTION_PWD=test PORT=5000 venv/bin/python src/main_web.py 2>&1"
