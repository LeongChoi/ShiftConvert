Unicode true
!include "FileFunc.nsh"
Name "ShiftConvert"
OutFile "../../windows-payload/ShiftConvert.exe"
Icon "app.ico"
RequestExecutionLevel user
SilentInstall silent
AutoCloseWindow true
Section
  SetOutPath "$EXEDIR"
  ${GetParameters} $R0
  Exec '"$EXEDIR\runtime\pythonw.exe" "$EXEDIR\launch.pyw" $R0'
  IfErrors 0 +2
    MessageBox MB_ICONSTOP "ShiftConvert could not start. Reinstall the application."
SectionEnd
