Unicode true
!include "MUI2.nsh"
!include "x64.nsh"
Name "ShiftConvert 0.2.0"
OutFile "../../deliverables/ShiftConvert-0.2.0-Setup.exe"
InstallDir "$LOCALAPPDATA\Programs\ShiftConvert"
RequestExecutionLevel user
SetCompressor zlib
Icon "app.ico"
UninstallIcon "app.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TEXT "Convert images, PDFs, spreadsheets and media locally.$\r$\n$\r$\nPython and core conversion tools are included. Word to PDF and OCR require optional LibreOffice and Tesseract.$\r$\n$\r$\nThis unsigned preview build has not been run on a Windows PC."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\ShiftConvert.exe"
!define MUI_FINISHPAGE_SHOWREADME "$INSTDIR\START_HERE.html"
!define MUI_FINISHPAGE_SHOWREADME_TEXT "Open the getting started guide"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
Function .onInit
 ${IfNot} ${RunningX64}
  MessageBox MB_ICONSTOP "ShiftConvert needs 64-bit Windows 10 or 11."
  Abort
 ${EndIf}
FunctionEnd
Section "ShiftConvert application"
 SectionIn RO
 SetShellVarContext current
 SetOutPath "$INSTDIR"
 File /r "../../windows-payload/*"
 WriteUninstaller "$INSTDIR\Uninstall.exe"
 CreateDirectory "$SMPROGRAMS\ShiftConvert"
 CreateShortcut "$SMPROGRAMS\ShiftConvert\ShiftConvert.lnk" "$INSTDIR\ShiftConvert.exe"
 CreateShortcut "$SMPROGRAMS\ShiftConvert\Getting started.lnk" "$INSTDIR\START_HERE.html"
 CreateShortcut "$DESKTOP\ShiftConvert.lnk" "$INSTDIR\ShiftConvert.exe"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ShiftConvert" "DisplayName" "ShiftConvert"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ShiftConvert" "DisplayVersion" "0.2.0"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ShiftConvert" "Publisher" "ShiftConvert"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ShiftConvert" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ShiftConvert" "DisplayIcon" "$INSTDIR\ShiftConvert.exe"
 WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ShiftConvert" "NoModify" 1
 WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ShiftConvert" "NoRepair" 1
SectionEnd
Section "Start quietly in the system tray when I sign in"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "ShiftConvert" '$\"$INSTDIR\ShiftConvert.exe$\" --background'
SectionEnd
Section "Uninstall"
 SetShellVarContext current
 Delete "$DESKTOP\ShiftConvert.lnk"
 Delete "$SMPROGRAMS\ShiftConvert\ShiftConvert.lnk"
 Delete "$SMPROGRAMS\ShiftConvert\Getting started.lnk"
 RMDir "$SMPROGRAMS\ShiftConvert"
 DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ShiftConvert"
 DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "ShiftConvert"
 RMDir /r "$INSTDIR\runtime"
 RMDir /r "$INSTDIR\source"
 RMDir /r "$INSTDIR\shiftconvert"
 Delete "$INSTDIR\ShiftConvert.exe"
 Delete "$INSTDIR\launch.pyw"
 Delete "$INSTDIR\START_HERE.html"
 Delete "$INSTDIR\LICENSE"
 Delete "$INSTDIR\Uninstall.exe"
 RMDir "$INSTDIR"
SectionEnd
