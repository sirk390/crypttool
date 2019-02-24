; -- Example3.iss --
; Same as Example1.iss, but creates some registry entries too.

; SEE THE DOCUMENTATION FOR DETAILS ON CREATING .ISS SCRIPT FILES!

[Setup]
AppName=CryptTool
AppVersion=1.0
DefaultDirName={pf}\CryptTool
DefaultGroupName=CryptTool
UninstallDisplayIcon={app}\CryptTool.exe
OutputDir=installer

[Files]
Source: "dist/CryptTool/*"; DestDir: "{app}"

[Icons]
Name: "{group}\My Program"; Filename: "{app}\CryptTool.exe"

