@echo off
REM 🚀 MCP Testing Suite - Zero Friction Launcher (Windows)
REM Just run START.bat and everything works!

echo 🚀 Starting MCP Testing Suite...
echo ⏱️  This takes ~15 seconds...
echo.

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python 3 is required but not found
    echo Please install Python 3 and try again
    pause
    exit /b 1
)

REM Check if we're in the right directory
if not exist "launcher\main.py" (
    echo ❌ Please run this script from the MCP_Testing_Tools directory
    echo cd MCP_Testing_Tools && START.bat
    pause
    exit /b 1
)

REM Find available port (start from 8094)
set LAUNCHER_PORT=8094

REM Kill any existing launcher processes
echo 🧹 Cleaning up any existing processes...
taskkill /f /im python.exe >nul 2>&1

REM Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo 📦 Creating virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
echo 🔌 Activating virtual environment...
call .venv\Scripts\activate.bat

REM Install/upgrade dependencies
echo ⬇️  Installing dependencies...
pip install --quiet --upgrade pip
pip install --quiet fastapi uvicorn requests aiofiles python-multipart

REM Check for Docker (optional)
docker --version >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Docker not found - some features will use mock mode
    set DOCKER_AVAILABLE=false
) else (
    echo ✅ Docker found - full functionality available
    set DOCKER_AVAILABLE=true
)

REM Set environment variables
set MCP_TESTING_SUITE_DOCKER_AVAILABLE=%DOCKER_AVAILABLE%
set MCP_TESTING_SUITE_PORT=%LAUNCHER_PORT%
set MCP_TESTING_SUITE_AUTO_OPEN=true

REM Start the launcher
echo 🚀 Starting MCP Testing Suite launcher...
echo.

cd launcher
start "MCP Testing Suite" python main.py --port=%LAUNCHER_PORT% --auto-open

REM Wait for launcher to start
timeout /t 3 /nobreak >nul

echo.
echo 🎉 MCP Testing Suite is RUNNING!
echo.
echo 🌐 Web Interface: http://localhost:%LAUNCHER_PORT%
echo.
echo 🎯 Choose your adventure:
echo    🧪 Interactive - Test MCP tools Postman-style
echo    🔧 API Mode - Headless testing ^& automation
echo    📊 Monitoring - Server health ^& performance
echo    🔒 Enterprise - Security ^& policy enforcement
echo.
echo 💡 TIP: Try the demo modes if you don't have MCP servers yet!
echo.
echo Your browser should open automatically...
echo Press any key to exit
pause >nul