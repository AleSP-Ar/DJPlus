[Setup]
AppName=DJPlus
AppVersion=1.0.0-rc1
AppPublisher=DJPlus
AppPublisherURL=https://example.com/
AppId={{A2C94B17-0E0F-48E1-A351-79A8B0F8B3C2}}
AppCopyright=Copyright © 2026 DJPlus
VersionInfoVersion=1.0.0.0
DefaultDirName={localappdata}\Programs\DJPlus
DefaultGroupName=DJPlus
PrivilegesRequired=lowest
DisableProgramGroupPage=no
DisableStartupPrompt=yes
CreateAppDir=yes
Compression=lzma
SolidCompression=yes
CompressionThreads=2
OutputBaseFilename=DJPlus-Setup-1.0.0-rc1
LicenseFile=..\runtime\ffmpeg\LICENSE.txt
InfoBeforeFile=..\runtime\ffmpeg\NOTICE.txt
InfoAfterFile=..\runtime\ffmpeg\SOURCE.txt

[Tasks]
Name: desktopicon; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "..\dist\DJPlus\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\DJPlus"; Filename: "{app}\DJPlus.exe"; WorkingDir: "{app}"
Name: "{userdesktop}\DJPlus"; Filename: "{app}\DJPlus.exe"; Tasks: desktopicon; WorkingDir: "{app}"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
