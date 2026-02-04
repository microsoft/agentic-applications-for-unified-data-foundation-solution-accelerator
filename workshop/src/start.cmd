@echo off
setlocal enabledelayedexpansion
echo Starting the application setup...

REM Set root and config paths
set ROOT_DIR=%cd%\..
set AZURE_FOLDER=%ROOT_DIR%\.azure
set CONFIG_FILE=%AZURE_FOLDER%\config.json

REM Validate config.json
if not exist "%CONFIG_FILE%" (
    echo config.json not found at %CONFIG_FILE%
    exit /b 1
)

REM Extract default environment name
for /f "delims=" %%i in ('powershell -command "(Get-Content '%CONFIG_FILE%' | ConvertFrom-Json).defaultEnvironment"') do set DEFAULT_ENV=%%i

if not defined DEFAULT_ENV (
    echo Failed to extract defaultEnvironment from config.json
    exit /b 1
)

REM Load .env file
set ENV_FILE=%AZURE_FOLDER%\%DEFAULT_ENV%\.env
if not exist "%ENV_FILE%" (
    echo .env file not found at %ENV_FILE%
    exit /b 1
)

REM Parse required variables from .env
for /f "tokens=1,* delims==" %%A in ('type "%ENV_FILE%"') do (
    if "%%A"=="AZURE_RESOURCE_GROUP" set AZURE_RESOURCE_GROUP=%%~B
    if "%%A"=="AZURE_COSMOSDB_ACCOUNT" set AZURE_COSMOSDB_ACCOUNT=%%~B
    if "%%A"=="SQLDB_SERVER" (
        set SQLDB_SERVER=%%~B
        for /f "tokens=1 delims=." %%C in ("%%~B") do set SQLDB_SERVER_NAME=%%C
    )
)

REM Copy .env to src/api
set API_ENV_FILE=%ROOT_DIR%\src\api\.env
copy /Y "%ENV_FILE%" "%API_ENV_FILE%"
if errorlevel 1 (
    echo Failed to copy .env to src/api
    exit /b 1
)
echo Copied .env to src/api

REM Write API base URL to frontend .env
set APP_ENV_FILE=%ROOT_DIR%\src\App\.env
(
    echo REACT_APP_API_BASE_URL=http://127.0.0.1:8000
) > "%APP_ENV_FILE%"
echo Updated src/App/.env with APP_API_BASE_URL

@REM REM Copy .env to workshop
@REM set MICROHACK_ENV_FILE=%ROOT_DIR%\workshop\docs\workshop\.env
@REM copy /Y "%ENV_FILE%" "%MICROHACK_ENV_FILE%"
@REM if errorlevel 1 (
@REM     echo Failed to copy .env to workshop/docs/workshop
@REM     exit /b 1
@REM )
@REM echo Copied .env to workshop/docs/workshop

REM Define paths
set "SOURCE_ENV_FILE=%ENV_FILE%"
set "TARGET_ENV_FILE=%ROOT_DIR%\workshop\docs\workshop\.env"
set "TEMP_MERGED_FILE=%TEMP%\merged_env.tmp"

REM Ensure the source env file exists
if not exist "%SOURCE_ENV_FILE%" (
    echo Source .env file not found at %SOURCE_ENV_FILE%
    exit /b 1
)

REM Create temporary merged file
copy /Y "%TARGET_ENV_FILE%" "%TEMP_MERGED_FILE%" >nul 2>&1

REM Read lines from SOURCE_ENV_FILE
for /f "usebackq tokens=* delims=" %%A in ("%SOURCE_ENV_FILE%") do (
    set "line=%%A"

    REM Skip empty lines or comments
    if not "!line!"=="" if not "!line:~0,1!"=="#" (

        REM Extract variable name (text before '=')
        for /f "tokens=1 delims==" %%B in ("!line!") do (
            set "var=%%B"

            REM Check if variable already exists in TARGET_ENV_FILE
            findstr /b /i "%%B=" "%TARGET_ENV_FILE%" >nul
            if errorlevel 1 (
                echo !line!>>"%TEMP_MERGED_FILE%"
            ) else (
                echo Skipping existing variable: %%B
            )
        )
    )
)

REM Move merged file back to .env
move /Y "%TEMP_MERGED_FILE%" "%TARGET_ENV_FILE%" >nul
if errorlevel 1 (
    echo Failed to update .env file
    exit /b 1
)

echo Successfully merged .env variables.

REM Authenticate with Azure
echo Checking Azure login status...
call az account show --query id --output tsv >nul 2>&1
if %ERRORLEVEL%==0 (
    echo Already authenticated with Azure.
) else (
    echo Not authenticated. Attempting Azure login...

    call az login --use-device-code --output none

    call az account show --query "[name, id]" --output tsv

    echo Logged in successfully.
)


REM Get signed-in user ID
FOR /F "delims=" %%i IN ('az ad signed-in-user show --query id -o tsv') DO set "signed_user_id=%%i"

REM Check if user has Cosmos DB role
FOR /F "delims=" %%i IN ('az cosmosdb sql role assignment list --resource-group %AZURE_RESOURCE_GROUP% --account-name %AZURE_COSMOSDB_ACCOUNT% --query "[?roleDefinitionId.ends_with(@, '00000000-0000-0000-0000-000000000002') && principalId == '%signed_user_id%']" -o tsv') DO set "roleExists=%%i"
if defined roleExists (
    echo User already has the Cosmos DB Built-in Data Contributor role.
) else (
    echo Assigning Cosmos DB Built-in Data Contributor role...
    set MSYS_NO_PATHCONV=1
    call az cosmosdb sql role assignment create ^
        --resource-group %AZURE_RESOURCE_GROUP% ^
        --account-name %AZURE_COSMOSDB_ACCOUNT% ^
        --role-definition-id 00000000-0000-0000-0000-000000000002 ^
        --principal-id %signed_user_id% ^
        --scope "/" ^
        --output none
)
echo Cosmos DB Built-in Data Contributor role assigned successfully.

REM Assign Azure SQL Server AAD admin
FOR /F "delims=" %%i IN ('az account show --query user.name --output tsv') DO set "SQLADMIN_USERNAME=%%i"
echo Assigning Azure SQL Server AAD admin role to %SQLADMIN_USERNAME%...
call az sql server ad-admin create ^
    --display-name %SQLADMIN_USERNAME% ^
    --object-id "%signed_user_id%" ^
    --resource-group %AZURE_RESOURCE_GROUP% ^
    --server %SQLDB_SERVER_NAME%
    --output tsv >nul 2>&1
echo Azure SQL Server AAD admin role assigned successfully.

echo Proceeding to restore backend Python packages...
REM Restore backend Python packages
cd %ROOT_DIR%\src\api
call python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to restore backend Python packages
    exit /b 1
)
cd %ROOT_DIR%

REM Restore frontend packages
cd %ROOT_DIR%\src\App
call npm install --force
if errorlevel 1 (
    echo Failed to restore frontend npm packages
    exit /b 1
)
cd %ROOT_DIR%

REM Start backend
start cmd /k "cd src\api && python app.py --port=8000"
timeout /t 10 /nobreak >nul

REM Start frontend
start cmd /k "cd src\App && npm start"

echo Backend running at http://127.0.0.1:8000
echo Frontend running at http://localhost:3000

endlocal