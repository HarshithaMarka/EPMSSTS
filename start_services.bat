@echo off
REM Start EPMSSTS services
echo.
echo ========================================
echo EPMSSTS - Starting Services
echo ========================================
echo.

REM Check if ports are available
echo [CHECK] Checking if required ports are available...
netstat -ano | findstr :8000 > nul 2>&1
IF NOT ERRORLEVEL 1 (
    echo [WARNING] Port 8000 is already in use!
    echo Please close the existing process or use a different port.
    pause
    exit /b 1
)

netstat -ano | findstr :5173 > nul 2>&1
IF NOT ERRORLEVEL 1 (
    echo [WARNING] Port 5173 is already in use!
    echo Please close the existing process or use a different port.
    pause
    exit /b 1
)

echo [OK] Ports are available
echo.

REM Start Backend
echo [START] Starting Backend (FastAPI) on port 8000...
echo Opening new terminal window...
start "EPMSSTS Backend" cmd /k "cd /d %cd% && %USERPROFILE%\Miniconda3\Scripts\activate.bat && uvicorn epmssts.api.main:app --reload --port 8000"
echo.

REM Wait for backend to start
echo [WAIT] Waiting for backend to initialize (5 seconds)...
timeout /t 5 /nobreak > nul

REM Start Frontend
echo.
echo [START] Starting Frontend (Vite/React) on port 5173...
echo Opening new terminal window...
start "EPMSSTS Frontend" cmd /k "cd /d %cd%\web && npm run dev"
echo.

echo ========================================
echo ✅ Services Started!
echo ========================================
echo.
echo 📍 Backend API:  http://localhost:8000
echo 🌐 Frontend UI:  http://localhost:5173
echo.
echo Press any key to close this window...
pause
