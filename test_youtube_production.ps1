# Quick Production Test: YouTube Ranking

# Test production /youtube/rank endpoint
$body = @{
    "recipe_name" = "Risotto al Pomodoro"
    "recipe_cuisine" = "Italian"
    "recipe_techniques" = @("sautéing", "risotto technique", "stirring")
    "candidates" = @(
        @{
            "video_id" = "abc123"
            "title" = "Perfect Risotto al Pomodoro - Italian Chef"
            "channel" = "Italian Cooking Academy"
            "language" = "en"
            "transcript" = "Today we make authentic risotto with tomatoes..."
            "metadata" = @{
                "duration" = "12:45"
                "views" = 500000
            }
        },
        @{
            "video_id" = "xyz789"
            "title" = "Quick Tomato Rice Recipe"
            "channel" = "Fast Food Channel"
            "language" = "en"
            "transcript" = "This is a quick tomato rice dish..."
            "metadata" = @{
                "duration" = "5:30"
                "views" = 100000
            }
        }
    )
    "output_language" = "en"
} | ConvertTo-Json -Depth 10

Write-Host "Testing production /youtube/rank endpoint..." -ForegroundColor Cyan
Write-Host "URL: https://savo-ynp1.onrender.com/youtube/rank" -ForegroundColor Yellow
Write-Host ""

try {
    $response = Invoke-RestMethod -Uri "https://savo-ynp1.onrender.com/youtube/rank" -Method POST -Body $body -ContentType "application/json"
    
    Write-Host "Response received!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Ranked Videos:" -ForegroundColor Magenta
    
    foreach ($video in $response.ranked_videos) {
        Write-Host ""
        Write-Host "  Video: $($video.title)" -ForegroundColor White
        Write-Host "     Channel: $($video.channel)" -ForegroundColor Gray
        Write-Host "     Video ID: $($video.video_id)" -ForegroundColor Gray
        Write-Host "     Trust Score: $($video.trust_score)" -ForegroundColor Cyan
        Write-Host "     Match Score: $($video.match_score)" -ForegroundColor Cyan
        Write-Host "     Reasons: $($video.reasons -join ', ')" -ForegroundColor Yellow
    }
    
    Write-Host ""
    Write-Host "YouTube ranking endpoint working in production!" -ForegroundColor Green
    
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host ""
    if ($_.ErrorDetails) {
        Write-Host "Response Body: $($_.ErrorDetails.Message)" -ForegroundColor Yellow
    }
}
