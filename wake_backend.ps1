# Wake up Render backend (useful before testing Flutter web app)

Write-Host ""
Write-Host "Waking up Render backend..." -ForegroundColor Yellow
Write-Host "URL: https://savo-ynp1.onrender.com" -ForegroundColor Cyan
Write-Host ""

try {
    $response = Invoke-WebRequest -Uri "https://savo-ynp1.onrender.com/health" -Method GET -UseBasicParsing -TimeoutSec 90
    $content = $response.Content | ConvertFrom-Json
    
    Write-Host "Backend is awake and healthy!" -ForegroundColor Green
    Write-Host "Status: $($content.status)" -ForegroundColor White
    Write-Host "LLM Provider: $($content.llm_provider)" -ForegroundColor White
    Write-Host ""
    Write-Host "API Docs: https://savo-ynp1.onrender.com/docs" -ForegroundColor Cyan
    Write-Host "Flutter Web: https://savo-web.vercel.app" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Backend is ready for requests!" -ForegroundColor Green
    Write-Host ""
}
catch {
    Write-Host "Failed to wake backend: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "1. Check Render dashboard" -ForegroundColor White
    Write-Host "2. Verify environment variables are set" -ForegroundColor White
    Write-Host "3. Check logs for errors" -ForegroundColor White
    Write-Host ""
}
