# ==============================================================================
# 파일명: capAutoLoad_capture_mcp.tcl
# 설명: OrCAD Capture 시작 시 자동으로 capture_mcp 소켓 서버를 로드하는 시작 스크립트
# 설치 위치: %CDSROOT%\tools\capture\tclscripts\capAutoLoad\
# 작성일: 2026-10-28
# 인코딩: CP949 (한글 윈도우 시스템 기본 언어)
# ==============================================================================

proc capAutoLoad_capture_mcp_init {} {
    # 현재 스크립트 디렉터리 확인
    set scriptDir [file normalize [file dirname [info script]]]
    
    # 상위 디렉터리 기준 capture_mcp/capture_mcp_server.tcl 경로 계산
    set mcpServerPath [file normalize [file join $scriptDir ".." "capture_mcp" "capture_mcp_server.tcl"]]
    
    if {[file exists $mcpServerPath]} {
        # 서버 스크립트 로드
        if {[catch {source $mcpServerPath} err]} {
            puts stderr "\[Capture MCP\] 서버 스크립트 로드 실패: $err"
            return
        }
        
        # 18000 포트로 소켓 서버 자동 시작
        if {[catch {::capture_mcp::start_server 18000} srvErr]} {
            puts stderr "\[Capture MCP\] 소켓 서버 자동 시작 실패: $srvErr"
        }
    } else {
        puts stderr "\[Capture MCP\] capture_mcp_server.tcl 파일을 찾을 수 없습니다: $mcpServerPath"
    }
}

# Capture 기동 시 초기화 함수 실행
capAutoLoad_capture_mcp_init
