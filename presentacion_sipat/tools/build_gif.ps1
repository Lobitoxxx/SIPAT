# Ensambla los frames capturados en GIFs optimizados con paleta.
# Requisito: ffmpeg en el PATH (verificado: 8.1.2)
# Uso: powershell -ExecutionPolicy Bypass -File tools/build_gif.ps1

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$framesDir = Join-Path $root '.gif-frames'
$outDir = Join-Path $root 'public\gif'

New-Item -ItemType Directory -Path $outDir -Force | Out-Null

# nombre, delay por frame (cs, 0.05s = 20fps)
$jobs = @(
  @{ Name = 'hero-arquitectura';  Delay = 5 },
  @{ Name = 'transicion-dataflow'; Delay = 5 }
)

foreach ($job in $jobs) {
  $src = Join-Path $framesDir $job.Name
  if (-not (Test-Path $src)) {
    Write-Warning "Faltan frames para $($job.Name), se omite"
    continue
  }

  $count = (Get-ChildItem $src -Filter *.png).Count
  $tmpPal = Join-Path $root ".pal-$($job.Name).png"
  $outGif = Join-Path $outDir "$($job.Name).gif"

  Write-Host "[gif] $($job.Name): $count frames -> $($job.Name).gif"

  # 1) paleta global optimizada
  & ffmpeg -y -loglevel error `
    -framerate 20 -i (Join-Path $src 'f%03d.png') `
    -vf "fps=20,scale=iw-1:ih-1:flags=lanczos,palettegen=stats_mode=diff:max_colors=160" `
    $tmpPal

  # 2) aplicar paleta + bucle infinito
  & ffmpeg -y -loglevel error `
    -framerate 20 -i (Join-Path $src 'f%03d.png') `
    -i $tmpPal -lavfi "fps=20,scale=iw-1:ih-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3" `
    -loop 0 -delay $job.Delay $outGif

  Remove-Item $tmpPal -Force -ErrorAction SilentlyContinue

  $size = [math]::Round((Get-Item $outGif).Length / 1KB, 1)
  Write-Host "      listo: $([math]::Round($size/1024,2)) MB"
}

Write-Host ""
Write-Host "[gif] GIFs en public/gif/"
