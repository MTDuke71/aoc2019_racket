# Download Advent of Code 2019 problem statements and inputs.
# Usage:
#   .\scripts\download_aoc2019_problems.ps1 -SessionCookie "your_session_cookie_here"
#   $env:AOC_SESSION = "your_session_cookie_here"; .\scripts\download_aoc2019_problems.ps1

param(
    [Parameter(Mandatory = $false)]
    [string]$SessionCookie = $env:AOC_SESSION,

    [Parameter(Mandatory = $false)]
    [ValidateRange(1, 25)]
    [int]$StartDay = 1,

    [Parameter(Mandatory = $false)]
    [ValidateRange(1, 25)]
    [int]$EndDay = 25,

    [Parameter(Mandatory = $false)]
    [switch]$ProblemsOnly,

    [Parameter(Mandatory = $false)]
    [switch]$InputsOnly
)

$Year = "2019"

if ($StartDay -gt $EndDay) {
    Write-Host "ERROR: StartDay cannot be greater than EndDay." -ForegroundColor Red
    exit 1
}

if ($ProblemsOnly -and $InputsOnly) {
    Write-Host "ERROR: Use either -ProblemsOnly or -InputsOnly, not both." -ForegroundColor Red
    exit 1
}

$NeedsInputs = -not $ProblemsOnly
$CurlPath = $null

if ($NeedsInputs) {
    $CurlPath = (Get-Command curl.exe -ErrorAction SilentlyContinue).Source
    if ([string]::IsNullOrWhiteSpace($CurlPath)) {
        Write-Host "ERROR: curl.exe is required for input downloads and was not found on PATH." -ForegroundColor Red
        Write-Host "Install curl or run from a shell where curl.exe is available." -ForegroundColor Red
        exit 1
    }
}

# Validate session cookie
if ([string]::IsNullOrWhiteSpace($SessionCookie)) {
    Write-Host "ERROR: Session cookie required." -ForegroundColor Red
    Write-Host ""
    Write-Host "Option 1: Pass as parameter:"
    Write-Host '  .\scripts\download_aoc2019_problems.ps1 -SessionCookie "your_cookie_here"'
    Write-Host ""
    Write-Host "Option 2: Set environment variable:"
    Write-Host '  $env:AOC_SESSION = "your_cookie_here"'
    Write-Host '  .\scripts\download_aoc2019_problems.ps1'
    Write-Host ""
    Write-Host "To get your session cookie:"
    Write-Host "  1. Login to adventofcode.com"
    Write-Host "  2. Open Developer Tools (F12)"
    Write-Host "  3. Go to Application/Storage tab (or Storage in Firefox)"
    Write-Host "  4. Find Cookies -> https://adventofcode.com"
    Write-Host "  5. Copy the 'session' cookie value"
    exit 1
}

# Resolve repo root from script location.
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ProblemsDir = Join-Path $RepoRoot "Problem_Statements\days"
$InputsDir = Join-Path $RepoRoot "inputs"

Write-Host "=== Advent of Code $Year Downloader ===" -ForegroundColor Cyan
Write-Host "Repo root: $RepoRoot" -ForegroundColor Gray
Write-Host ""

# Create directories if needed
if (-not $InputsOnly) {
    New-Item -ItemType Directory -Force -Path $ProblemsDir | Out-Null
    Write-Host "Problems directory: $ProblemsDir" -ForegroundColor Gray
}

if (-not $ProblemsOnly) {
    New-Item -ItemType Directory -Force -Path $InputsDir | Out-Null
    Write-Host "Inputs directory: $InputsDir" -ForegroundColor Gray
    Write-Host "Input downloader: curl.exe" -ForegroundColor Gray
}

Write-Host ""

# Setup request parameters
$Headers = @{ "Cookie" = "session=$SessionCookie" }
$UserAgent = "aoc2019_racket/1.0"

for ($Day = $StartDay; $Day -le $EndDay; $Day++) {
    $DayPadded = "{0:D2}" -f $Day

    Write-Host "Day ${DayPadded}: " -NoNewline -ForegroundColor Yellow

    if (-not $InputsOnly) {
        $ProblemUrl = "https://adventofcode.com/$Year/day/$Day"
        $ProblemFile = Join-Path $ProblemsDir "day$DayPadded.html"

        Write-Host "Problem..." -NoNewline

        try {
            Invoke-WebRequest -Uri $ProblemUrl -Headers $Headers -UserAgent $UserAgent -OutFile $ProblemFile -ErrorAction Stop
            Write-Host "OK " -NoNewline -ForegroundColor Green
        }
        catch {
            Write-Host "FAIL " -NoNewline -ForegroundColor Red
            Write-Host "($($_.Exception.Message)) " -NoNewline -ForegroundColor DarkRed
        }
    }

    if (-not $ProblemsOnly) {
        $InputUrl = "https://adventofcode.com/$Year/day/$Day/input"
        $InputFile = Join-Path $InputsDir "day$DayPadded.txt"

        Write-Host "Input..." -NoNewline

        try {
            $CurlArgs = @(
                "--silent",
                "--show-error",
                "--fail",
                "--location",
                "--user-agent", $UserAgent,
                "--cookie", "session=$SessionCookie",
                "--output", $InputFile,
                $InputUrl
            )

            & $CurlPath @CurlArgs
            if ($LASTEXITCODE -ne 0) {
                throw "curl exited with code $LASTEXITCODE"
            }

            Write-Host "OK" -ForegroundColor Green
        }
        catch {
            Write-Host "FAIL ($($_.Exception.Message))" -ForegroundColor Red
        }
    }
    else {
        Write-Host ""
    }
}

Write-Host ""
Write-Host "=== Download Complete ===" -ForegroundColor Cyan
Write-Host ""

if (-not $InputsOnly) {
    $ProblemCount = (Get-ChildItem (Join-Path $ProblemsDir "*.html") -ErrorAction SilentlyContinue).Count
    Write-Host "Problems downloaded (.html): $ProblemCount" -ForegroundColor Gray
}

if (-not $ProblemsOnly) {
    $InputCount = (Get-ChildItem (Join-Path $InputsDir "*.txt") -ErrorAction SilentlyContinue).Count
    Write-Host "Inputs downloaded (.txt): $InputCount" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Examples:" -ForegroundColor Yellow
Write-Host '  .\scripts\download_aoc2019_problems.ps1 -StartDay 1 -EndDay 5'
Write-Host '  .\scripts\download_aoc2019_problems.ps1 -ProblemsOnly'
Write-Host '  .\scripts\download_aoc2019_problems.ps1 -InputsOnly -StartDay 10 -EndDay 15'
