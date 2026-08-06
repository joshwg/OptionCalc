' Launch the desktop app with no console window.
' Project root: Windows sees Z:\home\josh\projects\OptionCalculator, but WSL needs
' the POSIX path — Z: is a Windows mapping onto the WSL filesystem and is not
' mounted inside WSL itself.
Set objShell = CreateObject("WScript.Shell")
project = "/home/josh/projects/OptionCalculator"
objShell.Run "wsl -e bash -c ""cd " & project & " && PYTHONPATH=src venv/bin/python src/main.py 2>&1""", 0, False
