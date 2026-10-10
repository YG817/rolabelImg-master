#ifndef AppVersion
  #error Pass /DAppVersion=x.y.z to ISCC
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\roLabelImg"
#endif
#ifndef OutputDir
  #define OutputDir "..\release"
#endif

[Setup]
; This identity MUST remain unchanged in all future releases.
AppId={{C5A4A2D8-A96A-450E-9B52-6E0D65BE1D37}
AppName=roLabelImg
AppVersion={#AppVersion}
AppPublisher=YG817
AppPublisherURL=https://github.com/YG817/rolabelImg-master
AppUpdatesURL=https://github.com/YG817/rolabelImg-master/releases/latest
DefaultDirName={localappdata}\Programs\roLabelImg
DefaultGroupName=roLabelImg
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename=roLabelImg-Setup-{#AppVersion}-win-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\icons\roLabelImg.ico
UninstallDisplayIcon={app}\roLabelImg.exe
UsePreviousAppDir=yes
DisableProgramGroupPage=yes
CloseApplications=no
RestartApplications=no
AppMutex=Local\roLabelImg-running

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Only bundled runtime files; never put user data inside _internal.
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{group}\roLabelImg"; Filename: "{app}\roLabelImg.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\roLabelImg"; Filename: "{app}\roLabelImg.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\roLabelImg.exe"; Description: "Launch roLabelImg"; Flags: nowait postinstall skipifsilent

; No deletion of AppData, annotations or user image folders on update/uninstall.
