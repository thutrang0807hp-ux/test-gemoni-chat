[Setup]
AppId={{B2A2895D-F01E-40AF-858F-0CE6804F0745}
AppName=Gemini Tạo Ảnh - Thử tham chiếu
AppVersion=0.4.7
DefaultDirName={localappdata}\Programs\Gemini References Test
DefaultGroupName=Gemini Thử Tham Chiếu
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
OutputDir=..\try-on-installer
OutputBaseFilename=Gemini-Tao-Anh-References-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\dist\Gemini-Thu-Do\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Gemini Thử Tham Chiếu"; Filename: "{app}\Gemini-Thu-Do.exe"

[Run]
Filename: "{app}\Gemini-Thu-Do.exe"; Description: "Mở Gemini Tạo Ảnh"; Flags: nowait postinstall skipifsilent
