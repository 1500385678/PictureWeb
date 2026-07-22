' PictureWeb 自动启动(用相对路径,跟 vbs 所在目录)
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptDir
WshShell.Run "python.exe -X utf8 """ & scriptDir & "\server.py""", 0, False
Set WshShell = Nothing
