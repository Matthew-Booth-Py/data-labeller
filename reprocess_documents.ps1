# Reprocess all documents to fix table duplication

Write-Host "Fetching documents..." -ForegroundColor Cyan

# Get all documents
$response = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/documents" -Method Get
$documents = $response.documents

Write-Host "Found $($documents.Count) documents" -ForegroundColor Green
Write-Host ""

foreach ($doc in $documents) {
    Write-Host "Reprocessing: $($doc.filename) (ID: $($doc.id))" -ForegroundColor Yellow
    
    try {
        $result = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/documents/$($doc.id)/reprocess" -Method Post
        Write-Host "  ✓ Success: $($result.message)" -ForegroundColor Green
    }
    catch {
        Write-Host "  ✗ Failed: $($_.Exception.Message)" -ForegroundColor Red
    }
    
    Write-Host ""
}

Write-Host "Done! Refresh your browser to see the updated documents." -ForegroundColor Cyan
