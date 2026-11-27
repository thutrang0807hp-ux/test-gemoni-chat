[Setup]
AppId={{B52CEAB7-27A3-4AEA-AD64-E8B773A91BB4}
AppName=Gemini Tạo Ảnh
AppVersion=0.4.9
DefaultDirName={localappdata}\Programs\Gemini Thu Do
DefaultGroupName=Gemini Tạo Ảnh
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
OutputDir=..\try-on-installer
OutputBaseFilename=Gemini-Tao-Anh-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\dist\Gemini-Thu-Do\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Gemini Tạo Ảnh"; Filename: "{app}\Gemini-Thu-Do.exe"

[Run]
Filename: "{app}\Gemini-Thu-Do.exe"; Description: "Mở Gemini Tạo Ảnh"; Flags: nowait postinstall skipifsilent
