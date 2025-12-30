# Test production backend with Google Gemini
$body = @{
    "inventory" = @{
        "available_ingredients" = @("tomatoes", "pasta", "olive oil", "garlic", "basil")
        "expiring_soon" = @()
        "leftovers" = @()
    }
    "cuisine_preferences" = @("Italian")
    "skill_level" = "beginner"
} | ConvertTo-Json

Write-Host "Testing production backend with Google Gemini..." -ForegroundColor Cyan
Write-Host "URL: https://savo-ynp1.onrender.com/plan/daily" -ForegroundColor Yellow
Write-Host ""

$response = Invoke-RestMethod -Uri "https://savo-ynp1.onrender.com/plan/daily" -Method POST -Body $body -ContentType "application/json"

Write-Host "Response received!" -ForegroundColor Green
Write-Host ""
Write-Host "Selected Cuisine: $($response.selected_cuisine)" -ForegroundColor Magenta
Write-Host ""

foreach ($menu in $response.menus) {
    Write-Host "=== $($menu.course_name) ===" -ForegroundColor Yellow
    Write-Host "Recipe: $($menu.recipe_name)" -ForegroundColor White
    Write-Host "Time: $($menu.time_minutes) minutes" -ForegroundColor Gray
    Write-Host "Calories: $($menu.calories_kcal) kcal" -ForegroundColor Gray
    Write-Host "Ingredients: $($menu.ingredients -join ', ')" -ForegroundColor Cyan
    Write-Host ""
}
