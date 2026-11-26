[Setup]
AppId={{B52CEAB7-27A3-4AEA-AD64-E8B773A91BB4}
AppName=Gemini Thử Đồ
AppVersion=0.3.0
DefaultDirName={localappdata}\Programs\Gemini Thu Do
DefaultGroupName=Gemini Thử Đồ
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
OutputDir=..\try-on-installer
OutputBaseFilename=Gemini-Thu-Do-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\dist\Gemini-Thu-Do\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Gemini Thử Đồ"; Filename: "{app}\Gemini-Thu-Do.exe"

[Run]
Filename: "{app}\Gemini-Thu-Do.exe"; Description: "Mở Gemini Thử Đồ"; Flags: nowait postinstall skipifsilent
