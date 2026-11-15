# Akash Setu - Secure Render API Key Input & Automated Deployer
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "   AKASH SETU (आकाश सेतु) - SECURE RENDER.COM DEPLOYER" -ForegroundColor White
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Your Render API Key can be generated in 10 seconds at:" -ForegroundColor Gray
Write-Host "https://dashboard.render.com/u/settings#api-keys" -ForegroundColor Yellow
Write-Host ""

# Prompt for masked API key (Keystrokes hidden / not logged)
$secureKey = Read-Host "Enter your Render API Key (input will be completely hidden)" -AsSecureString

if ($null -eq $secureKey -or $secureKey.Length -eq 0) {
    Write-Host "[ERROR] Render API Key cannot be blank. Aborting." -ForegroundColor Red
    pause
    exit 1
}

# Prompt for custom Commander Passcode (or enter for default)
Write-Host ""
$customPasscode = Read-Host "Set a secret Commander Passcode for Rescue Dashboard [Press Enter for default: NDRF-2026-RESCUE]"
if ([string]::IsNullOrWhiteSpace($customPasscode)) {
    $customPasscode = "NDRF-2026-RESCUE"
}

# Convert secure string in memory
$bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
$plainKey = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)

$env:RENDER_API_KEY = $plainKey
$env:COMMANDER_PASSCODE = $customPasscode

Write-Host ""
Write-Host "Starting automated deployment to Render.com..." -ForegroundColor Green
Write-Host "Creating service, injecting environment variables, monitoring build..." -ForegroundColor Gray
Write-Host ""

try {
    python deploy_render.py
} finally {
    # Zero out sensitive key memory
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    $plainKey = $null
    Remove-Item env:RENDER_API_KEY -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Deployment process finished." -ForegroundColor Cyan
pause
