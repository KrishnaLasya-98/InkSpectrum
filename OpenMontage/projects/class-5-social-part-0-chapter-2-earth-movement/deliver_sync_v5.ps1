param([switch]$Deliver)
$ErrorActionPreference = 'Stop'
$projectDir = $PSScriptRoot
$repoDir = [IO.Path]::GetFullPath((Join-Path $projectDir '..\..'))
$deliveryDir = Join-Path $repoDir 'final-videos\Class-5-Social'
$sourceVideo = Join-Path $projectDir 'hyperframes-elevenlabs-sync-repair-v5\renders\class5-social-chapter2-earth-movement-sync-repair-v5.mp4'
$targetVideo = Join-Path $deliveryDir 'Class-5-Social-Chapter-02-Earth-Movement.mp4'
$qaPath = Join-Path $projectDir 'artifacts\encoded-sync-v5-qa.json'
$qa = Get-Content -LiteralPath $qaPath -Raw | ConvertFrom-Json
if ($qa.status -ne 'technical_pass' -or $qa.visual_review.status -ne 'reviewed') {
    throw 'Technical and recorded visual QA must pass before promotion.'
}
if (-not (Test-Path -LiteralPath $sourceVideo -PathType Leaf)) { throw 'Render missing.' }
$newHash = (Get-FileHash -LiteralPath $sourceVideo -Algorithm SHA256).Hash.ToLowerInvariant()
if ($newHash -ne $qa.sha256) { throw 'Rendered file changed after QA.' }
$oldTargets = @(
    $targetVideo,
    (Join-Path $deliveryDir 'Class-5-Social-Chapter-02-Earth-Movement-title-pause-v4.mp4')
)
foreach ($oldPath in $oldTargets) {
    if ([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($oldPath)) -ne $deliveryDir) {
        throw 'Unexpected delivery target.'
    }
}
if (-not $Deliver) {
    [pscustomobject]@{ Status='ready_to_move'; Source=$sourceVideo; Destination=$targetVideo; Superseded=$oldTargets } | ConvertTo-Json
    exit 0
}
Add-Type -AssemblyName Microsoft.VisualBasic
$recycled = @()
foreach ($oldPath in $oldTargets) {
    if (Test-Path -LiteralPath $oldPath -PathType Leaf) {
        [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile(
            $oldPath,
            [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
            [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin)
        $recycled += $oldPath
    }
}
Move-Item -LiteralPath $sourceVideo -Destination $targetVideo
if ((Test-Path -LiteralPath $sourceVideo) -or (Get-FileHash -LiteralPath $targetVideo).Hash.ToLowerInvariant() -ne $newHash) {
    throw 'Move verification failed.'
}
$indexPath = Join-Path $deliveryDir 'index.json'
$index = Get-Content -LiteralPath $indexPath -Raw | ConvertFrom-Json
$chapter = $index.chapters | Where-Object chapter -eq 2
$chapter.video = $targetVideo
$chapter.status = 'completed'
$chapter | Add-Member -NotePropertyName revision -NotePropertyValue 'sync-repair-v5' -Force
$chapter | Add-Member -NotePropertyName sha256 -NotePropertyValue $newHash -Force
$chapter | Add-Member -NotePropertyName qa_report -NotePropertyValue $qaPath -Force
$index | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $indexPath -Encoding utf8
$qa.path = $targetVideo
$qa | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $qaPath -Encoding utf8
$delivery = [ordered]@{ status='delivered'; path=$targetVideo; revision='sync-repair-v5'; sha256=$newHash; duplicate_render_retained=$false; recycled_superseded_deliveries=$recycled; recycled_files_recoverable=$true; qa_report=$qaPath }
$delivery | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $projectDir 'artifacts\delivery-sync-v5.json') -Encoding utf8
$delivery | ConvertTo-Json -Depth 10
