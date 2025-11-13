[Setup]
AppName=Ostia Client
AppVersion=1.0.0
DefaultDirName={pf}\OstiaClient
DefaultGroupName=Ostia Client
OutputBaseFilename=OstiaClientSetup-1.0.0
ArchitecturesInstallIn64BitMode=x64
Compression=lzma
SolidCompression=yes

[Files]
; Copia l'eseguibile nella cartella di installazione
Source: "dist\OstiaClient.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Icona nel menu Start
Name: "{autoprograms}\Ostia Client"; Filename: "{app}\OstiaClient.exe"
; Icona sul Desktop (opzionale, collegata a task)
Name: "{autodesktop}\Ostia Client"; Filename: "{app}\OstiaClient.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crea un'icona sul desktop"; GroupDescription: "Icone aggiuntive:"; Flags: unchecked
