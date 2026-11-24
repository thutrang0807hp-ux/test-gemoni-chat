#define AppVersion "0.2.0"

[Setup]
AppId={{FB747BF4-CA09-4B2E-94C1-C489DECA857C}
AppName=Studio Ảnh Gemini
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\Studio Anh Gemini
DefaultGroupName=Studio Ảnh Gemini
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
OutputDir=..\installer
OutputBaseFilename=Studio-Anh-Gemini-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\dist\Studio-Anh-Gemini\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Studio Ảnh Gemini"; Filename: "{app}\Studio-Anh-Gemini.exe"

[Run]
Filename: "{app}\Studio-Anh-Gemini.exe"; Description: "Mở Studio Ảnh Gemini"; Flags: nowait postinstall skipifsilent
