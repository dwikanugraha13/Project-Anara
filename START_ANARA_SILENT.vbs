' Project Anara - Silent Background Launcher
' Anara Standard Background Service Launcher
Option Explicit
Dim sh, fso, rootDir, backendDir, frontendDir, logDir, runDir
Dim pythonExe, npmCmd, backendCmd, frontendCmd, localAppData, env, tunnelCmd

Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

rootDir = fso.GetParentFolderName(WScript.ScriptFullName)
backendDir = rootDir & "\backend"
frontendDir = rootDir & "\frontend"

localAppData = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%")
logDir = localAppData & "\anara\logs"
runDir = localAppData & "\anara\run"

If Not fso.FolderExists(localAppData & "\anara") Then fso.CreateFolder(localAppData & "\anara")
If Not fso.FolderExists(logDir) Then fso.CreateFolder(logDir)
If Not fso.FolderExists(runDir) Then fso.CreateFolder(runDir)

' 1. Resolve Python executable
pythonExe = "python.exe"
If fso.FileExists(backendDir & "\venv\Scripts\python.exe") Then
    pythonExe = backendDir & "\venv\Scripts\python.exe"
ElseIf fso.FileExists(backendDir & "\.venv\Scripts\python.exe") Then
    pythonExe = backendDir & "\.venv\Scripts\python.exe"
ElseIf fso.FileExists(localAppData & "\Programs\Python\Python312\python.exe") Then
    pythonExe = localAppData & "\Programs\Python\Python312\python.exe"
ElseIf fso.FileExists(localAppData & "\Programs\Python\Python311\python.exe") Then
    pythonExe = localAppData & "\Programs\Python\Python311\python.exe"
End If

' 2. Resolve npm.cmd
npmCmd = "npm.cmd"
If fso.FileExists("C:\Program Files\nodejs\npm.cmd") Then
    npmCmd = "C:\Program Files\nodejs\npm.cmd"
ElseIf fso.FileExists("C:\Program Files (x86)\nodejs\npm.cmd") Then
    npmCmd = "C:\Program Files (x86)\nodejs\npm.cmd"
ElseIf fso.FileExists(localAppData & "\Programs\nodejs\npm.cmd") Then
    npmCmd = localAppData & "\Programs\nodejs\npm.cmd"
ElseIf fso.FileExists(sh.ExpandEnvironmentStrings("%APPDATA%") & "\npm\npm.cmd") Then
    npmCmd = sh.ExpandEnvironmentStrings("%APPDATA%") & "\npm\npm.cmd"
End If

' 3. Set environment
Set env = sh.Environment("PROCESS")
env.Item("PYTHONIOENCODING") = "utf-8"
env.Item("PYTHONPATH") = backendDir
env.Item("ANARA_SILENT_DAEMON") = "1"

' 4. Launch Backend quietly (Port 8000)
sh.CurrentDirectory = backendDir
backendCmd = "cmd.exe /c """"" & pythonExe & """ main.py > """ & logDir & "\backend.log"" 2>&1"""
sh.Run backendCmd, 0, False

' 5. Launch Frontend quietly (Port 3000)
sh.CurrentDirectory = frontendDir
frontendCmd = "cmd.exe /c """"" & npmCmd & """ run dev > """ & logDir & "\frontend.log"" 2>&1"""
sh.Run frontendCmd, 0, False

' 6. Launch Cloudflare Tunnel quietly (anara.my.id)
sh.CurrentDirectory = rootDir
tunnelCmd = "cmd.exe /c """"" & pythonExe & """ cli.py gateway tunnel > """ & logDir & "\tunnel_init.log"" 2>&1"""
sh.Run tunnelCmd, 0, False

' 7. Windows notification dialog (auto-closes after 6s)
sh.Popup "Project Anara successfully started in background (Silent Daemon)!" & vbCrLf & vbCrLf & _
         "• Backend API : http://localhost:8000" & vbCrLf & _
         "• 3D Studio   : http://localhost:3000" & vbCrLf & _
         "• Code Studio : http://localhost:3000/code" & vbCrLf & _
         "• Remote URL  : https://anara.my.id" & vbCrLf & vbCrLf & _
         "Status & Log  : %LOCALAPPDATA%\anara\logs\" & vbCrLf & _
         "To stop       : run STOP_ANARA.bat or 'python cli.py daemon stop'", 6, "Anara 3D AI Assistant", 64
