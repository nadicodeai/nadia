param(
    [Parameter(Mandatory=$true)][string]$Profile,
    [Parameter(Mandatory=$true)][string]$HonchoWorkspace,
    [Parameter(Mandatory=$true)][string]$HonchoPeer,
    [Parameter(Mandatory=$true)][string]$HonchoApiKey,
    [string]$HonchoBaseUrl = "",
    [Parameter(Mandatory=$true)][string]$TelegramToken,
    [Parameter(Mandatory=$true)][string]$TelegramAllowedUsers,
    [string]$TelegramHomeChannel = "",
    [switch]$SkipGateway,
    [string]$ArgoHome = $(if ($env:ARGO_HOME) { $env:ARGO_HOME } else { Join-Path $env:LOCALAPPDATA "argo" })
)

$ErrorActionPreference = "Stop"

function Resolve-ArgoPython {
    $candidate = Join-Path $ArgoHome "argo-agent\venv\Scripts\python.exe"
    if (Test-Path $candidate) { return $candidate }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "python not found"
}

function Resolve-ArgoCommand {
    $cmd = Get-Command argo -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidate = Join-Path $ArgoHome "argo-agent\venv\Scripts\argo.exe"
    if (Test-Path $candidate) { return $candidate }
    throw "argo not found on PATH"
}

$argo = Resolve-ArgoCommand
$python = Resolve-ArgoPython
$profileHome = Join-Path (Join-Path $ArgoHome "profiles") $Profile

if (-not (Test-Path $profileHome)) {
    & $argo profile create $Profile --clone
}
New-Item -ItemType Directory -Force -Path $profileHome | Out-Null

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
for section_name in ("memory", "security", "gateway"):
    if not isinstance(data.get(section_name), dict):
        data[section_name] = {}
data["memory"]["provider"] = "honcho"
data["security"]["allow_lazy_installs"] = False
data["gateway"]["platform"] = "telegram"
path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
'@ | & $python - (Join-Path $profileHome "config.yaml")

@'
from __future__ import annotations

import json
import sys
from pathlib import Path

template_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])
workspace = sys.argv[3]
peer = sys.argv[4]
api_key = sys.argv[5]
base_url = sys.argv[6]

data = {}
if template_path.exists():
    data = json.loads(template_path.read_text(encoding="utf-8") or "{}")
if not isinstance(data, dict):
    data = {}
data["workspace"] = workspace
data["peerName"] = peer
data["apiKey"] = api_key
if base_url:
    data["baseUrl"] = base_url
else:
    data.pop("baseUrl", None)
out_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
'@ | & $python - `
    (Join-Path $ArgoHome "honcho.json.template") `
    (Join-Path $profileHome "honcho.json") `
    $HonchoWorkspace `
    $HonchoPeer `
    $HonchoApiKey `
    $HonchoBaseUrl

$envLines = @(
    "TELEGRAM_BOT_TOKEN=$TelegramToken",
    "TELEGRAM_ALLOWED_USERS=$TelegramAllowedUsers"
)
if ($TelegramHomeChannel) {
    $envLines += "TELEGRAM_HOME_CHANNEL=$TelegramHomeChannel"
}
$envPath = Join-Path $profileHome ".env"
$envLines | Set-Content -Path $envPath -Encoding UTF8

$soulTemplate = Join-Path $ArgoHome "SOUL.md.template"
$soulPath = Join-Path $profileHome "SOUL.md"
if (Test-Path $soulTemplate) {
    $soul = Get-Content -Raw -Path $soulTemplate
    $soul = $soul.Replace("{{PROFILE}}", $Profile)
    $soul = $soul.Replace("{{HONCHO_WORKSPACE}}", $HonchoWorkspace)
    $soul = $soul.Replace("{{HONCHO_PEER}}", $HonchoPeer)
    $soul | Set-Content -Path $soulPath -Encoding UTF8
} else {
    @"
# Customer Operating Context

Profile: $Profile
Honcho workspace: $HonchoWorkspace
Honcho peer: $HonchoPeer
"@ | Set-Content -Path $soulPath -Encoding UTF8
}

if (-not $SkipGateway) {
    & $argo -p $Profile gateway install
    & $argo -p $Profile gateway start
}

Write-Host "configured profile $Profile at $profileHome"
