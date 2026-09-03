@echo off
REM Instalador Brother ADS-1300 - Agentes Elite (autoarranque)
REM Ejecutar como Administrador la primera vez. Despues solo pulsar "Escanear".

setlocal enabledelayedexpansion
set AGENT_DIR=%LOCALAPPDATA%\AgentesElite
set AGENT_FILE=%AGENT_DIR%\brother_scan_agent.py

echo Instalando agente Brother ADS-1300 en %AGENT_DIR%...

mkdir "%AGENT_DIR%" 2>nul

REM Si el .py esta junto al .bat, copiarlo; si no, descargarlo del servidor
if exist "%~dp0brother_scan_agent.py" (
  copy /Y "%~dp0brother_scan_agent.py" "%AGENT_FILE%" >nul
  echo Copiado desde %~dp0brother_scan_agent.py
) else (
  echo Descargando agente desde el servidor...
  powershell -Command "try { $u='https://gestion.agenteselite.es/static/brother/brother_scan_agent.py'; try { Invoke-WebRequest -Uri $u -OutFile '%AGENT_FILE%' -UseBasicParsing } catch { $u='https://gestion.ocasoarmilla.es/static/brother/brother_scan_agent.py'; Invoke-WebRequest -Uri $u -OutFile '%AGENT_FILE%' -UseBasicParsing }; if (Test-Path '%AGENT_FILE%') { exit 0 } else { exit 1 } } catch { exit 1 }"
  if errorlevel 1 (
    echo ERROR: No se pudo descargar brother_scan_agent.py
    echo Descargalo manualmente de https://gestion.agenteselite.es/static/brother/brother_scan_agent.py
    echo y colocalo junto a este .bat, luego vuelve a ejecutar.
    pause
    exit /b 1
  )
  echo Descargado correctamente.
)

if not exist "%AGENT_FILE%" (
  echo ERROR: No se encontro %AGENT_FILE%
  pause
  exit /b 1
)

REM Dependencias (silencioso)
echo Instalando dependencias...
python -m pip install --quiet flask flask-cors pillow >nul 2>&1
if errorlevel 1 py -m pip install --quiet flask flask-cors pillow >nul 2>&1
if errorlevel 1 python3 -m pip install --quiet flask flask-cors pillow >nul 2>&1

REM Crear tarea programada que arranca al iniciar sesion
echo Creando tarea de autoarranque...
schtasks /create /tn "AgentesElite Brother Agent" /tr "pythonw \"%AGENT_FILE%\"" /sc onlogon /rl limited /f >nul 2>&1
if errorlevel 1 (
  echo No se pudo crear la tarea programada, creando acceso directo en Inicio...
  powershell -Command "$W=New-Object -ComObject WScript.Shell; $S=$W.CreateShortcut(\"$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\AgentesElite Brother.lnk\"); $S.TargetPath='pythonw'; $S.Arguments='\"%AGENT_FILE%\"'; $S.WorkingDirectory='%AGENT_DIR%'; $S.Save()"
  if errorlevel 1 (
    echo ERROR: No se pudo crear el acceso directo.
  ) else (
    echo Acceso directo creado en Inicio.
  )
) else (
  echo Tarea programada creada.
)

echo.
echo Instalado. El agente arrancara solo al iniciar Windows.
echo Arrancando ahora...
start "" pythonw "%AGENT_FILE%"
timeout /t 2 >nul
echo Listo. Ya puedes pulsar "Escanear" en la ficha del cliente sin volver a ejecutar nada.
pause
