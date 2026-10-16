@echo off
REM ========================================================
REM 파일명: install_requirements.bat
REM 설명: RLC BPF 시뮬레이터 구동에 필요한 Python 라이브러리 자동 설치 스크립트
REM 인코딩: UTF-8 (CRLF 개행)
REM ========================================================

REM 콘솔 코드페이지를 UTF-8(65001)로 설정하여 한글 깨짐을 방지합니다.
chcp 65001 > nul

REM 콘솔 창의 제목(Title)을 설정합니다.
title Python 라이브러리 자동 설치 - RLC BPF Simulator

REM 배치 파일이 위치한 프로젝트 기준 폴더로 작업 디렉터리를 변경합니다.
cd /d "%~dp0"

REM 시작 안내 헤더를 콘솔 화면에 출력합니다.
echo ========================================================
echo  [RLC BPF Simulator] 필수 Python 라이브러리 설치 시작
echo ========================================================
echo.

REM 시스템에 Python이 설치되어 있는지 확인합니다.
python --version > nul 2>&1
if errorlevel 1 goto PYTHON_NOT_FOUND

REM 현재 설치되어 있는 파이썬 버전을 화면에 표시합니다.
echo [1/3] Python 환경 확인 완료:
python --version
echo.

REM 안정적인 패키지 설치를 위해 pip 도구를 최신 버전으로 업데이트합니다.
echo [2/3] pip 패키지 관리자 최신 버전 업데이트 진행 중...
python -m pip install --upgrade pip
echo.

REM 라이브러리 목록 파일(requirements.txt)이 존재하는지 확인합니다.
if exist requirements.txt goto INSTALL_FROM_REQ
goto INSTALL_DIRECT

:INSTALL_FROM_REQ
REM requirements.txt 파일에 명시된 라이브러리들을 일괄 설치합니다.
echo [3/3] requirements.txt 파일 기반 라이브러리 설치 중...
python -m pip install -r requirements.txt
if errorlevel 1 goto INSTALL_FAILED
goto INSTALL_SUCCESS

:INSTALL_DIRECT
REM requirements.txt가 없을 경우 필수 라이브러리를 직접 지정하여 설치합니다.
echo [3/3] 필수 라이브러리(PySide6, numpy, matplotlib, pyinstaller) 설치 중...
python -m pip install PySide6 numpy matplotlib pyinstaller
if errorlevel 1 goto INSTALL_FAILED
goto INSTALL_SUCCESS

:PYTHON_NOT_FOUND
REM Python이 설치되지 않았거나 PATH에 등록되지 않았을 때의 안내 메시지입니다.
echo.
echo ========================================================
echo [오류] Python이 시스템에 설치되어 있지 않거나 환경 변수(PATH)에 등록되지 않았습니다.
echo - https://www.python.org 에서 Python(3.8 이상 권장)을 다운로드하여 설치해 주세요.
echo - 설치 시 반드시 'Add Python to PATH' 옵션을 체크해야 합니다.
echo ========================================================
echo.
pause
exit /b 1

:INSTALL_FAILED
REM 패키지 설치 도중 네트워크 오류나 권한 오류가 발생했을 때의 안내 메시지입니다.
echo.
echo ========================================================
echo [오류] 라이브러리 설치 도중 문제가 발생했습니다.
echo - 인터넷 연결 상태를 확인해 주세요.
echo - 필요한 경우 관리자 권한으로 실행하거나 보안 프로그램을 확인해 주세요.
echo ========================================================
echo.
pause
exit /b 1

:INSTALL_SUCCESS
REM 모든 라이브러리가 성공적으로 설치 완료되었을 때의 안내 메시지입니다.
echo.
echo ========================================================
echo [성공] 모든 필수 라이브러리가 성공적으로 설치되었습니다!
echo 이제 'run_gui.bat'을 더블 클릭하여 프로그램을 바로 실행하실 수 있습니다.
echo ========================================================
echo.
pause
exit /b 0
