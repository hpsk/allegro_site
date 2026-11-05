@echo off
rem ==============================================================================
rem OrCAD Capture Tcl 자동화 스크립트 설치 및 배포 배치 파일 (install_tcl_scripts.bat)
rem 설명: %CDSROOT%\tools\capture\tclscripts 디렉터리에 필수 Tcl 스크립트를 자동 복사합니다.
rem ==============================================================================

chcp 65001 >nul
echo [Capture MCP] Tcl 자동화 스크립트 설치를 시작합니다...
echo.

rem 1. 현재 배치 파일 디렉터리 기준 tcl_release 소스 경로 설정
set "SRC_DIR=%~dp0tcl_release"
if not exist "%SRC_DIR%" (
    echo [오류] tcl_release 폴더를 찾을 수 없습니다: %SRC_DIR%
    pause
    exit /b 1
)

rem 2. Cadence 설치 루트 디렉터리 확인 (%CDSROOT%)
set "CADENCE_ROOT=%CDSROOT%"

if "%CADENCE_ROOT%"=="" (
    echo [알림] CDSROOT 환경 변수가 설정되어 있지 않습니다. 기본 설치 경로를 탐색합니다...
    if exist "C:\Cadence\SPB_17.4" (
        set "CADENCE_ROOT=C:\Cadence\SPB_17.4"
    ) else if exist "C:\Cadence\SPB_22.1" (
        set "CADENCE_ROOT=C:\Cadence\SPB_22.1"
    ) else (
        echo [오류] Cadence 설치 경로를 찾을 수 없습니다.
        echo       시스템 환경 변수에 CDSROOT를 설정하거나 Cadence 설치 폴더를 확인해 주세요.
        pause
        exit /b 1
    )
)

echo - Cadence 루트 경로: %CADENCE_ROOT%

rem 3. 복사 대상 tclscripts 디렉터리 설정
set "TARGET_DIR=%CADENCE_ROOT%\tools\capture\tclscripts"
echo - 대상 설치 경로   : %TARGET_DIR%
echo.

if not exist "%TARGET_DIR%" (
    echo [오류] OrCAD Capture tclscripts 폴더가 존재하지 않습니다: %TARGET_DIR%
    pause
    exit /b 1
)

rem 4. 하위 대상 디렉터리 생성 (존재하지 않을 경우)
if not exist "%TARGET_DIR%\capAutoLoad" mkdir "%TARGET_DIR%\capAutoLoad"
if not exist "%TARGET_DIR%\capture_mcp" mkdir "%TARGET_DIR%\capture_mcp"

rem 5. Tcl 스크립트 파일 복사 (capAutoLoad 및 capture_mcp)
echo [복사 중] capAutoLoad_capture_mcp.tcl 복사...
copy /Y "%SRC_DIR%\capAutoLoad\capAutoLoad_capture_mcp.tcl" "%TARGET_DIR%\capAutoLoad\capAutoLoad_capture_mcp.tcl"
if errorlevel 1 (
    echo [오류] capAutoLoad_capture_mcp.tcl 복사 실패! [관리자 권한 필요]
    pause
    exit /b 1
)

echo [복사 중] capture_mcp 폴더 파일 복사...
copy /Y "%SRC_DIR%\capture_mcp\*.*" "%TARGET_DIR%\capture_mcp\*.*"
if errorlevel 1 (
    echo [오류] capture_mcp 폴더 파일 복사 실패! [관리자 권한 필요]
    pause
    exit /b 1
)

echo.
echo ==============================================================================
echo [설치 완료] OrCAD Capture Tcl 자동화 스크립트가 성공적으로 복사되었습니다!
echo.
echo  - 시작 스크립트 : %TARGET_DIR%\capAutoLoad\capAutoLoad_capture_mcp.tcl
echo  - 서버 스크립트 : %TARGET_DIR%\capture_mcp\capture_mcp_server.tcl
echo.
echo 이제 OrCAD Capture를 실행하면
echo 소켓 서버(포트 18000)가 백그라운드에서 자동으로 기동됩니다.
echo ==============================================================================
echo.
pause
