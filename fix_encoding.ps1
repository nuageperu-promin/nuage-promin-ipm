$repo = "D:\Descargas\nuage-promin-ipm"
$files = Get-ChildItem -Path $repo -Recurse -Include *.py,*.xml

$win1252 = [System.Text.Encoding]::GetEncoding(1252)
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$utf8Strict = New-Object System.Text.UTF8Encoding($false, $true)

$count = 0
foreach ($file in $files) {
    $bytes = [System.IO.File]::ReadAllBytes($file.FullName)
    try {
        $null = $utf8Strict.GetString($bytes)
        continue  # ya es UTF-8 valido, no tocar
    } catch {
        # bytes invalidos para UTF-8: reinterpretar como ANSI y regrabar como UTF-8
    }
    $text = $win1252.GetString($bytes)
    [System.IO.File]::WriteAllBytes($file.FullName, $utf8NoBom.GetBytes($text))
    Write-Host "Reencodado: $($file.FullName)"
    $count++
}
Write-Host ""
Write-Host "Total de archivos corregidos: $count"