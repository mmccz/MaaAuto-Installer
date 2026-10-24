; ============================================================================
; MaaAuto 在线引导包（约 2 MB，不内嵌 payload）
;
; 只做一件事：从 GitHub Release 下载完整安装包（带 SHA256 校验），
; 下载完成后交给它继续走向导。安装逻辑全部在完整包里，这里不复制一份。
;
; build_release.py 通过 /D 传入 MySetupUrl 与 MySetupSha256。
; ============================================================================

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#ifndef MyOutputDir
  #define MyOutputDir "..\dist"
#endif
#ifndef MyIcon
  #define MyIcon "..\resources\icon.ico"
#endif
#ifndef MySetupUrl
  #define MySetupUrl ""
#endif
#ifndef MySetupSha256
  #define MySetupSha256 ""
#endif
#ifndef MyOnlineBase
  #define MyOnlineBase "MaaAuto_Online_v" + MyAppVersion + "-Windows-x64"
#endif

[Setup]
AppId={{6F3A2C1E-8B4D-4E7A-9C15-3D02A7B9E4C1}
AppName=MaaAuto
AppVersion={#MyAppVersion}
AppVerName=MaaAuto {#MyAppVersion}
AppPublisher=mmccz
AppPublisherURL=https://github.com/mmccz/MaaAuto-Tool-works
DefaultDirName={autopf}\MaaAuto
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#MyOutputDir}
OutputBaseFilename={#MyOnlineBase}
SetupIconFile={#MyIcon}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
Uninstallable=no
CreateUninstallRegKey=no
UpdateUninstallLogAppName=no

[Languages]
Name: "cn"; MessagesFile: "languages\ChineseSimplified.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Messages]
cn.WelcomeLabel2=即将从 GitHub 下载 MaaAuto {#MyAppVersion} 安装包（约 100 MB）。%n%n下载完成后会自动启动安装向导。
en.WelcomeLabel2=This will download the MaaAuto {#MyAppVersion} installer (about 100 MB) from GitHub.%n%nThe setup wizard starts automatically after the download.

[Code]
var
  DownloadPage: TDownloadWizardPage;

procedure InitializeWizard();
begin
  DownloadPage := CreateDownloadPage(
    '正在下载 MaaAuto 安装包', '正在从 GitHub 获取，请稍候…', nil);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  SetupPath: String;
  ResultCode: Integer;
begin
  Result := True;
  if CurPageID <> wpReady then
    Exit;

  Result := False;

  if '{#MySetupUrl}' = '' then
  begin
    MsgBox('此在线安装包未配置下载地址，请改用完整安装包。', mbError, MB_OK);
    Exit;
  end;

  DownloadPage.Clear;
  DownloadPage.Add('{#MySetupUrl}', 'MaaAuto_Setup.exe', '{#MySetupSha256}');
  DownloadPage.Show;
  try
    try
      DownloadPage.Download;
    except
      MsgBox('下载失败，请检查网络后重试，或直接下载完整安装包。', mbError, MB_OK);
      Exit;
    end;
  finally
    DownloadPage.Hide;
  end;

  SetupPath := ExpandConstant('{tmp}\MaaAuto_Setup.exe');
  if not ShellExec('', SetupPath, '', '', SW_SHOW, ewNoWait, ResultCode) then
  begin
    MsgBox('无法启动安装程序：' + SetupPath, mbError, MB_OK);
    Exit;
  end;

  WizardForm.Close;
end;
