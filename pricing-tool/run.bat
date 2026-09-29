@echo off
setlocal
cd /d "%~dp0"

rem Roda o simulador no Windows sem exigir Python instalado.
rem O uv cuida de baixar o Python 3.12 e as dependencias na primeira execucao.

set "UV=uv"
where uv >nul 2>&1 || set "UV=%USERPROFILE%\.local\bin\uv.exe"

if not "%UV%"=="uv" if not exist "%UV%" (
    echo.
    echo Instalando o uv ...
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 goto :falhou_uv
)

if not "%UV%"=="uv" if not exist "%UV%" set "UV=%USERPROFILE%\.cargo\bin\uv.exe"
if not "%UV%"=="uv" if not exist "%UV%" goto :falhou_uv

echo Preparando o ambiente ...
"%UV%" run --python 3.12 main.py
if errorlevel 1 goto :falhou_app

endlocal
exit /b 0

:falhou_uv
echo.
echo Nao foi possivel instalar o uv.
echo Verifique a conexao com a internet e tente de novo, ou instale o Python 3.12 manualmente.
echo.
pause
exit /b 1

:falhou_app
echo.
echo O simulador terminou com erro. A mensagem acima explica o motivo.
echo.
pause
exit /b 1
