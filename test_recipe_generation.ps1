# Test Recipe Generation
# Run this after Render deployment completes

Write-Host "Testing Recipe Generation..." -ForegroundColor Cyan

$token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4YzQyM2YwNC0wNDNkLTQ5YTUtOGNkZC04MThhNWQxYzZiYjciLCJleHAiOjE3Njc5MjY0MDB9.VfMkY_hRbm5GlxQJc6K5tnU3WZEqPBLf2nXvXB5ZGlg"
$body = @{
    meal_type = "dinner"
    servings = 2
    time_available_minutes = 45
} | ConvertTo-Json

try {
    Write-Host "Sending request..." -ForegroundColor Yellow
    $startTime = Get-Date
    
    $response = Invoke-WebRequest `
        -Uri "https://savo-ynp1.onrender.com/plan/daily" `
        -Method POST `
        -Headers @{
            "Content-Type" = "application/json"
            "Authorization" = "Bearer $token"
        } `
        -Body $body `
        -TimeoutSec 15
    
    $endTime = Get-Date
    $duration = ($endTime - $startTime).TotalSeconds
    
    $result = $response.Content | ConvertFrom-Json
    
    Write-Host "`n✅ SUCCESS!" -ForegroundColor Green
    Write-Host "Response Time: $duration seconds" -ForegroundColor Cyan
    Write-Host "Status: $($result.status)" -ForegroundColor Green
    Write-Host "Selected Cuisine: $($result.selected_cuisine)" -ForegroundColor Yellow
    Write-Host "Number of Menus: $($result.menus.Count)" -ForegroundColor Yellow
    
    if ($result.menus -and $result.menus.Count -gt 0) {
        $menu = $result.menus[0]
        Write-Host "Courses: $($menu.courses.Count)" -ForegroundColor Yellow
        
        if ($menu.courses -and $menu.courses.Count -gt 0) {
            $course = $menu.courses[0]
            Write-Host "Recipe Options: $($course.recipe_options.Count)" -ForegroundColor Yellow
            
            if ($course.recipe_options -and $course.recipe_options.Count -gt 0) {
                Write-Host "`nRecipe Names:" -ForegroundColor Cyan
                foreach ($recipe in $course.recipe_options) {
                    $name = if ($recipe.recipe_name.en) { $recipe.recipe_name.en } else { $recipe.recipe_name }
                    Write-Host "  - $name" -ForegroundColor White
                }
            }
        }
    }
    
    if ($result._fallback_mode) {
        Write-Host "`n⚠️  Note: Recipes generated using fallback mode (LLM unavailable)" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "`n❌ FAILED!" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    
    if ($_.ErrorDetails.Message) {
        Write-Host "Details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
}
