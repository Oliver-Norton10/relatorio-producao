@echo off
cd /d "%~dp0"
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
if not exist dados\entrada\ordens_producao.csv python -m src.gerar_dados
python -m src.main
echo.
pause
