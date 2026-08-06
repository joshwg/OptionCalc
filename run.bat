@echo off
rem Project root. Windows sees it as Z:\home\josh\projects\OptionCalculator, but
rem WSL needs the POSIX path: Z: is a Windows mapping onto the WSL filesystem and
rem is not mounted inside WSL itself, so "cd z:\..." would fail in the shell below.
set "PROJECT=/home/josh/projects/OptionCalculator"

rem run via the virtual environment
wsl -e bash -c "cd %PROJECT% && PYTHONPATH=src venv/bin/python src/main.py 2>&1"
