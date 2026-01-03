# Quick test: call /plan/daily directly to see the response
# This bypasses Flutter UI and shows raw API response

$token = Read-Host "Paste your Supabase JWT token (from DevTools → Application → Local Storage → supabase.auth.token)"

$headers = @{
    "Authorization" = "Bearer $token"
    "Origin" = "https://savo-web.vercel.app"
    "Content-Type" = "application/json"
}

$body = @{
    meal_type = "dinner"
    servings = 4
    time_available_minutes = 45
    cuisine_preferences = @("Indian", "Italian")
} | ConvertTo-Json

Write-Host "`nCalling POST /plan/daily..." -ForegroundColor Cyan

try {
    $response = Invoke-RestMethod `
        -Uri "https://savo-ynp1.onrender.com/plan/daily" `
        -Method Post `
        -Headers $headers `
        -Body $body

    Write-Host "`nResponse:" -ForegroundColor Green
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "`nError:" -ForegroundColor Red
    Write-Host $_.Exception.Message
    Write-Host "`nResponse body:" -ForegroundColor Yellow
    $_.ErrorDetails.Message
}
