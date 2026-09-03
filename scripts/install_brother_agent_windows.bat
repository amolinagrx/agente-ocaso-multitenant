@echo off
REM Instalador Brother ADS-1300 - Agentes Elite (autoarranque)
REM Ejecutar como Administrador la primera vez. Despues el usuario solo pulsa "Escanear".

set AGENT_DIR=%LOCALAPPDATA%\AgentesElite
set AGENT_FILE=%AGENT_DIR%\brother_scan_agent.py

echo Instalando agente Brother ADS-1300 en %AGENT_DIR%...

mkdir "%AGENT_DIR%" 2>nul
copy /Y "%~dp0brother_scan_agent.py" "%AGENT_FILE%"

REM Dependencias (silencioso)
python -m pip install --quiet flask flask-cors pillow 2>nul
if errorlevel 1 py -m pip install --quiet flask flask-cors pillow 2>nul

REM Crear tarea programada que arranca al iniciar sesion (sin pedir script)
schtasks /create /tn "AgentesElite Brother Agent" /tr "pythonw \"%AGENT_FILE%\"" /sc onlogon /rl limited /f >nul 2>&1
if errorlevel 1 (
  echo No se pudo crear la tarea automatica. Se creara acceso directo en Inicio.
  mkdir "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup" 2>nul
  echo Set oWS = CreateObject("WScript.Shell") > "%TEMP%\c.vbs"
  echo sLinkFile = "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\AgentesElite Brother.lnk" >> "%TEMP%\c.vbs"
  echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%TEMP%\c.vbs"
  echo oLink.TargetPath = "pythonw" >> "%TEMP%\c.vbs"
  echo oLink.Arguments = """%AGENT_FILE%""" >> "%TEMP%\c.vbs"
  echo oLink.Save >> "%TEMP%\c.vbs"
  cscript "%TEMP%\c.vbs" //nologo >nul
  del "%TEMP%\c.vbs"
)

echo.
echo Instalado. El agente arrancara solo al iniciar Windows.
echo Arrancando ahora...
start "" pythonw "%AGENT_FILE%"
timeout /t 2 >nul
echo Listo. Ya puedes pulsar "Escanear" en la ficha del cliente sin volver a ejecutar nada.
pause
