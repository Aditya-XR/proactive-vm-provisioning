# Compiles the Java simulator against a local CloudSim 5.0 build using JDK 8.
param(
    [string]$CloudSimHome = $(if ($env:CLOUDSIM_HOME) { $env:CLOUDSIM_HOME } else { 'C:\CloudSim\cloudsim-5.0' }),
    [string]$JdkHome = $(if ($env:JDK8_HOME) { $env:JDK8_HOME } else { 'C:\Program Files\Eclipse Adoptium\jdk-8.0.502.7-hotspot' })
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$classes = Join-Path $CloudSimHome 'modules\cloudsim\target\classes'
if (-not (Test-Path $classes)) { throw "CloudSim classes not found at $classes. Import CloudSim into Eclipse or run mvn compile first." }
$math = Get-ChildItem "$env:USERPROFILE\.m2\repository\org\apache\commons\commons-math3" -Recurse -Filter 'commons-math3-*.jar' |
    Where-Object { $_.Name -notmatch 'sources|javadoc' } | Select-Object -First 1
if (-not $math) { throw 'commons-math3 jar not found in the local Maven repository.' }

$out = Join-Path $root 'simulator\build'
if (Test-Path $out) { Remove-Item -Recurse -Force $out }
New-Item -ItemType Directory $out | Out-Null
$sources = (Get-ChildItem (Join-Path $root 'simulator\src\provisioning') -Filter *.java).FullName
& "$JdkHome\bin\javac.exe" -encoding UTF-8 -nowarn -cp "$classes;$($math.FullName)" -d $out $sources
if ($LASTEXITCODE -ne 0) { throw 'javac failed' }
Set-Content -Path (Join-Path $root 'simulator\classpath.txt') -Value "$out;$classes;$($math.FullName)" -NoNewline
Write-Output "built $out"
