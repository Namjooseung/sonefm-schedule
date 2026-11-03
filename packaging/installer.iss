; SoneFM 편성표 설치 파일 (Inno Setup 6)
; 만들기: 먼저 pyinstaller packaging/sonefm.spec 로 dist\SoneFM 을 만든 뒤
;         "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" packaging\installer.iss
; 결과: packaging\Output\SoneFM편성표_Setup.exe
;
; - 관리자 권한 없이 설치 (사용자별 Program Files). 데이터는 문서\SoneFM 에 있어 설치·업데이트·제거해도 남는다.
; - AppId 고정: 새 버전을 같은 설치 파일로 덮어 설치하면 업데이트된다.

#define AppName "SoneFM 편성표"
#define AppVersion "1.0.0"
#define AppExe "SoneFM.exe"

[Setup]
AppId={{6E2A7C1B-3F4D-4B8E-9A21-5C0D7E8F9A63}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=SoneFM 수원공동체라디오
DefaultDirName={autopf}\SoneFM편성표
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=Output
OutputBaseFilename=SoneFM편성표_Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 아이콘 만들기"; GroupDescription: "추가 작업:"

[Files]
Source: "..\dist\SoneFM\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "지금 {#AppName} 실행"; Flags: nowait postinstall skipifsilent

[Code]
{ Microsoft Edge WebView2 런타임이 있는지 확인. 없으면 안내만 한다 (자동 다운로드 안 함). }
function WebView2Installed: Boolean;
var
  V: String;
begin
  Result :=
    RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', V) or
    RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', V) or
    RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', V);
  if Result then
    Result := (V <> '') and (V <> '0.0.0.0');
end;

function InitializeSetup: Boolean;
begin
  Result := True;
  if not WebView2Installed then
    MsgBox('이 PC에 "Microsoft Edge WebView2 런타임"이 없습니다.' + #13#10 +
           '설치는 계속되지만, 프로그램 화면이 뜨려면 WebView2 런타임이 필요합니다.' + #13#10#13#10 +
           '마이크로소프트 홈페이지에서 "WebView2 Runtime"을 검색해 "Evergreen 부트스트래퍼"를 설치해 주세요.',
           mbInformation, MB_OK);
end;
