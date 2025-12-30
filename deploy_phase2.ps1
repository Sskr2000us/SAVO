# Phase 2 Deployment Automation Script
# Run this to deploy training data collection to production

param(
    [switch]$CheckOnly,
    [switch]$Deploy
)

Write-Host "`n=== PHASE 2 DEPLOYMENT SCRIPT ===" -ForegroundColor Green

# Step 1: Verify local state
Write-Host "`n[1/5] Checking local repository state..." -ForegroundColor Yellow
Push-Location $PSScriptRoot

$gitStatus = git status --porcelain
if ($gitStatus) {
    Write-Host "   WARNING: Uncommitted changes detected" -ForegroundColor Red
    git status --short
    Write-Host "`n   Commit changes before deploying!" -ForegroundColor Red
    Pop-Location
    exit 1
} else {
    Write-Host "   ✓ Repository clean" -ForegroundColor Green
}

$currentCommit = git rev-parse --short HEAD
Write-Host "   Current commit: $currentCommit" -ForegroundColor Cyan

# Step 2: Verify training endpoints exist
Write-Host "`n[2/5] Verifying training endpoints..." -ForegroundColor Yellow
$trainingRouteExists = Test-Path "services\api\app\api\routes\training.py"
$trainingModelExists = Test-Path "services\api\app\models\training.py"
$mlInfraExists = Test-Path "services\ml\train.py"

if ($trainingRouteExists -and $trainingModelExists -and $mlInfraExists) {
    Write-Host "   ✓ Training API routes found" -ForegroundColor Green
    Write-Host "   ✓ Training models found" -ForegroundColor Green
    Write-Host "   ✓ ML infrastructure found" -ForegroundColor Green
} else {
    Write-Host "   ERROR: Training infrastructure incomplete" -ForegroundColor Red
    Pop-Location
    exit 1
}

# Step 3: Test local imports
Write-Host "`n[3/5] Testing Python imports..." -ForegroundColor Yellow
Push-Location "services\api"
& .\.venv\Scripts\Activate.ps1

$importTest = python -c "from app.api.routes.training import router; from app.models.training import TrainingDataSubmission; print('✓')" 2>&1
if ($importTest -match "✓") {
    Write-Host "   ✓ Training modules import successfully" -ForegroundColor Green
} else {
    Write-Host "   ERROR: Import failed" -ForegroundColor Red
    Write-Host $importTest -ForegroundColor Red
    Pop-Location
    Pop-Location
    exit 1
}

Pop-Location

# Step 4: Display deployment checklist
Write-Host "`n[4/5] RENDER DEPLOYMENT CHECKLIST:" -ForegroundColor Yellow
Write-Host "`n   Manual steps required (Render Dashboard):" -ForegroundColor Cyan
Write-Host "   1. Go to: https://dashboard.render.com" -ForegroundColor White
Write-Host "   2. Select service: savo-api" -ForegroundColor White
Write-Host "   3. Click 'Environment' tab" -ForegroundColor White
Write-Host "   4. Add these environment variables:" -ForegroundColor White
Write-Host ""
Write-Host "      SAVO_COLLECT_TRAINING_DATA=true" -ForegroundColor Green
Write-Host "      SAVO_VISION_PROVIDER=google" -ForegroundColor Green
Write-Host "      SAVO_REASONING_PROVIDER=openai" -ForegroundColor Green
Write-Host "      GOOGLE_API_KEY=<your-key>" -ForegroundColor Yellow
Write-Host "      OPENAI_API_KEY=<your-key>" -ForegroundColor Yellow
Write-Host "      SAVO_USE_CUSTOM_VISION=false" -ForegroundColor Green
Write-Host ""
Write-Host "   5. Click 'Manual Deploy' → 'Deploy latest commit'" -ForegroundColor White
Write-Host "   6. Wait 3-5 minutes for build to complete" -ForegroundColor White

# Step 5: Verification URLs
Write-Host "`n[5/5] POST-DEPLOYMENT VERIFICATION:" -ForegroundColor Yellow
Write-Host "`n   After deployment completes, test these URLs:" -ForegroundColor Cyan
Write-Host "   https://savo-ynp1.onrender.com/docs#/training" -ForegroundColor White
Write-Host "   https://savo-ynp1.onrender.com/training/stats" -ForegroundColor White
Write-Host ""
Write-Host "   Expected response from /training/stats:" -ForegroundColor Cyan
Write-Host '   {' -ForegroundColor Gray
Write-Host '     "total_samples": 0,' -ForegroundColor Gray
Write-Host '     "samples_today": 0,' -ForegroundColor Gray
Write-Host '     "samples_this_week": 0,' -ForegroundColor Gray
Write-Host '     "average_detections_per_image": 0,' -ForegroundColor Gray
Write-Host '     "correction_rate": 0,' -ForegroundColor Gray
Write-Host '     "storage_size_mb": 0' -ForegroundColor Gray
Write-Host '   }' -ForegroundColor Gray

# Summary
Write-Host "`n=== DEPLOYMENT SUMMARY ===" -ForegroundColor Green
Write-Host "   Local State: Ready ✓" -ForegroundColor Green
Write-Host "   Commit: $currentCommit ✓" -ForegroundColor Green
Write-Host "   Training Endpoints: Ready ✓" -ForegroundColor Green
Write-Host "   Next Step: Configure Render environment variables" -ForegroundColor Yellow
Write-Host ""
Write-Host "   See DEPLOY_PHASE2.md for detailed instructions" -ForegroundColor Cyan

# Optional: Open Render dashboard
Write-Host "`n   Open Render dashboard now? (Y/N): " -ForegroundColor Yellow -NoNewline
$response = Read-Host
if ($response -eq 'Y' -or $response -eq 'y') {
    Start-Process "https://dashboard.render.com"
    Write-Host "   ✓ Opening Render dashboard..." -ForegroundColor Green
}

# Optional: Open documentation
Write-Host "   Open deployment documentation? (Y/N): " -ForegroundColor Yellow -NoNewline
$response = Read-Host
if ($response -eq 'Y' -or $response -eq 'y') {
    Start-Process "DEPLOY_PHASE2.md"
    Write-Host "   ✓ Opening DEPLOY_PHASE2.md..." -ForegroundColor Green
}

Pop-Location

Write-Host "`n=== READY TO DEPLOY ===" -ForegroundColor Green
Write-Host "   Data collection starts immediately after deployment!" -ForegroundColor Cyan
Write-Host "   Every user scan = training data for your custom model" -ForegroundColor Cyan
Write-Host ""
