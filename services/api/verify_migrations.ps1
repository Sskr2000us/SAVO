# Quick Migration Verification Script for SAVO Database
# Checks all critical database objects exist

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "SAVO Database Migration Verification" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

# Check if psycopg2 is installed
Write-Host "📦 Checking dependencies..." -ForegroundColor Yellow
$pythonCheck = python -c "import psycopg2; print('OK')" 2>&1

if ($pythonCheck -ne "OK") {
    Write-Host "❌ psycopg2 not installed. Installing..." -ForegroundColor Red
    pip install psycopg2-binary python-dotenv
    Write-Host ""
}

# Run the verification
Write-Host "🔍 Running database verification..." -ForegroundColor Yellow
Write-Host ""

cd services/api/migrations
python db_helper.py

$exitCode = $LASTEXITCODE

Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan

if ($exitCode -eq 0) {
    Write-Host "✅ All migrations verified successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Deploy to Render: git push origin main" -ForegroundColor White
    Write-Host "  2. Test API endpoints" -ForegroundColor White
    Write-Host "  3. Test Flutter app integration" -ForegroundColor White
} else {
    Write-Host "❌ Verification failed. Please review errors above." -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "  1. Check DATABASE_URL or SUPABASE credentials in .env" -ForegroundColor White
    Write-Host "  2. Ensure database is accessible" -ForegroundColor White
    Write-Host "  3. Run migrations manually in Supabase SQL Editor" -ForegroundColor White
    Write-Host "  4. See services/api/migrations/README.md for details" -ForegroundColor White
}

Write-Host "=" * 70 -ForegroundColor Cyan

exit $exitCode
