; DramaFetch Windows 安装包配置（Inno Setup 6）
; 版本号与源目录由命令行传入：
;   ISCC.exe /DAppVersion=0.2.51+57 /DSourceDir=... /DOutputDir=... dramafetch.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\upstream\build\windows\x64\runner\Release"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif

#define AppName "DramaFetch"
#define AppPublisher "Adamcssy19"
#define AppExeName "dramafetch.exe"
#define AppUrl "https://github.com/Adamcssy19/DramaFetch"
; 文件名里不带构建号（由构建脚本传入，例如 0.0.1）
#ifndef VersionInName
  #define VersionInName AppVersion
#endif

[Setup]
AppId={{A7F3D2E1-9C4B-4E8A-B6D5-3F1A8C2E7B90}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}
AppUpdatesURL={#AppUrl}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes
OutputDir={#OutputDir}
OutputBaseFilename=DramaFetch-x64-{#VersionInName}-setup
SetupIconFile=..\overlay\windows\runner\resources\app_icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
#if FileExists(AddBackslash(CompilerPath) + "Languages\ChineseSimplified.isl")
Name: "cn"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式 / Create a desktop shortcut"; GroupDescription: "附加任务 / Additional tasks:"; Flags: checkedonce

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "立即启动 {#AppName} / Launch now"; Flags: nowait postinstall skipifsilent
