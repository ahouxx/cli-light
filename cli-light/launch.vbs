' CLI Light launcher (auto-generated)
Set shell = CreateObject("WScript.Shell")
Set fso   = CreateObject("Scripting.FileSystemObject")

scriptDir  = fso.GetParentFolderName(WScript.ScriptFullName)
mainScript = fso.BuildPath(scriptDir, "cli_light.py")

pythonw = ""
' Scan %LOCALAPPDATA%\Programs\Python for any Python3* install
localPy = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\"
If fso.FolderExists(localPy) Then
    For Each folder In fso.GetFolder(localPy).SubFolders
        pyPath = folder.Path & "\pythonw.exe"
        If fso.FileExists(pyPath) Then
            pythonw = pyPath
            Exit For
        End If
    Next
End If

' Check common root installs
If pythonw = "" Then
    For Each ver In Array("314","313","312","311","310","39","38")
        testPath = "C:\Python" & ver & "\pythonw.exe"
        If fso.FileExists(testPath) Then
            pythonw = testPath
            Exit For
        End If
    Next
End If

' Fall back to PATH
If pythonw = "" Then
    pythonw = "pythonw.exe"
End If

shell.Run """" & pythonw & """ """ & mainScript & """", 0, False
