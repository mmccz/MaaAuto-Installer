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
; Inno 的 VersionInfoVersion 只接受纯数字，预发布版本需要把 b1/rc1 剥掉
#ifndef MyVersionQuad
  #define MyVersionQuad "0.0.0.0"
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
VersionInfoVersion={#MyVersionQuad}
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

[CustomMessages]
cn.CreateStartMenuIcon=创建开始菜单快捷方式
en.CreateStartMenuIcon=Create a Start Menu shortcut

[Tasks]
; 开始菜单快捷方式做成可选项（1.0.6）：有些用户只用桌面图标/任务栏，不想被塞
; 开始菜单条目；默认勾选，保持老用户升级后的行为不变。
Name: "startmenuicon"; Description: "{cm:CreateStartMenuIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MyPayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\MaaAuto"; Filename: "{app}\MaaAuto.exe"; Tasks: startmenuicon
Name: "{group}\{cm:UninstallProgram,MaaAuto}"; Filename: "{uninstallexe}"; Tasks: startmenuicon
Name: "{autodesktop}\MaaAuto"; Filename: "{app}\MaaAuto.exe"; Tasks: desktopicon

; 卸载时兜底清掉开始菜单组。
;
; 实测（1.0.5 验证）：卸载器会删掉「卸载 MaaAuto」快捷方式，却经常把
; 「MaaAuto.lnk」和整个组目录留下（Inno 自己的卸载记录没能清掉，尤其是先升级
; 再卸载、或外壳正持有该目录句柄时）。这台机器上它过了几分钟才被系统回收，
; 用户当场看就是「卸载没干净」。直接 filesandordirs 删整个 {group} 目录，
; 反正这个目录只属于本程序。
[UninstallDelete]
Type: filesandordirs; Name: "{group}"

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

{ MaaAuto.exe 是否还在运行。
  卸载器有 ParamStr 但没有进程 API，这里用 tasklist + find 的退出码判断。 }
function IsAppRunning(): Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  if Exec(ExpandConstant('{cmd}'),
       '/c tasklist /FI "IMAGENAME eq MaaAuto.exe" /NH | find /I "MaaAuto.exe" >nul',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Result := (ResultCode = 0);
end;

{ 让正在运行的主程序优雅退出。

为什么要用 .upgrading 握手而不是直接 taskkill：
本安装包默认 per-user、卸载器**不提权**，而主程序 exe 的清单要求管理员。
低完整性进程 kill 不掉高完整性进程（taskkill 返回「拒绝访问」），
文件就删不干净——这正是用户反馈「卸载后还剩一堆东西」。
主程序每秒轮询 config\.upgrading，写这个文件它就会保存配置后自己退出，
既不需要 UAC，也不会留下半截状态。 }
function AskAppToExit(TimeoutMs: Integer): Boolean;
var
  FlagPath: String;
  Waited: Integer;
begin
  FlagPath := ExpandConstant('{app}\config\.upgrading');
  ForceDirectories(ExpandConstant('{app}\config'));
  SaveStringToFile(FlagPath, 'uninstall', False);

  Waited := 0;
  while (Waited < TimeoutMs) and IsAppRunning() do
  begin
    Sleep(300);
    Waited := Waited + 300;
  end;

  Result := not IsAppRunning();
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir, FlagPath: String;
  Purge: Boolean;
  ResultCode: Integer;
  I: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    CleanLegacyRegistry();

    { 先把主程序停掉：它可能正在运行并占用 _internal 里的 DLL，
      否则 Inno 删不掉文件，用户会看到「卸载没搞干净」。
      顺序：握手让主程序自己退出 → 还在就 taskkill（同权限下有效）→ 兜底提示。 }
    if IsAppRunning() then
    begin
      if not AskAppToExit(12000) then
      begin
        Exec(ExpandConstant('{cmd}'),
             '/c taskkill /F /IM MaaAuto.exe /T >nul 2>&1', '',
             SW_HIDE, ewWaitUntilTerminated, ResultCode);
        Sleep(1000);
      end;
    end;

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
    end
    else
    begin
      { 保留用户数据时要清掉握手文件，否则重装后主程序一启动就自己退出 }
      DeleteFile(ExpandConstant('{app}\config\.upgrading'));
    end;

    DeleteFile(ExpandConstant('{app}\.maaauto.json'));
    { 升级残留的 .old exe 与临时目录 }
    DeleteFile(ExpandConstant('{app}\upgrade.exe.old'));

    { 进程真的没退掉时明确告诉用户，而不是留下半截目录 }
    if IsAppRunning() then
      MsgBox('MaaAuto 仍在运行，可能无法结束它（权限不足）。' + #13#10 +
             '请手动退出程序后重新卸载，否则部分文件会残留。',
             mbError, MB_OK);
  end;
end;
