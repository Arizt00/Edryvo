#define AppVersion "0.5.3"
[Setup]
AppId={{842D0758-86C8-48DB-B6C5-035BE7E04AA1}
AppName=Zénit
AppVersion={#AppVersion}
AppPublisher=Zénit
DefaultDirName={localappdata}\Programs\Zenit
DefaultGroupName=Zénit
PrivilegesRequired=lowest
OutputDir=..\..\dist\installers
OutputBaseFilename=Zenit-{#AppVersion}-R2-Windows-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\zenit.exe
CloseApplications=yes
[Files]
Source: "..\..\dist\Zenit\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Tasks]
Name: "desktopicon"; Description: "Crear un acceso en el escritorio"; Flags: unchecked
[Icons]
Name: "{group}\Zénit"; Filename: "{app}\zenit.exe"
Name: "{autodesktop}\Zénit"; Filename: "{app}\zenit.exe"; Tasks: desktopicon
Name: "{group}\Desinstalar Zénit"; Filename: "{uninstallexe}"
[Run]
Filename: "{app}\zenit.exe"; Description: "Abrir Zénit"; Flags: nowait postinstall skipifsilent
; No registry PATH changes. User configuration and projects are not removed.
; Sign with a publisher-owned certificate before public distribution.
