# ==============================================================================
# 파일명: capture_mcp_server.tcl
# 설명: Cadence OrCAD Capture 내부에서 동작하는 공식 Tcl/Tk 경량 소켓 서버
# 작성일: 2026-10-28
# 인코딩: CP949 (한글 윈도우 시스템 기본 언어)
# ==============================================================================

namespace eval ::capture_mcp {
    # 서버 소켓 핸들
    variable server_socket ""
    # 기본 포트 (기본값: 18000)
    variable port 18000
    # 활성 클라이언트 목록
    variable clients [list]

    # --------------------------------------------------------------------------
    # JSON 인코딩 헬퍼 함수
    # --------------------------------------------------------------------------
    proc escape_json_str {str} {
        set res ""
        set len [string length $str]
        for {set i 0} {$i < $len} {incr i} {
            set c [string index $str $i]
            switch -exact -- $c {
                "\\" { append res "\\\\" }
                "\"" { append res "\\\"" }
                "\b" { append res "\\b" }
                "\f" { append res "\\f" }
                "\n" { append res "\\n" }
                "\r" { append res "\\r" }
                "\t" { append res "\\t" }
                default {
                    append res $c
                }
            }
        }
        return $res
    }

    # --------------------------------------------------------------------------
    # 소켓 서버 시작 함수
    # --------------------------------------------------------------------------
    proc start_server {{listen_port 18000}} {
        variable server_socket
        variable port
        variable clients

        # 기존 서버가 실행 중이면 먼저 중지
        if {$server_socket ne ""} {
            stop_server
        }

        set port $listen_port
        set clients [list]

        # 127.0.0.1 로컬호스트 루프백 바인딩
        if {[catch {
            set server_socket [socket -server ::capture_mcp::accept_client -myaddr 127.0.0.1 $port]
        } err]} {
            puts stderr "\[Capture MCP ERROR\] 서버 소켓 바인딩 실패 ($port): $err"
            return 0
        }

        puts "=================================================================="
        puts "\[Capture MCP\] Tcl 공식 인터페이스 소켓 서버가 시작되었습니다."
        puts " - 바인딩 주소 : 127.0.0.1"
        puts " - 포트 번호   : $port"
        puts " - 언어/인코딩 : CP949 (시스템 언어)"
        puts " - 제어 방식   : Cadence Capture 공식 Tcl & Dbo C++ API"
        puts "=================================================================="
        return 1
    }

    # --------------------------------------------------------------------------
    # 소켓 서버 중지 함수
    # --------------------------------------------------------------------------
    proc stop_server {} {
        variable server_socket
        variable clients

        foreach chan $clients {
            catch {close $chan}
        }
        set clients [list]

        if {$server_socket ne ""} {
            catch {close $server_socket}
            set server_socket ""
            puts "\[Capture MCP\] 소켓 서버가 정상적으로 중지되었습니다."
        }
    }

    # --------------------------------------------------------------------------
    # 새 클라이언트 접속 수락(Accept) 핸들러 (상시 연결 유지)
    # --------------------------------------------------------------------------
    proc accept_client {chan addr client_port} {
        variable clients
        lappend clients $chan

        # 채널 인코딩을 시스템 언어(cp949)로 설정, 지속 연결 유지
        fconfigure $chan -blocking 0 -buffering line -encoding cp949 -translation crlf

        # 읽기 가능 이벤트 발생 시 콜백 등록
        fileevent $chan readable [list ::capture_mcp::handle_client_read $chan]
    }

    # --------------------------------------------------------------------------
    # 클라이언트 명령 수신 및 실행 핸들러
    # --------------------------------------------------------------------------
    proc handle_client_read {chan} {
        variable clients

        set status [gets $chan line]
        if {$status < 0} {
            if {[eof $chan]} {
                catch {close $chan}
                set idx [lsearch -exact $clients $chan]
                if {$idx >= 0} {
                    set clients [lreplace $clients $idx $idx]
                }
            }
            return
        }

        set cmd [string trim $line]
        if {$cmd eq ""} {
            return
        }

        # Tcl 전역 네임스페이스(#0)에서 명령 실행
        set exec_err [catch {uplevel #0 $cmd} exec_result]

        # 응답 JSON 구성 (0=TCL_OK, 2=TCL_RETURN 모두 성공 처리)
        set escaped_result [escape_json_str $exec_result]
        if {$exec_err == 0 || $exec_err == 2} {
            set response "{\"status\":\"ok\",\"result\":\"$escaped_result\"}"
        } else {
            set response "{\"status\":\"error\",\"error\":\"$escaped_result\"}"
        }

        # 결과 전송
        if {[catch {
            puts $chan $response
            flush $chan
        } send_err]} {
            catch {close $chan}
        }
    }

    # --------------------------------------------------------------------------
    # 서버 상태 조회 함수
    # --------------------------------------------------------------------------
    proc status {} {
        variable server_socket
        variable port
        variable clients

        if {$server_socket eq ""} {
            puts "\[Capture MCP\] 서버 상태: 중지됨"
        } else {
            puts "\[Capture MCP\] 서버 상태: 실행 중 (포트: $port, 접속 클라이언트 수: [llength $clients])"
        }
    }
}
