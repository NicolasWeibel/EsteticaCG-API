param(
    [string]$Service = "estetica-api-production",
    [string]$Region = "southamerica-east1",
    [string]$EnvFile = ".env.production"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $EnvFile)) {
    throw "No se encontro el archivo de entorno: $EnvFile"
}

$tempEnvFile = Join-Path $env:TEMP "cloudrun-production-env.yaml"
$yamlLines = New-Object System.Collections.Generic.List[string]

foreach ($line in Get-Content $EnvFile) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#")) {
        continue
    }

    $separatorIndex = $line.IndexOf("=")
    if ($separatorIndex -lt 1) {
        throw "Linea invalida en ${EnvFile}: $line"
    }

    $key = $line.Substring(0, $separatorIndex).Trim()
    $value = $line.Substring($separatorIndex + 1)
    $escapedValue = $value.Replace("'", "''")
    $yamlLines.Add("$key`: '$escapedValue'")
}

Set-Content -Path $tempEnvFile -Value $yamlLines -Encoding UTF8

try {
    gcloud run deploy $Service `
        --source . `
        --region $Region `
        --allow-unauthenticated `
        --env-vars-file $tempEnvFile
}
finally {
    if (Test-Path $tempEnvFile) {
        Remove-Item $tempEnvFile -Force
    }
}
