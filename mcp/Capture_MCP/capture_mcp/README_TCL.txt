==============================================================================
OrCAD Capture 공식 Tcl/Tk 인터페이스 자동화 브릿지 안내
==============================================================================

[개요]
본 패키지는 Cadence OrCAD Capture에서 제공하는 공식 Tcl/Tk 인터페이스를 활용하여,
외부 Python / PySide6 및 AI MCP 서버와 실시간으로 통신할 수 있는 공식 소켓 서버입니다.
Capture 내부의 공식 Tcl 인터프리터 및 Dbo C++ API를 활용하여 신뢰성 높은 제어를 제공합니다.

[설치 방법]
압축 파일의 내용을 아래 Cadence tclscripts 디렉터리에 그대로 압축 해제합니다:
  - 대상 폴더: %CDSROOT%\tools\capture\tclscripts\

압축 해제 후 폴더 구조:
  %CDSROOT%\tools\capture\tclscripts\
    ├── capAutoLoad\
    │     └── capAutoLoad_capture_mcp.tcl   (Capture 시작 시 자동 실행)
    └── capture_mcp\
          ├── capture_mcp_server.tcl        (공식 소켓 서버 코어)
          └── README_TCL.txt                (본 안내문)

[작동 확인]
1. OrCAD Capture를 실행합니다.
2. 하단 Command Window에 다음과 같은 메시지가 출력되면 정상 작동 중입니다:
   ==================================================================
   [Capture MCP] Tcl 공식 인터페이스 소켓 서버가 시작되었습니다.
    - 바인딩 주소 : 127.0.0.1
    - 포트 번호   : 18000
    - 언어/인코딩 : CP949 (시스템 언어)
    - 제어 방식   : Cadence Capture 공식 Tcl & Dbo C++ API
   ==================================================================
3. 수동으로 다시 시작하거나 상태를 확인하려면 Command Window에 아래 명령을 입력합니다:
   - 상태 확인: ::capture_mcp::status
   - 서버 중지: ::capture_mcp::stop_server
   - 서버 시작: ::capture_mcp::start_server 18000
