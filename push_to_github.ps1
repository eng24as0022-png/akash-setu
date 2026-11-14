# Akash Setu - GitHub Push Helper with Secure Browser Authentication
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "   AKASH SETU (आकाश सेतु) - SECURE GITHUB PUSHER" -ForegroundColor White
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host ""

$username = Read-Host "Enter your GitHub Username (e.g. john-doe)"
if ([string]::IsNullOrWhiteSpace($username)) {
    Write-Host "Error: Username cannot be blank." -ForegroundColor Red
    exit 1
}

$repoUrl = "https://github.com/$username/akash-setu.git"
Write-Host "Configuring remote origin: $repoUrl" -ForegroundColor Yellow

git remote remove origin 2>$null
git remote add origin $repoUrl
git branch -M main

Write-Host "Pushing code to GitHub using Git Credential Manager..." -ForegroundColor Green
Write-Host "A browser window will open if you are not already logged in to GitHub." -ForegroundColor Gray
Write-Host ""

git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "==============================================================================" -ForegroundColor Green
    Write-Host "   SUCCESS: Akash Setu pushed to GitHub: $repoUrl" -ForegroundColor Green
    Write-Host "==============================================================================" -ForegroundColor Green
    Write-Host "Next step: In Render.com, create a New Web Service and select 'akash-setu'!" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "Push failed. Please check that the repository 'akash-setu' exists on GitHub under your account." -ForegroundColor Red
}
