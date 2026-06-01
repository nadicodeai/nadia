param(
    [switch]$DryRun,
    [switch]$PrintPythonPackages,
    [switch]$SkipArgoInstall,
    [switch]$SkipBrowser,
    [switch]$SkipInitInstall,
    [switch]$AllowLazyInstalls,
    [string]$ArgoHome = $(if ($env:ARGO_HOME) { $env:ARGO_HOME } else { Join-Path $env:LOCALAPPDATA "argo" }),
    [string]$ArgoInstallDir = $(if ($env:ARGO_INSTALL_DIR) { $env:ARGO_INSTALL_DIR } else { "" }),
    [string]$InstallUrl = $(if ($env:ARGO_INSTALL_URL) { $env:ARGO_INSTALL_URL } else { "https://raw.githubusercontent.com/nadicodeai/argo/release/scripts/install.ps1" })
)

$ErrorActionPreference = "Stop"

$FdePythonPackages = @(
    "honcho-ai==2.0.1",
    "python-telegram-bot[webhooks]==22.6",
    "edge-tts==7.2.7",
    "ddgs"
)

function Invoke-Fde {
    param([scriptblock]$Action, [string]$Display)
    if ($DryRun) {
        Write-Host "DRY-RUN: $Display"
    } else {
        & $Action
    }
}

function Resolve-ArgoInstallDir {
    if ($ArgoInstallDir) { return $ArgoInstallDir }
    $candidate = Join-Path $ArgoHome "argo-agent"
    if (Test-Path $candidate) { return $candidate }
    return $candidate
}

function Resolve-ArgoPython {
    $installDir = Resolve-ArgoInstallDir
    $candidate = Join-Path $installDir "venv\Scripts\python.exe"
    if ((Test-Path $candidate) -or $DryRun) { return $candidate }
    throw "Argo venv python not found at $candidate"
}

function Resolve-Uv {
    $cmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($candidate in @(
        (Join-Path $env:USERPROFILE ".local\bin\uv.exe"),
        (Join-Path $env:USERPROFILE ".cargo\bin\uv.exe")
    )) {
        if (Test-Path $candidate) { return $candidate }
    }
    return ""
}

function Install-Argo {
    if ($SkipArgoInstall) { return }
    $installer = Join-Path $env:TEMP "argo-install.ps1"
    Write-Host "install Argo from $InstallUrl"
    Invoke-Fde { Invoke-WebRequest -Uri $InstallUrl -OutFile $installer -UseBasicParsing } "download $InstallUrl"
    $args = @("-SkipSetup", "-NonInteractive")
    if ($SkipBrowser) {
        Write-Host "SkipBrowser requested; install.ps1 has no browser-skip flag, so the native Windows installer controls browser provisioning"
    }
    Invoke-Fde { & powershell -ExecutionPolicy Bypass -File $installer @args } "powershell -ExecutionPolicy Bypass -File $installer $($args -join ' ')"
}

function Install-FdePythonPackages {
    $python = Resolve-ArgoPython
    Write-Host "preinstall FDE Python packages"
    foreach ($package in $FdePythonPackages) {
        Write-Host "python package $package"
    }
    if ($DryRun) {
        Write-Host "DRY-RUN: $python -m pip install -U $($FdePythonPackages -join ' ')"
        return
    }
    & $python -m pip --version *> $null
    if ($LASTEXITCODE -eq 0) {
        & $python -m pip install -U @FdePythonPackages
        return
    }
    $uv = Resolve-Uv
    if ($uv) {
        & $uv pip install --python $python -U @FdePythonPackages
        return
    }
    & $python -m ensurepip --upgrade
    & $python -m pip install -U @FdePythonPackages
}

function Write-FdeTemplates {
    Write-Host "write customer templates under $ArgoHome"
    if ($DryRun) {
        Write-Host "write $ArgoHome\SOUL.md.template"
        Write-Host "write $ArgoHome\honcho.json.template"
        return
    }
    New-Item -ItemType Directory -Force -Path $ArgoHome | Out-Null
    @"
# Customer Operating Context

Profile: {{PROFILE}}
Honcho workspace: {{HONCHO_WORKSPACE}}
Honcho peer: {{HONCHO_PEER}}

Use this file for customer-specific operating context, preferences, boundaries,
and escalation notes. Do not put long-lived secrets here.
"@ | Set-Content -Path (Join-Path $ArgoHome "SOUL.md.template") -Encoding UTF8
    @"
{
  "aiPeer": "argo",
  "contextCadence": 1,
  "dialecticCadence": 2,
  "dialecticDepth": 1,
  "environment": "production",
  "pinUserPeer": true,
  "recallMode": "hybrid",
  "writeFrequency": "async"
}
"@ | Set-Content -Path (Join-Path $ArgoHome "honcho.json.template") -Encoding UTF8
}

function Write-LazyPolicy {
    if ($AllowLazyInstalls) { return }
    $config = Join-Path $ArgoHome "config.yaml"
    Write-Host "write $config security.allow_lazy_installs=false"
    if ($DryRun) { return }
    New-Item -ItemType Directory -Force -Path $ArgoHome | Out-Null
    $python = Resolve-ArgoPython
    @'
from __future__ import annotations

import sys
from pathlib import Path

import yaml

path = Path(sys.argv[1])
data = {}
if path.exists():
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
if not isinstance(data, dict):
    data = {}
security = data.setdefault("security", {})
if not isinstance(security, dict):
    security = {}
    data["security"] = security
security["allow_lazy_installs"] = False
path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
'@ | & $python - $config
}

function Install-CustomerInit {
    if ($SkipInitInstall) { return }
    $source = Join-Path $PSScriptRoot "argo-customer-init.ps1"
    if (-not (Test-Path $source)) { throw "missing $source" }
    $binDir = Join-Path $ArgoHome "bin"
    Write-Host "install argo-customer-init.ps1 to $binDir"
    if ($DryRun) { return }
    New-Item -ItemType Directory -Force -Path $binDir | Out-Null
    Copy-Item -Force $source (Join-Path $binDir "argo-customer-init.ps1")
}

function Verify-Imports {
    $python = Resolve-ArgoPython
    Write-Host "verify preinstalled imports"
    if ($DryRun) { return }
    @'
import importlib

for module in ("honcho", "telegram", "edge_tts", "ddgs"):
    importlib.import_module(module)
print("fde imports ok")
'@ | & $python -
}

if ($PrintPythonPackages) {
    $FdePythonPackages | ForEach-Object { Write-Output $_ }
    exit 0
}

Install-Argo
Install-FdePythonPackages
Write-FdeTemplates
Write-LazyPolicy
Install-CustomerInit
Verify-Imports
Write-Host "FDE provision completed"
