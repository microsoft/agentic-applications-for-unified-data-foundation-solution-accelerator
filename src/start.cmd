@echo off
setlocal enabledelayedexpansion
echo Starting the application setup...

REM Set root and config paths (resolve relative to script location, not cwd)
set "ROOT_DIR=%~dp0.."
set "AZURE_FOLDER=%ROOT_DIR%\.azure"
set "CONFIG_FILE=%AZURE_FOLDER%\config.json"
set "API_PYTHON_ENV_FILE=%ROOT_DIR%\src\api\python\.env"
set "API_DOTNET_DIR=%ROOT_DIR%\src\api\dotnet"

REM ============================================================
REM  Locate .env file (Azure deployment or local fallback)
REM ============================================================

REM Check if .azure folder exists
if not exist "%AZURE_FOLDER%" (
    echo .azure folder not found. This is normal if Azure deployment hasn't been run yet.
    goto :check_local_env
)

REM Check if config.json exists
if not exist "%CONFIG_FILE%" (
    echo config.json not found in .azure folder. This is normal if Azure deployment hasn't been run yet.
    goto :check_local_env
)

REM Extract default environment name
for /f "delims=" %%i in ('powershell -command "try { (Get-Content '%CONFIG_FILE%' | ConvertFrom-Json).defaultEnvironment } catch { '' }"') do set "DEFAULT_ENV=%%i"

if not defined DEFAULT_ENV (
    echo Failed to extract defaultEnvironment from config.json.
    goto :check_local_env
)

REM Load .env file from Azure deployment
set "ENV_FILE=%AZURE_FOLDER%\%DEFAULT_ENV%\.env"

if exist "%ENV_FILE%" (
    echo Found .env file in Azure deployment folder: %ENV_FILE%

    REM Pre-check backend runtime stack from Azure .env
    set "_PRE_STACK="
    for /f "tokens=1,* delims==" %%A in ('findstr /b "BACKEND_RUNTIME_STACK=" "%ENV_FILE%"') do set "_PRE_STACK=%%~B"

    REM Check if backend config already exists and ask for overwrite
    if /i "!_PRE_STACK!"=="dotnet" (
        if exist "%API_DOTNET_DIR%\appsettings.json" (
            echo Found existing appsettings.json in src\api\dotnet
            set /p OVERWRITE_ENV="Do you want to overwrite it with the Azure deployment .env? (y/N): "
            if /i "!OVERWRITE_ENV!" neq "y" (
                echo Preserving existing appsettings.json. Using local configuration.
                set "SKIP_DOTNET_CONFIG=true"
            ) else (
                echo Overwriting with Azure deployment configuration...
            )
        )
    ) else (
        if exist "%API_PYTHON_ENV_FILE%" (
            echo Found existing .env file in src\api\python
            set /p OVERWRITE_ENV="Do you want to overwrite it with the Azure deployment .env? (y/N): "
            if /i "!OVERWRITE_ENV!"=="y" (
                echo Overwriting with Azure deployment configuration...
            ) else (
                echo Preserving existing .env files. Using local configuration.
                set "ENV_FILE=%API_PYTHON_ENV_FILE%"
            )
        )
    )
    goto :setup_environment
)

:check_local_env
echo Checking for local .env files...

REM Check python subfolder
if exist "%API_PYTHON_ENV_FILE%" (
    echo Using existing .env file from src\api\python for configuration.
    set "ENV_FILE=%API_PYTHON_ENV_FILE%"
    goto :setup_environment
)

REM Check parent api folder as legacy fallback
if exist "%ROOT_DIR%\src\api\.env" (
    echo Using existing .env file from src\api for configuration.
    set "ENV_FILE=%ROOT_DIR%\src\api\.env"
    goto :setup_environment
)

echo.
echo ERROR: No .env files found in any location.
echo.
echo Please choose one of the following options:
echo   1. Run 'azd up' to deploy Azure resources and generate .env files
echo   2. Manually create %API_PYTHON_ENV_FILE% with required environment variables
echo   3. Copy an existing .env file to src\api\python\.env
echo.
exit /b 1

:setup_environment
echo.
echo Using environment file: %ENV_FILE%

REM ============================================================
REM  Parse required variables from .env
REM ============================================================
for /f "tokens=1,* delims==" %%A in ('type "%ENV_FILE%"') do (
    if "%%A"=="AZURE_RESOURCE_GROUP" set "AZURE_RESOURCE_GROUP=%%~B"
    if "%%A"=="AZURE_COSMOSDB_ACCOUNT" set "AZURE_COSMOSDB_ACCOUNT=%%~B"
    if "%%A"=="BACKEND_RUNTIME_STACK" set "BACKEND_RUNTIME_STACK=%%~B"
    if "%%A"=="IS_WORKSHOP" set "IS_WORKSHOP=%%~B"
    if "%%A"=="AZURE_ENV_ONLY" set "AZURE_ENV_ONLY=%%~B"
    if "%%A"=="AGENT_NAME_CHAT" set "AGENT_NAME_CHAT=%%~B"
    if "%%A"=="AGENT_NAME_TITLE" set "AGENT_NAME_TITLE=%%~B"
    if "%%A"=="AI_FOUNDRY_RESOURCE_ID" set "AI_FOUNDRY_RESOURCE_ID=%%~B"
    if "%%A"=="FABRIC_SQL_SERVER" set "FABRIC_SQL_SERVER=%%~B"
    if "%%A"=="FABRIC_SQL_DATABASE" set "FABRIC_SQL_DATABASE=%%~B"
    if "%%A"=="FABRIC_SQL_CONNECTION_STRING" set "FABRIC_SQL_CONNECTION_STRING=%%~B"
    if "%%A"=="USE_CHAT_HISTORY_ENABLED" set "USE_CHAT_HISTORY_ENABLED=%%~B"
    if "%%A"=="API_UID" set "API_UID=%%~B"
    if "%%A"=="APPINSIGHTS_INSTRUMENTATIONKEY" set "APPINSIGHTS_INSTRUMENTATIONKEY=%%~B"
    if "%%A"=="APPLICATIONINSIGHTS_CONNECTION_STRING" set "APPLICATIONINSIGHTS_CONNECTION_STRING=%%~B"
    if "%%A"=="AZURE_AI_AGENT_API_VERSION" set "AZURE_AI_AGENT_API_VERSION=%%~B"
    if "%%A"=="AZURE_AI_AGENT_ENDPOINT" set "AZURE_AI_AGENT_ENDPOINT=%%~B"
    if "%%A"=="AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME" set "AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME=%%~B"
    if "%%A"=="AZURE_ENV_OPENAI_API_VERSION" set "AZURE_ENV_OPENAI_API_VERSION=%%~B"
    if "%%A"=="AZURE_OPENAI_API_VERSION" set "AZURE_OPENAI_API_VERSION=%%~B"
    if "%%A"=="AZURE_ENV_GPT_MODEL_NAME" set "AZURE_ENV_GPT_MODEL_NAME=%%~B"
    if "%%A"=="AZURE_OPENAI_DEPLOYMENT_MODEL" set "AZURE_OPENAI_DEPLOYMENT_MODEL=%%~B"
    if "%%A"=="AZURE_OPENAI_ENDPOINT" set "AZURE_OPENAI_ENDPOINT=%%~B"
    if "%%A"=="AZURE_OPENAI_RESOURCE" set "AZURE_OPENAI_RESOURCE=%%~B"
    if "%%A"=="DISPLAY_CHART_DEFAULT" set "DISPLAY_CHART_DEFAULT=%%~B"
    if "%%A"=="REACT_APP_LAYOUT_CONFIG" set "REACT_APP_LAYOUT_CONFIG=%%~B"
    if "%%A"=="SOLUTION_NAME" set "SOLUTION_NAME=%%~B"
    if "%%A"=="USE_AI_PROJECT_CLIENT" set "USE_AI_PROJECT_CLIENT=%%~B"
    if "%%A"=="AZURE_SQLDB_SERVER" (
        set "AZURE_SQLDB_SERVER=%%~B"
        for /f "tokens=1 delims=." %%C in ("%%~B") do set "AZURE_SQLDB_SERVER_NAME=%%C"
    )
    if "%%A"=="SQLDB_SERVER" (
        set "SQLDB_SERVER=%%~B"
        for /f "tokens=1 delims=." %%C in ("%%~B") do set "SQLDB_SERVER_NAME=%%C"
    )
)

REM Fallback: AZURE_ENV_GPT_MODEL_NAME falls back to AZURE_OPENAI_DEPLOYMENT_MODEL
if not defined AZURE_ENV_GPT_MODEL_NAME (
    if defined AZURE_OPENAI_DEPLOYMENT_MODEL set "AZURE_ENV_GPT_MODEL_NAME=!AZURE_OPENAI_DEPLOYMENT_MODEL!"
)

REM Fallback: AZURE_ENV_OPENAI_API_VERSION falls back to AZURE_OPENAI_API_VERSION
if not defined AZURE_ENV_OPENAI_API_VERSION (
    if defined AZURE_OPENAI_API_VERSION set "AZURE_ENV_OPENAI_API_VERSION=!AZURE_OPENAI_API_VERSION!"
)

REM Fallback: AZURE_SQLDB_SERVER falls back to SQLDB_SERVER
if not defined AZURE_SQLDB_SERVER (
    if defined SQLDB_SERVER (
        set "AZURE_SQLDB_SERVER=!SQLDB_SERVER!"
        set "AZURE_SQLDB_SERVER_NAME=!SQLDB_SERVER_NAME!"
    )
)

REM Normalize booleans to lowercase
if /i "!IS_WORKSHOP!"=="true" (set "IS_WORKSHOP=true") else (set "IS_WORKSHOP=false")
if /i "!AZURE_ENV_ONLY!"=="true" (set "AZURE_ENV_ONLY=true") else (set "AZURE_ENV_ONLY=false")

REM Default USE_CHAT_HISTORY_ENABLED to true if not set (for existing deployments)
if not defined USE_CHAT_HISTORY_ENABLED (
    set "USE_CHAT_HISTORY_ENABLED=true"
) else (
    if /i "!USE_CHAT_HISTORY_ENABLED!"=="true" (set "USE_CHAT_HISTORY_ENABLED=true") else (set "USE_CHAT_HISTORY_ENABLED=false")
)

REM Default backend to python if not set
if not defined BACKEND_RUNTIME_STACK set "BACKEND_RUNTIME_STACK=python"

echo.
echo Configuration:
echo   BACKEND_RUNTIME_STACK=%BACKEND_RUNTIME_STACK%
echo   IS_WORKSHOP=%IS_WORKSHOP%
echo   AZURE_ENV_ONLY=%AZURE_ENV_ONLY%
echo   USE_CHAT_HISTORY_ENABLED=%USE_CHAT_HISTORY_ENABLED%
echo.

REM ============================================================
REM  Read agent names and Fabric SQL settings from config files
REM ============================================================
set "AGENT_IDS_FILE=%ROOT_DIR%\data\default\config\agent_ids.json"
set "FABRIC_IDS_FILE=%ROOT_DIR%\data\default\config\fabric_ids.json"

REM Get agent names from env first, fallback to agent_ids.json
if not defined AGENT_NAME_CHAT (
    if exist "%AGENT_IDS_FILE%" (
        for /f "delims=" %%i in ('powershell -command "(Get-Content '%AGENT_IDS_FILE%' | ConvertFrom-Json).chat_agent_name"') do set "AGENT_NAME_CHAT=%%i"
        for /f "delims=" %%i in ('powershell -command "(Get-Content '%AGENT_IDS_FILE%' | ConvertFrom-Json).title_agent_name"') do set "AGENT_NAME_TITLE=%%i"
        echo Loaded agent names from agent_ids.json: AGENT_NAME_CHAT=!AGENT_NAME_CHAT!, AGENT_NAME_TITLE=!AGENT_NAME_TITLE!
    ) else (
        echo [WARN] agent_ids.json not found at %AGENT_IDS_FILE%. Agent names will not be configured.
    )
) else (
    echo Loaded agent names from env: AGENT_NAME_CHAT=!AGENT_NAME_CHAT!, AGENT_NAME_TITLE=!AGENT_NAME_TITLE!
)

REM Load Fabric SQL settings (needed unless workshop + azure-only mode)
REM Python code: get_db_connection() uses Azure SQL only when IS_WORKSHOP=true AND AZURE_ENV_ONLY=true
REM All other combinations use Fabric SQL
set "USE_FABRIC_SQL=true"
if "%IS_WORKSHOP%"=="true" if "%AZURE_ENV_ONLY%"=="true" set "USE_FABRIC_SQL=false"

if "%USE_FABRIC_SQL%"=="true" (
    if not defined FABRIC_SQL_SERVER (
        if exist "%FABRIC_IDS_FILE%" (
            for /f "delims=" %%i in ('powershell -command "(Get-Content '%FABRIC_IDS_FILE%' | ConvertFrom-Json).sql_endpoint"') do set "FABRIC_SQL_SERVER=%%i"
            for /f "delims=" %%i in ('powershell -command "(Get-Content '%FABRIC_IDS_FILE%' | ConvertFrom-Json).lakehouse_name"') do set "FABRIC_SQL_DATABASE=%%i"
            echo Loaded Fabric SQL from fabric_ids.json: SERVER=!FABRIC_SQL_SERVER!, DATABASE=!FABRIC_SQL_DATABASE!
        ) else (
            echo [WARN] Fabric SQL mode required but fabric_ids.json not found. Database connections may fail.
        )
    ) else (
        echo Loaded Fabric SQL from env: SERVER=!FABRIC_SQL_SERVER!, DATABASE=!FABRIC_SQL_DATABASE!
    )
) else (
    echo Using Azure SQL mode ^(IS_WORKSHOP=true, AZURE_ENV_ONLY=true^). AZURE_SQLDB_SERVER=%AZURE_SQLDB_SERVER%
)

REM ============================================================
REM  Configure backend .env / appsettings
REM ============================================================

REM --- Python backend configuration ---
if /i "%BACKEND_RUNTIME_STACK%"=="python" (
    REM Guard: skip copy when source and destination are the same file
    for %%I in ("%ENV_FILE%") do set "ENV_FILE_RESOLVED=%%~fI"
    for %%I in ("%API_PYTHON_ENV_FILE%") do set "API_PYTHON_ENV_FILE_RESOLVED=%%~fI"
    if /i "!ENV_FILE_RESOLVED!"=="!API_PYTHON_ENV_FILE_RESOLVED!" (
        echo Python .env source and destination are the same file; skipping copy.
    ) else (
        copy /Y "%ENV_FILE%" "%API_PYTHON_ENV_FILE%" >nul
    )

    if defined AGENT_NAME_CHAT (
        call :upsert_env "AGENT_NAME_CHAT" "!AGENT_NAME_CHAT!" "%API_PYTHON_ENV_FILE%"
        call :upsert_env "AGENT_NAME_TITLE" "!AGENT_NAME_TITLE!" "%API_PYTHON_ENV_FILE%"
    )
    REM Upsert Fabric SQL settings when needed
    if "%USE_FABRIC_SQL%"=="true" if defined FABRIC_SQL_SERVER (
        call :upsert_env "FABRIC_SQL_SERVER" "!FABRIC_SQL_SERVER!" "%API_PYTHON_ENV_FILE%"
        call :upsert_env "FABRIC_SQL_DATABASE" "!FABRIC_SQL_DATABASE!" "%API_PYTHON_ENV_FILE%"
    )

    REM Add or update APP_ENV=dev in python .env file
    call :upsert_env "APP_ENV" "dev" "%API_PYTHON_ENV_FILE%"
    echo Configured src\api\python\.env
)

REM --- Dotnet backend configuration ---
if /i "%BACKEND_RUNTIME_STACK%"=="dotnet" if exist "%API_DOTNET_DIR%" (
    if /i "!SKIP_DOTNET_CONFIG!"=="true" (
        echo Preserving existing src\api\dotnet\appsettings.json
    ) else (
        REM Validate template file exists
        if not exist "!API_DOTNET_DIR!\appsettings.json.sample" (
            echo ERROR: Missing required template file "!API_DOTNET_DIR!\appsettings.json.sample"
            exit /b 1
        )
        REM Build appsettings.json from env values using PowerShell
        echo Generating src\api\dotnet\appsettings.json from environment values...

        powershell -command ^
            "$json = Get-Content '!API_DOTNET_DIR!\appsettings.json.sample' -Raw | ConvertFrom-Json;" ^
            "$json.'FABRIC_SQL_CONNECTION_STRING' = '!FABRIC_SQL_CONNECTION_STRING!';" ^
            "$json.'FABRIC_SQL_DATABASE' = '!FABRIC_SQL_DATABASE!';" ^
            "$json.'FABRIC_SQL_SERVER' = '!FABRIC_SQL_SERVER!';" ^
            "$json.'APP_ENV' = 'dev';" ^
            "$json.'AGENT_NAME_CHAT' = '!AGENT_NAME_CHAT!';" ^
            "$json.'AGENT_NAME_TITLE' = '!AGENT_NAME_TITLE!';" ^
            "$json.'API_UID' = '!API_UID!';" ^
            "$json.'APPINSIGHTS_INSTRUMENTATIONKEY' = '!APPINSIGHTS_INSTRUMENTATIONKEY!';" ^
            "$json.'APPLICATIONINSIGHTS_CONNECTION_STRING' = '!APPLICATIONINSIGHTS_CONNECTION_STRING!';" ^
            "$json.'AZURE_AI_AGENT_API_VERSION' = '!AZURE_AI_AGENT_API_VERSION!';" ^
            "$json.'AZURE_AI_AGENT_ENDPOINT' = '!AZURE_AI_AGENT_ENDPOINT!';" ^
            "$json.'AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME' = '!AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME!';" ^
            "$json.'AZURE_ENV_OPENAI_API_VERSION' = '!AZURE_ENV_OPENAI_API_VERSION!';" ^
            "$json.'AZURE_ENV_GPT_MODEL_NAME' = '!AZURE_ENV_GPT_MODEL_NAME!';" ^
            "$json.'AZURE_OPENAI_ENDPOINT' = '!AZURE_OPENAI_ENDPOINT!';" ^
            "$json.'AZURE_OPENAI_RESOURCE' = '!AZURE_OPENAI_RESOURCE!';" ^
            "$json.'DISPLAY_CHART_DEFAULT' = '!DISPLAY_CHART_DEFAULT!';" ^
            "$json.'SOLUTION_NAME' = '!SOLUTION_NAME!';" ^
            "$json.'USE_AI_PROJECT_CLIENT' = '!USE_AI_PROJECT_CLIENT!';" ^
            "$json.'USE_CHAT_HISTORY_ENABLED' = '!USE_CHAT_HISTORY_ENABLED!';" ^
            "$json | ConvertTo-Json -Depth 10 | Set-Content '!API_DOTNET_DIR!\appsettings.json' -Encoding UTF8"

        echo Configured src\api\dotnet\appsettings.json with environment values
    )
)

REM Set process env vars for local development (dotnet inherits these via IConfiguration)
set "APP_ENV=dev"

REM ============================================================
REM  Write frontend .env
REM ============================================================
set "APP_ENV_FILE=%ROOT_DIR%\src\App\.env"
(
    echo REACT_APP_API_BASE_URL=http://127.0.0.1:8000
    echo REACT_APP_IS_WORKSHOP=%IS_WORKSHOP%
    echo REACT_APP_CHAT_LANDING_TEXT=You can ask questions around sales, products and orders.
) > "%APP_ENV_FILE%"
echo Updated src\App\.env with frontend configuration

REM ============================================================
REM  Authenticate with Azure
REM ============================================================
echo.
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

REM ============================================================
REM  Cosmos DB role assignment (only when account is configured)
REM ============================================================
if not defined AZURE_COSMOSDB_ACCOUNT goto :skip_cosmos
if "!AZURE_COSMOSDB_ACCOUNT!"=="" goto :skip_cosmos

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
    echo Cosmos DB Built-in Data Contributor role assigned successfully.
)
goto :done_cosmos

:skip_cosmos
echo [INFO] No Cosmos DB account configured, skipping role assignment.

:done_cosmos

REM ============================================================
REM  Azure SQL Server AAD admin (only when AZURE_SQLDB_SERVER is set)
REM ============================================================
if not defined AZURE_SQLDB_SERVER goto :skip_sql
if "!AZURE_SQLDB_SERVER!"=="" goto :skip_sql

FOR /F "delims=" %%i IN ('az account show --query user.name --output tsv') DO set "SQLADMIN_USERNAME=%%i"
echo Assigning Azure SQL Server AAD admin role to %SQLADMIN_USERNAME%...
call az sql server ad-admin create ^
    --display-name %SQLADMIN_USERNAME% ^
    --object-id "%signed_user_id%" ^
    --resource-group %AZURE_RESOURCE_GROUP% ^
    --server %AZURE_SQLDB_SERVER_NAME% ^
    --output tsv >nul 2>&1
echo Azure SQL Server AAD admin role assigned successfully.
goto :done_sql

:skip_sql
echo [INFO] No Azure SQL Server configured, skipping admin role assignment.

:done_sql

REM ============================================================
REM  Azure AI User role assignment (only when AI_FOUNDRY_RESOURCE_ID is set)
REM ============================================================
if not defined AI_FOUNDRY_RESOURCE_ID goto :skip_aiuser
if "!AI_FOUNDRY_RESOURCE_ID!"=="" goto :skip_aiuser

FOR /F "delims=" %%s IN ('az account show --query id -o tsv') DO set "subscription_id=%%s"

echo Checking Azure AI User role assignment...
FOR /F "delims=" %%i IN ('az role assignment list --assignee %signed_user_id% --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" --scope "%AI_FOUNDRY_RESOURCE_ID%" --query "[0].id" -o tsv 2^>nul') DO set "aiUserRoleExists=%%i"
if defined aiUserRoleExists (
    echo User already has the Azure AI User role.
) else (
    echo Assigning Azure AI User role to AI Foundry account...
    call az role assignment create ^
        --assignee %signed_user_id% ^
        --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" ^
        --scope "%AI_FOUNDRY_RESOURCE_ID%" ^
        --output none
    echo Azure AI User role assigned successfully.
)
goto :done_aiuser

:skip_aiuser
echo [INFO] No AI Foundry resource configured, skipping AI User role assignment.

:done_aiuser

REM ============================================================
REM  Restore and start backend
REM ============================================================
if /i "%BACKEND_RUNTIME_STACK%"=="dotnet" (
    echo.
    echo Restoring dotnet backend packages...
    cd "%ROOT_DIR%\src\api\dotnet"
    call dotnet restore --verbosity quiet
    if errorlevel 1 (
        echo Failed to restore dotnet backend packages
        exit /b 1
    )
    cd "%ROOT_DIR%"
) else (
    echo.
    REM Create virtual environment if it doesn't exist
    cd "%ROOT_DIR%"
    if not exist ".venv" (
        echo Creating Python virtual environment...
        call python -m venv .venv
        if errorlevel 1 (
            echo Failed to create virtual environment
            exit /b 1
        )
        echo Virtual environment created successfully.
    ) else (
        echo Virtual environment already exists.
    )

    REM Activate virtual environment and install packages
    echo Activating virtual environment and installing backend packages...
    call .venv\Scripts\activate.bat
    call python -m pip install --upgrade pip --quiet
    call python -m pip install uv --quiet
    cd "%ROOT_DIR%\src\api\python"
    call python -m uv pip install -r requirements.txt
    if errorlevel 1 (
        echo Failed to restore backend Python packages
        call deactivate
        exit /b 1
    )
    echo Backend Python packages installed successfully.
    call deactivate
    cd "%ROOT_DIR%"
)

REM Restore frontend packages
echo Restoring frontend npm packages...
cd "%ROOT_DIR%\src\App"
call npm install --force
if errorlevel 1 (
    echo Failed to restore frontend npm packages
    exit /b 1
)
cd "%ROOT_DIR%"

REM Check for existing processes on ports 8000 and 3000 before starting
for %%P in (8000 3000) do (
    for /f "tokens=5" %%A in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":%%P "') do (
        if "%%A" neq "0" (
            echo Port %%P is already in use by PID %%A.
            set /p "KILL_PORT=Do you want to stop it? (Y/N): "
            if /i "!KILL_PORT!"=="Y" (
                taskkill /F /PID %%A /T >nul 2>&1
                echo Stopped PID %%A on port %%P.
            ) else (
                echo WARNING: Port %%P is still in use. The server may fail to start.
            )
        )
    )
)

REM Start backend in background, frontend in foreground (single terminal window)
echo.
if /i "%BACKEND_RUNTIME_STACK%"=="dotnet" (
    echo Starting dotnet backend...
    cd "%ROOT_DIR%\src\api\dotnet"
    start /b dotnet run --urls=http://127.0.0.1:8000
) else (
    echo Starting Python backend...
    cd "%ROOT_DIR%"
    call .venv\Scripts\activate.bat
    cd src\api\python
    start /b python app.py --port=8000
)
echo Backend started at http://127.0.0.1:8000

echo Waiting for backend to initialize...
timeout /t 10 /nobreak >nul

echo Starting frontend server...
cd "%ROOT_DIR%\src\App"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try { npm start } finally {" ^
    "  Write-Host '';" ^
    "  Write-Host 'Stopping all processes...';" ^
    "  Start-Sleep -Milliseconds 500;" ^
    "  @(8000, 3000) | ForEach-Object {" ^
    "    $port = $_;" ^
    "    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |" ^
    "      ForEach-Object {" ^
    "        $pid_ = $_.OwningProcess;" ^
    "        if ($pid_ -and $pid_ -ne 0) {" ^
    "          taskkill /F /PID $pid_ /T 2>$null;" ^
    "        }" ^
    "      }" ^
    "  };" ^
    "  Write-Host 'Cleanup complete.';" ^
    "  Write-Host '';" ^
    "  Write-Host 'All servers stopped. Press Y or N to exit.' -ForegroundColor Yellow" ^
    "}"

REM Fallback cleanup in case PowerShell finally block was interrupted
for %%P in (8000 3000) do (
    for /f "tokens=5" %%A in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":%%P "') do (
        if "%%A" neq "0" (
            taskkill /F /PID %%A /T >nul 2>&1
        )
    )
)

endlocal
exit /b 0

:upsert_env
REM Usage: call :upsert_env "KEY" "VALUE" "FILE"
setlocal enabledelayedexpansion
set "UKEY=%~1"
set "UVAL=%~2"
set "UFILE=%~3"
findstr /i /b "!UKEY!=" "!UFILE!" >nul 2>&1
if !ERRORLEVEL!==0 (
    powershell -command "(Get-Content '!UFILE!') -replace '^!UKEY!=.*', '!UKEY!=!UVAL!' | Set-Content '!UFILE!'"
) else (
    echo !UKEY!=!UVAL!>>"!UFILE!"
)
endlocal
exit /b 0