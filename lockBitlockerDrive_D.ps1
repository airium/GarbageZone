# Change the filename suffix letter to match your drive
$driveletter = ($PSCommandPath.split('_') | Select-Object -Last 1).split('.') | Select-Object -First 1
Lock-BitLocker -MountPoint ${driveletter}: -ForceDismount