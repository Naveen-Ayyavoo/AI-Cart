# .agents/scripts/graphify-auto.ps1
# Automated Graphify Maintenance and Enforcement Hook for TrustCart
# Native Google Antigravity Lifecycle Hook (PreInvocation and Stop)

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [ValidateSet('PreInvocation', 'Stop')]
    [string]$Event = 'PreInvocation'
)

$ErrorActionPreference = 'SilentlyContinue'

# 1. Parse JSON input from stdin
$rawInput = $null
try {
    $rawInput = [Console]::In.ReadToEnd()
} catch {}

$inputJson = $null
if (-not [string]::IsNullOrWhiteSpace($rawInput)) {
    try {
        $inputJson = $rawInput | ConvertFrom-Json
    } catch {}
}

# Allow hookEventName from payload to override/specify event
if ($inputJson -and $inputJson.hookEventName) {
    if ($inputJson.hookEventName -in @('PreInvocation', 'Stop')) {
        $Event = $inputJson.hookEventName
    }
}

# 2. Determine and validate TrustCart workspace root
$workspaceRoot = $null
if ($inputJson -and $inputJson.workspacePaths) {
    foreach ($wp in $inputJson.workspacePaths) {
        if (Test-Path (Join-Path $wp "manage.py")) {
            $workspaceRoot = (Resolve-Path $wp).Path
            break
        }
    }
}
if (-not $workspaceRoot -and $inputJson -and $inputJson.cwd) {
    if (Test-Path (Join-Path $inputJson.cwd "manage.py")) {
        $workspaceRoot = (Resolve-Path $inputJson.cwd).Path
    }
}
if (-not $workspaceRoot) {
    $scriptDir = $PSScriptRoot
    if (-not $scriptDir) { $scriptDir = (Get-Location).Path }
    $candidate = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
    if (Test-Path (Join-Path $candidate "manage.py")) {
        $workspaceRoot = $candidate
    } else {
        $workspaceRoot = (Get-Location).Path
    }
}

# Runtime and storage paths
$runtimeDir = Join-Path $workspaceRoot ".graphify-runtime"
if (-not (Test-Path $runtimeDir)) {
    New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
}
$logFile = Join-Path $runtimeDir "diagnostics.log"
$hashFile = Join-Path $runtimeDir "last-indexed-source.sha256"
$lockFile = Join-Path $runtimeDir "graphify.lock"

# Helper: Append to diagnostic log
function Write-DiagLog([string]$level, [string]$message) {
    $timestamp = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
    $logLine = "[$timestamp] [$Event] [$level] $message"
    try {
        [System.IO.File]::AppendAllText($logFile, "$logLine`r`n", [System.Text.Encoding]::UTF8)
    } catch {}
}

# Helper: Locate Graphify CLI executable (isolated uv tool or local bin)
function Get-GraphifyExecutable {
    $cmdObj = Get-Command graphify -ErrorAction SilentlyContinue
    $cmd = if ($cmdObj) { $cmdObj.Source } else { $null }
    if ($cmd -and (Test-Path $cmd)) { return $cmd }
    $localBin = Join-Path $env:USERPROFILE ".local\bin\graphify.exe"
    if (Test-Path $localBin) { return $localBin }
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        $uvDirRaw = uv tool dir 2>$null
        $uvDir = if ($uvDirRaw) { $uvDirRaw.Trim() } else { $null }
        if ($uvDir) {
            $uvExe = Join-Path $uvDir "graphifyy\Scripts\graphify.exe"
            if (Test-Path $uvExe) { return $uvExe }
        }
    }
    return "graphify"
}

# Helper: Compute SHA-256 fingerprint across all indexable source files
function Get-SourceFingerprint([string]$root) {
    $excludeDirs = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    @('.git', '.venv', 'venv', 'env', 'node_modules', 'graphify-out', '__pycache__', '.planning', '.agents', 'scratch', 'brain', '.graphify-runtime', '.ruff_cache', '.pytest_cache', '.vscode', '.idea') | ForEach-Object { $excludeDirs.Add($_) | Out-Null }

    $fileList = [System.Collections.Generic.List[string]]::new()
    $dirQueue = [System.Collections.Generic.Queue[string]]::new()
    $dirQueue.Enqueue($root)

    while ($dirQueue.Count -gt 0) {
        $current = $dirQueue.Dequeue()
        try {
            $subDirs = [System.IO.Directory]::EnumerateDirectories($current)
            foreach ($d in $subDirs) {
                $name = [System.IO.Path]::GetFileName($d)
                if (-not $excludeDirs.Contains($name)) {
                    $dirQueue.Enqueue($d)
                }
            }
            $subFiles = [System.IO.Directory]::EnumerateFiles($current)
            foreach ($f in $subFiles) {
                $ext = [System.IO.Path]::GetExtension($f).ToLowerInvariant()
                $name = [System.IO.Path]::GetFileName($f)
                if ($ext -notin @('.pyc', '.pyo', '.pyd', '.log', '.sha256', '.lock') -and $name -notlike '*.sqlite3*' -and $name -ne 'Thumbs.db') {
                    $fileList.Add($f)
                }
            }
        } catch {}
    }

    $fileList.Sort([System.StringComparer]::OrdinalIgnoreCase)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $ms = [System.IO.MemoryStream]::new()
    $writer = [System.IO.BinaryWriter]::new($ms)

    foreach ($f in $fileList) {
        $rel = $f.Substring($root.Length).TrimStart('\', '/')
        $relBytes = [System.Text.Encoding]::UTF8.GetBytes($rel)
        $writer.Write($relBytes.Length)
        $writer.Write($relBytes)
        
        $content = [System.IO.File]::ReadAllBytes($f)
        $fhash = $sha.ComputeHash($content)
        $writer.Write($fhash)
    }
    $writer.Flush()
    $ms.Position = 0
    $fingerprint = [BitConverter]::ToString($sha.ComputeHash($ms)).Replace('-', '').ToLowerInvariant()
    $writer.Close()
    $ms.Close()
    return @{
        Fingerprint = $fingerprint
        FileCount = $fileList.Count
    }
}

# Helper: Lock management
function Acquire-GraphifyLock {
    try {
        if (Test-Path $lockFile) {
            $isStale = $false
            try {
                $content = [System.IO.File]::ReadAllText($lockFile).Trim()
                $parts = $content.Split(',')
                $lockPid = [int]$parts[0]
                $lockTime = [DateTime]::Parse($parts[1])
                if ((Get-Date).ToUniversalTime().Subtract($lockTime).TotalMinutes -gt 5) {
                    $isStale = $true
                } else {
                    $proc = Get-Process -Id $lockPid -ErrorAction SilentlyContinue
                    if (-not $proc) { $isStale = $true }
                }
            } catch {
                $isStale = $true
            }
            if ($isStale) {
                Write-DiagLog "WARN" "Reclaiming stale lock file"
                Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
            }
        }

        $fs = [System.IO.File]::Open($lockFile, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
        $sw = [System.IO.StreamWriter]::new($fs)
        $sw.WriteLine("$PID,$([DateTime]::UtcNow.ToString('o'))")
        $sw.Flush()
        $fs.Close()
        return $true
    } catch {
        Write-DiagLog "WARN" "Failed to acquire lock: $($_.Exception.Message)"
        return $false
    }
}

function Release-GraphifyLock {
    try {
        if (Test-Path $lockFile) {
            Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
        }
    } catch {}
}

# Helper: Execute Graphify refresh safely in project root
function Invoke-GraphifyRefresh([string]$reason) {
    if (-not (Acquire-GraphifyLock)) {
        Write-DiagLog "SKIP" "Update skipped: concurrent lock held ($reason)"
        return $false
    }

    $startTime = [System.Diagnostics.Stopwatch]::StartNew()
    $graphJsonPath = Join-Path $workspaceRoot "graphify-out\graph.json"
    $graphExists = Test-Path $graphJsonPath
    $graphifyExe = Get-GraphifyExecutable

    Write-DiagLog "INFO" "Starting graph refresh ($reason) using $graphifyExe"

    $success = $false
    Push-Location $workspaceRoot
    try {
        if (-not $graphExists) {
            Write-DiagLog "INFO" "graphify-out/graph.json missing; initiating fresh code-only extraction"
            $extractOutput = & $graphifyExe extract . --code-only 2>&1
            if ($LASTEXITCODE -eq 0) {
                $clusterOutput = & $graphifyExe cluster-only . --no-label 2>&1
                if ($LASTEXITCODE -eq 0) {
                    $success = $true
                } else {
                    Write-DiagLog "ERROR" "Clustering failed: $($clusterOutput -join ' ')"
                }
            } else {
                Write-DiagLog "ERROR" "Extraction failed: $($extractOutput -join ' ')"
            }
        } else {
            $updateOutput = & $graphifyExe update . 2>&1
            if ($LASTEXITCODE -eq 0) {
                $success = $true
            } else {
                Write-DiagLog "ERROR" "Update failed: $($updateOutput -join ' ')"
            }
        }
    } catch {
        Write-DiagLog "ERROR" "Exception during graphify update: $($_.Exception.Message)"
        $success = $false
    } finally {
        Pop-Location
        Release-GraphifyLock
        $startTime.Stop()
    }

    if ($success) {
        Write-DiagLog "SUCCESS" "Graph refresh completed in $($startTime.ElapsedMilliseconds)ms"
    }
    return $success
}

# -------------------------------------------------------------
# EVENT HANDLERS
# -------------------------------------------------------------

if ($Event -eq 'PreInvocation') {
    $userInput = if ($inputJson -and $inputJson.lastUserInput) { [string]$inputJson.lastUserInput } else { "" }
    $previewInput = if ($userInput.Length -gt 60) { $userInput.Substring(0, 60) + '...' } else { $userInput }
    Write-DiagLog "EVENT" "PreInvocation triggered (lastUserInput: '$previewInput')"

    $fpInfo = Get-SourceFingerprint $workspaceRoot
    $currentFp = $fpInfo.Fingerprint
    $graphJsonPath = Join-Path $workspaceRoot "graphify-out\graph.json"
    $graphExists = Test-Path $graphJsonPath

    $lastFp = $null
    if (Test-Path $hashFile) {
        $lastFp = [System.IO.File]::ReadAllText($hashFile).Trim()
    }

    $needsRefresh = (-not $graphExists) -or ($currentFp -ne $lastFp)

    if ($needsRefresh) {
        $reason = if (-not $graphExists) { "graph missing" } else { "source fingerprint changed ($lastFp -> $currentFp)" }
        $refreshed = Invoke-GraphifyRefresh $reason
        if ($refreshed) {
            [System.IO.File]::WriteAllText($hashFile, $currentFp, [System.Text.Encoding]::UTF8)
            Write-DiagLog "FINGERPRINT" "Saved new source fingerprint: $currentFp ($($fpInfo.FileCount) files)"
        } else {
            Write-DiagLog "WARN" "Refresh failed; saved fingerprint not updated"
        }
    } else {
        Write-DiagLog "SKIP" "Source code unchanged ($currentFp); skipped graph update"
    }

    # Mandatory transient directive requiring Graphify consultation
    $instruction = "MANDATORY GRAPHIFY DIRECTIVE: For this TrustCart task, you must consult the Graphify skill and inspect the local knowledge graph (graphify-out/graph.json). Use scoped graph commands (`graphify path`, `graphify explain`, or `graphify query`) to examine callers, dependencies, data flows, and architectural relationships across domain boundaries (contracts, catalog, policies, orders, payments, trustcart) before implementing, debugging, or modifying code. Verify all critical conclusions against the actual source code and automated tests."

    $output = @{
        injectSteps = @(
            @{
                systemMessage = @{
                    systemMessage = $instruction
                }
            }
        )
    }

    $jsonOutput = $output | ConvertTo-Json -Depth 5 -Compress
    [Console]::Out.WriteLine($jsonOutput)
    exit 0
}

if ($Event -eq 'Stop') {
    $fullyIdle = $true
    if ($inputJson -and $null -ne $inputJson.fullyIdle) {
        $fullyIdle = [bool]$inputJson.fullyIdle
    }

    Write-DiagLog "EVENT" "Stop hook triggered (fullyIdle: $fullyIdle)"

    if ($fullyIdle) {
        $fpInfo = Get-SourceFingerprint $workspaceRoot
        $currentFp = $fpInfo.Fingerprint
        $lastFp = $null
        if (Test-Path $hashFile) {
            $lastFp = [System.IO.File]::ReadAllText($hashFile).Trim()
        }

        if ($currentFp -ne $lastFp) {
            $refreshed = Invoke-GraphifyRefresh "Stop hook detected source change ($lastFp -> $currentFp)"
            if ($refreshed) {
                [System.IO.File]::WriteAllText($hashFile, $currentFp, [System.Text.Encoding]::UTF8)
                Write-DiagLog "FINGERPRINT" "Stop hook saved new fingerprint: $currentFp ($($fpInfo.FileCount) files)"
            } else {
                Write-DiagLog "WARN" "Stop hook refresh failed; fingerprint not updated"
            }
        } else {
            Write-DiagLog "SKIP" "Stop hook skipped update: source code unchanged ($currentFp)"
        }
    } else {
        Write-DiagLog "SKIP" "Stop hook skipped: fullyIdle is false"
    }

    $output = @{
        decision = "allow"
    }
    $jsonOutput = $output | ConvertTo-Json -Depth 5 -Compress
    [Console]::Out.WriteLine($jsonOutput)
    exit 0
}

# Fallback output for any other event
$output = @{}
$jsonOutput = $output | ConvertTo-Json -Depth 2 -Compress
[Console]::Out.WriteLine($jsonOutput)
exit 0
