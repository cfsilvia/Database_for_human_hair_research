$source = "C:\Users\Administrator\OneDrive - weizmann.ac.il\Gili Solomon-Green's files - Hair_Project\Follow_participants_hair_project.xlsm"
$destination = "D:\HairProject\SmartSurvey"

Copy-Item -LiteralPath $source -Destination $destination -Force -ErrorAction Stop

Write-Host "File copied successfully"

