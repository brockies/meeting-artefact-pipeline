Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (git rev-parse --show-toplevel).Trim()
Set-Location $repoRoot

$stagedFiles = @(git diff --cached --name-only --diff-filter=ACMR)
if (-not $stagedFiles -or $stagedFiles.Count -eq 0) {
    exit 0
}

$blockedPathPatterns = @(
    '^(?:\.env)$',
    '^(?:inputs|history|outputs)[\\/].+'
)

$secretPatterns = @(
    'sk-[A-Za-z0-9]{20,}',
    'AKIA[0-9A-Z]{16}',
    '-----BEGIN [A-Z ]*PRIVATE KEY-----',
    '(?i)authorization\s*:\s*bearer\s+[A-Za-z0-9\-._~+/]+=*',
    '(?i)(?:api[_-]?key|secret|token|password|passwd|client[_-]?secret)\s*[:=]\s*["''][^"'']{8,}["'']',
    '(?i)(?:api[_-]?key|secret|token|password|passwd|client[_-]?secret)\s*[:=]\s*[A-Za-z0-9._~+/=-]{12,}'
)

$allowPatterns = @(
    '(?i)OPENAI_API_KEY\s*=\s*your-openai-api-key-here',
    '(?i)(?:api[_-]?key|secret|token|password|passwd|client[_-]?secret)\s*[:=]\s*(?:your-|example|changeme|replace-me|replace_this)'
)

$violations = New-Object System.Collections.Generic.List[string]

foreach ($path in $stagedFiles) {
    foreach ($pattern in $blockedPathPatterns) {
        if ($path -match $pattern) {
            $violations.Add("Blocked path staged: $path")
            continue
        }
    }

    $content = git show --textconv ":$path" 2>$null
    if ($LASTEXITCODE -ne 0) {
        continue
    }

    $lineNumber = 0
    foreach ($line in ($content -split "`r?`n")) {
        $lineNumber += 1
        foreach ($pattern in $secretPatterns) {
            if ($line -notmatch $pattern) {
                continue
            }

            $isAllowed = $false
            foreach ($allowPattern in $allowPatterns) {
                if ($line -match $allowPattern) {
                    $isAllowed = $true
                    break
                }
            }

            if (-not $isAllowed) {
                $violations.Add(("Potential secret in {0}:{1}" -f $path, $lineNumber))
                break
            }
        }
    }
}

if ($violations.Count -gt 0) {
    Write-Host ""
    Write-Host "Commit blocked by secret scan:" -ForegroundColor Red
    $violations | Sort-Object -Unique | ForEach-Object { Write-Host " - $_" -ForegroundColor Yellow }
    Write-Host ""
    Write-Host "If a match is intentional, replace it with a safe placeholder before committing." -ForegroundColor Cyan
    exit 1
}

exit 0
