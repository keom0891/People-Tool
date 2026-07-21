@echo off
cd /d "%~dp0"

REM Try to find Anaconda/Miniconda automatically
set "CONDA_BAT="

if exist "%USERPROFILE%\anaconda3\condabin\conda.bat" set "CONDA_BAT=%USERPROFILE%\anaconda3\condabin\conda.bat"
if exist "%USERPROFILE%\miniconda3\condabin\conda.bat" set "CONDA_BAT=%USERPROFILE%\miniconda3\condabin\conda.bat"
if exist "C:\ProgramData\anaconda3\condabin\conda.bat" set "CONDA_BAT=C:\ProgramData\anaconda3\condabin\conda.bat"
if exist "C:\ProgramData\miniconda3\condabin\conda.bat" set "CONDA_BAT=C:\ProgramData\miniconda3\condabin\conda.bat"

if "%CONDA_BAT%"=="" (
    echo Could not find Anaconda or Miniconda automatically.
    echo Open Anaconda Prompt manually, go to this folder, and run:
    echo streamlit run app.py
    pause
    exit /b 1
)

call "%CONDA_BAT%" activate base

streamlit run app.py

pause
