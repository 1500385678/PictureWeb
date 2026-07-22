' PictureWeb 自动启动(用相对路径,跟 vbs 所在目录)
' 2026-07-22 v2.0.3:加错误处理 + 写日志(双击没反应时能看到原因)
Option Explicit

Sub LaunchServer()
    On Error Resume Next
    Dim WshShell, fso, scriptDir, logFile, ts

    Set WshShell = CreateObject("WScript.Shell")
    Set fso = CreateObject("Scripting.FileSystemObject")
    scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
    logFile = scriptDir & "\logs\start_hidden.err.log"

    ' 确保 logs 目录存在
    fso.CreateFolder(scriptDir & "\logs")

    WshShell.CurrentDirectory = scriptDir
    WshShell.Run "python.exe -X utf8 """ & scriptDir & "\server.py""", 0, False

    If Err.Number <> 0 Then
        Set ts = fso.OpenTextFile(logFile, 8, True)  ' 8 = ForAppending
        ts.WriteLine Now() & " [ERR " & Err.Number & "] " & Err.Description
        ts.Close
        MsgBox "启动失败,日志见 " & logFile, vbExclamation, "PictureWeb"
    End If

    Set ts = Nothing
    Set fso = Nothing
    Set WshShell = Nothing
End Sub

LaunchServer
