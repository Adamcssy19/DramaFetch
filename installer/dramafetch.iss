; DramaFetch Windows 安装包配置（Inno Setup 6）
; 界面为简体中文，采用 modern 向导风格。
; 版本号与目录由命令行传入：
;   ISCC.exe /DAppVersion=0.0.1+1 /DVersionInName=0.0.1 /DSourceDir=... /DOutputDir=... dramafetch.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef VersionInName
  #define VersionInName AppVersion
#endif
#ifndef SourceDir
  #define SourceDir "..\upstream\build\windows\x64\runner\Release"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif

#define AppName "DramaFetch"
#define AppExeName "dramafetch.exe"
#define AppPublisher "Adamcssy19"
#define AppUrl "https://github.com/Adamcssy19/DramaFetch"

[Setup]
AppId={{A7F3D2E1-9C4B-4E8A-B6D5-3F1A8C2E7B90}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}
AppUpdatesURL={#AppUrl}/releases
; 版本信息必须是四段式，补一个 0
VersionInfoVersion={#VersionInName}.0
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
; 现代化向导外观，接近 Windows 11 的视觉
WizardStyle=modern
WizardSizePercent=110
ShowLanguageDialog=no
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0
CloseApplications=yes
RestartApplications=no

[Languages]
; 中文语言文件随仓库提供，不依赖构建时的网络下载
Name: "cn"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："; Flags: checkedonce

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "立即运行 {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; 卸载前同样先结束程序，避免文件占用导致卸载不干净
Filename: "taskkill.exe"; Parameters: "/f /im {#AppExeName}"; Flags: runhidden

[Code]
// 安装前结束正在运行的程序：先请它自己退出并留出收尾时间，仍在运行则强制结束，
// 否则程序文件被占用会导致覆盖安装失败。
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Result := '';
  Exec('taskkill.exe', '/im {#AppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(2000);
  Exec('taskkill.exe', '/f /im {#AppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;
