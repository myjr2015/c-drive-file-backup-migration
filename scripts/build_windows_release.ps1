param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$argsList = @("scripts/build_windows_release.py")
if ($SkipTests) {
    $argsList += "--skip-tests"
}
python @argsList
if ($LASTEXITCODE -ne 0) {
    throw "build_windows_release.py failed with exit code $LASTEXITCODE"
}
