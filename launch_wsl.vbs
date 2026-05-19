Set objShell = CreateObject("WScript.Shell")
objShell.Run "wsl -e bash -c ""cd /mnt/c/Users/josh/Docs/lab/OptionCalculator && venv/bin/python main.py 2>&1""", 0, False
