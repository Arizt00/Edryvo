#define AppVersion "0.5.2"
[Setup]
AppId={{842D0758-86C8-48DB-B6C5-035BE7E04AA1}
AppName=Lumen Studio
AppVersion={#AppVersion}
AppPublisher=Lumen Studio
DefaultDirName={localappdata}\Programs\LumenStudio
DefaultGroupName=Lumen Studio
PrivilegesRequired=lowest
OutputDir=..\..\dist\installers
OutputBaseFilename=LumenStudio-{#AppVersion}-Windows-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\lumen.exe
CloseApplications=yes
[Files]
Source: "..\..\dist\LumenStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Tasks]
Name: "desktopicon"; Description: "Crear un acceso en el escritorio"; Flags: unchecked
[Icons]
Name: "{group}\Lumen Studio"; Filename: "{app}\lumen.exe"
Name: "{autodesktop}\Lumen Studio"; Filename: "{app}\lumen.exe"; Tasks: desktopicon
Name: "{group}\Desinstalar Lumen Studio"; Filename: "{uninstallexe}"
[Run]
Filename: "{app}\lumen.exe"; Description: "Abrir Lumen Studio"; Flags: nowait postinstall skipifsilent
; No registry PATH changes. User configuration and projects are not removed.
; Sign with a publisher-owned certificate before public distribution.
