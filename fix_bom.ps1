$repo = "D:\Descargas\nuage-promin-ipm"
$files = Get-ChildItem -Path $repo -Recurse -Include *.py,*.xml

$bom = [byte[]](0xEF,0xBB,0xBF)
$count = 0
foreach ($file in $files) {
    $bytes = [System.IO.File]::ReadAllBytes($file.FullName)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq $bom[0] -and $bytes[1] -eq $bom[1] -and $bytes[2] -eq $bom[2]) {
        $newBytes = $bytes[3..($bytes.Length-1)]
        [System.IO.File]::WriteAllBytes($file.FullName, $newBytes)
        Write-Host "BOM eliminado: $($file.FullName)"
        $count++
    }
}
Write-Host ""
Write-Host "Total de archivos con BOM corregidos: $count"