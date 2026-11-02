# Runs the simulator checks, then the validation and test experiments.
param(
    [string]$JdkHome = $(if ($env:JDK8_HOME) { $env:JDK8_HOME } else { 'C:\Program Files\Eclipse Adoptium\jdk-8.0.502.7-hotspot' })
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = Join-Path $root '.venv\Scripts\python.exe'
$java = "$JdkHome\bin\java.exe"

& (Join-Path $PSScriptRoot 'build_simulator.ps1') -JdkHome $JdkHome
& $python ml\prepare_scenarios.py
if ($LASTEXITCODE -ne 0) { throw 'prepare_scenarios failed' }

$cp = Get-Content simulator\classpath.txt -Raw
$margin = (Get-Content results\margin.txt).Trim()

& $java -cp $cp provisioning.SimulatorChecks | Tee-Object results\simulator_checks.txt
if ($LASTEXITCODE -ne 0) { throw 'simulator checks failed' }

& $java -Xmx6g -cp $cp provisioning.Main results\validation\scenarios results\validation $margin
if ($LASTEXITCODE -ne 0) { throw 'validation experiment failed' }
Remove-Item results\validation\sim_intervals.csv

& $java -Xmx6g -cp $cp provisioning.Main results\scenarios results $margin
if ($LASTEXITCODE -ne 0) { throw 'test experiment failed' }

& $python ml\analyse.py
if ($LASTEXITCODE -ne 0) { throw 'analysis failed' }
