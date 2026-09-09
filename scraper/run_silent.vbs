Dim WshShell, FSO, scriptDir
Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
scriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.Run "cmd /c """ & scriptDir & "\run_daily.bat""", 0, False
