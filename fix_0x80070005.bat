Set OSBIT=32

IF exist "%ProgramFiles(x86)%" set OSBIT=64

set RUNNINGDIR=%ProgramFiles%

IF %OSBIT% == 64 set RUNNINGDIR=%ProgramFiles(x86)%

subinacl /subkeyreg "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing" /grant="nt service\trustedinstaller"=f