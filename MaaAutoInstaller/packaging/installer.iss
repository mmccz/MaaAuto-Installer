; ============================================================================
; MaaAuto 完整安装包（Inno Setup 6.5+）
;
; 由 build_release.py 调用，通过 /D 传入：
;   MyAppVersion / MyInstallerVersion / MyUpdateApi
;   MyPayloadPrefix / MyMinInstaller / MyPayloadDir / MyOutputDir
;   MyIcon / MySetupBase
;
; 语言文件：Inno Setup 官方 issrc 仓库的 ChineseSimplified.isl
; ============================================================================

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#ifndef MyInstallerVersion
  #define MyInstallerVersion "0.0.0"
#endif
#ifndef MyUpdateApi
  #define MyUpdateApi "https://api.github.com/repos/mmccz/MaaAuto-Tool-works/releases/latest"
#endif
#ifndef MyPayloadPrefix
  #define MyPayloadPrefix "MaaAuto_payload_v"
#endif
#ifndef MyMinInstaller
  #define MyMinInstaller "0.0.0"
#endif
#ifndef MyPayloadDir
  #define MyPayloadDir "..\_build\payload"
#endif
#ifndef MyOutputDir
  #define MyOutputDir "..\dist"
#endif
#ifndef MyIcon
  #define MyIcon "..\resources\icon.ico"
#endif
#ifndef MySetupBase
  #define MySetupBase "MaaAuto_Setup_v" + MyAppVersion + "-Windows-x64"
#endif

[Setup]
AppId={{6F3A2C1E-8B4D-4E7A-9C15-3D02A7B9E4C1}
AppName=MaaAuto
AppVersion={#MyAppVersion}
AppVerName=MaaAuto {#MyAppVersion}
AppPublisher=mmccz
AppPublisherURL=https://github.com/mmccz/MaaAuto-Tool-works
AppSupportURL=https://github.com/mmccz/MaaAuto-Tool-works/issues
AppUpdatesURL=https://github.com/mmccz/MaaAuto-Tool-works/releases
VersionInfoVersion={#MyAppVersion}
VersionInfoDescription=MaaAuto Setup
DefaultDirName={autopf}\MaaAuto
DefaultGroupName=MaaAuto
DisableProgramGroupPage=yes
DisableWelcomePage=no
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#MyOutputDir}
OutputBaseFilename={#MySetupBase}
SetupIconFile={#MyIcon}
UninstallDisplayIcon={app}\MaaAuto.exe
UninstallDisplayName=MaaAuto
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
AllowNoIcons=yes

[Languages]
Name: "cn"; MessagesFile: "languages\ChineseSimplified.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MyPayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\MaaAuto"; Filename: "{app}\MaaAuto.exe"
Name: "{group}\{cm:UninstallProgram,MaaAuto}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\MaaAuto"; Filename: "{app}\MaaAuto.exe"; Tasks: desktopicon

[Run]
; shellexec 必需：主程序 manifest 要求管理员，用 CreateProcess 直接起会报
; 「错误代码 740，请求的操作需要提升」。ShellExecute 会走 UAC。
Filename: "{app}\MaaAuto.exe"; Description: "{cm:LaunchProgram,MaaAuto}"; Flags: nowait postinstall skipifsilent shellexec

[Code]
procedure WriteManifest();
var
  Dir, DirEsc, UninstEsc, Json, ManifestPath, InstalledAt: String;
begin
  Dir := ExpandConstant('{app}');
  DirEsc := Dir;
  StringChangeEx(DirEsc, '\', '\\', True);
  { Inno 的卸载器固定叫 unins000.exe（不支持重命名），这里写真实路径 }
  UninstEsc := ExpandConstant('{uninstallexe}');
  StringChangeEx(UninstEsc, '\', '\\', True);
  InstalledAt := GetDateTimeString('yyyy-mm-dd hh:nn:ss', #0, #0);

  Json :=
    '{' + #13#10 +
    '  "version": "{#MyAppVersion}",' + #13#10 +
    '  "installer_version": "{#MyInstallerVersion}",' + #13#10 +
    '  "manifest_version": 3,' + #13#10 +
    '  "install_dir": "' + DirEsc + '",' + #13#10 +
    '  "app_exe": "' + DirEsc + '\\MaaAuto.exe",' + #13#10 +
    '  "uninstall_exe": "' + UninstEsc + '",' + #13#10 +
    '  "upgrade_exe": "' + DirEsc + '\\upgrade.exe",' + #13#10 +
    '  "requirements_hash": "",' + #13#10 +
    '  "mirror": "",' + #13#10 +
    '  "installed_at": "' + InstalledAt + '",' + #13#10 +
    '  "updated_at": "' + InstalledAt + '",' + #13#10 +
    '  "release_channel": "stable",' + #13#10 +
    '  "last_checked_at": "",' + #13#10 +
    '  "last_upgrade_from": "",' + #13#10 +
    '  "source_hash": "",' + #13#10 +
    '  "extra": {' + #13#10 +
    '    "github_url": "https://github.com/mmccz/MaaAuto-Tool-works",' + #13#10 +
    '    "update_api": "{#MyUpdateApi}",' + #13#10 +
    '    "release_channel": "stable",' + #13#10 +
    '    "launch_args": [],' + #13#10 +
    '    "payload_asset_prefix": "{#MyPayloadPrefix}",' + #13#10 +
    '    "min_installer_version": "{#MyMinInstaller}"' + #13#10 +
    '  }' + #13#10 +
    '}';

  ManifestPath := ExpandConstant('{app}\.maaauto.json');
  if not SaveStringToFile(ManifestPath, Json, False) then
    MsgBox('写入 .maaauto.json 失败，自动升级可能不可用。' + #13#10 + ManifestPath,
           mbError, MB_OK);
end;

{ 2.x 用 RUNASADMIN 兼容标志提权；3.0 改为 exe 内嵌 manifest。
  这里清理老版本可能残留的注册表项，避免重复提示。 }
procedure CleanLegacyRegistry();
var
  ExePath: String;
begin
  RegDeleteValue(HKCU,
    'Software\Microsoft\Windows\CurrentVersion\Run', 'MaaAuto');
  ExePath := ExpandConstant('{app}\MaaAuto.exe');
  RegDeleteValue(HKCU,
    'Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers', ExePath);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    WriteManifest();
    CleanLegacyRegistry();
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
  Purge: Boolean;
  ResultCode: Integer;
  I: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    CleanLegacyRegistry();

    { 先把主程序停掉：它可能正在运行并占用 _internal 里的 DLL，
      否则 Inno 删不掉文件，用户会看到「卸载没搞干净」。 }
    Exec(ExpandConstant('{cmd}'),
         '/c taskkill /F /IM MaaAuto.exe /T >nul 2>&1', '',
         SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(800);

    { /PURGEDATA 强制连用户数据一起删；否则询问，默认保留。
      卸载器里没有 CmdLineParamExists，用 ParamStr 遍历。 }
    Purge := False;
    for I := 1 to ParamCount do
      if CompareText(ParamStr(I), '/PURGEDATA') = 0 then
        Purge := True;

    if not Purge then
      Purge := SuppressibleMsgBox(
        '是否同时删除配置与日志？' + #13#10 +
        '选择“否”将保留 config 与 logs 目录，重新安装后可继续使用。',
        mbConfirmation, MB_YESNO, IDNO) = IDYES;

    if Purge then
    begin
      DataDir := ExpandConstant('{app}\config');
      DelTree(DataDir, True, True, True);
      DataDir := ExpandConstant('{app}\logs');
      DelTree(DataDir, True, True, True);
    end;
    DeleteFile(ExpandConstant('{app}\.maaauto.json'));
    { 升级残留的 .old exe 与临时目录 }
    DeleteFile(ExpandConstant('{app}\upgrade.exe.old'));
  end;
end;
