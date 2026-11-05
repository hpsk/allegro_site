# -*- coding: utf-8 -*-
"""
파일명: tcl_bridge.py
설명: Cadence OrCAD Capture 공식 Tcl/Tk 소켓 서버(Port 18000)와 통신하는 순수 Python 브릿지
작성일: 2026-10-28
특징:
  - Python 표준 라이브러리(socket, json)만 사용하여 공식적이고 안전하게 동작
  - UTF-8 인코딩 및 자동 재연결/에러 핸들링 지원
"""

import socket
import json
import sys
import time
from typing import Dict, Any, Optional

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 18000
TIMEOUT_SEC = 5.0


class CaptureTclClient:
    """OrCAD Capture Tcl 소켓 서버와 통신하는 공식 브릿지 클라이언트"""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = TIMEOUT_SEC):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None

    def connect(self) -> bool:
        """Tcl 소켓 서버에 연결을 시도합니다."""
        self.close()
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # TCP Keep-Alive 상시 연결 유지 활성화
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self.sock.settimeout(self.timeout)
            self.sock.connect((self.host, self.port))
            return True
        except (socket.error, ConnectionRefusedError) as e:
            self.sock = None
            return False

    def close(self):
        """연결을 종료합니다."""
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def is_connected(self) -> bool:
        """연결 상태를 확인합니다."""
        return self.sock is not None

    def eval_tcl(self, tcl_code: str, auto_reconnect: bool = True) -> Dict[str, Any]:
        """
        OrCAD Capture Tcl 인터프리터에 명령을 전송하고 결과를 반환받습니다.
        
        Args:
            tcl_code: 실행할 Tcl 스크립트 (한 줄 또는 세미콜론/이스케이프 처리된 문자열)
            auto_reconnect: 연결 끊김 시 자동 재접속 시도 여부
            
        Returns:
            dict: {"status": "ok"|"error", "result": "...", "error": "..."}
        """
        # 줄바꿈 문자를 공백이나 세미콜론으로 정규화
        clean_cmd = tcl_code.strip()
        if not clean_cmd:
            return {"status": "ok", "result": ""}

        # 연결이 끊어져 있으면 재연결
        if not self.is_connected():
            if not self.connect():
                return {
                    "status": "error",
                    "error": (
                        f"OrCAD Capture Tcl 서버(127.0.0.1:{self.port})에 연결할 수 없습니다.\n"
                        "OrCAD Capture가 실행 중인지 확인하시고,\n"
                        f"Command Window에서 '::capture_mcp::status' 또는 '::capture_mcp::start_server {self.port}'를 실행해 주세요."
                    )
                }

        try:
            # 한글 윈도우 OrCAD 시스템 기본 인코딩(CP949) 및 CRLF 전송
            send_data = clean_cmd.encode("cp949", errors="replace") + b"\r\n"
            self.sock.sendall(send_data)

            # 응답 수신 (줄 단위)
            buffer = b""
            while b"\n" not in buffer:
                chunk = self.sock.recv(4096)
                if not chunk:
                    raise ConnectionResetError("OrCAD Tcl 서버와의 연결이 끊어졌습니다.")
                buffer += chunk

            line = buffer.decode("cp949", errors="replace").strip()
            # JSON 파싱 시도
            try:
                res_obj = json.loads(line)
                return res_obj
            except json.JSONDecodeError:
                return {"status": "ok", "result": line}

        except (socket.timeout, socket.error, ConnectionResetError) as e:
            self.close()
            if auto_reconnect:
                # 1회 재시도
                if self.connect():
                    return self.eval_tcl(clean_cmd, auto_reconnect=False)
            return {
                "status": "error",
                "error": f"Tcl 통신 오류 발생: {str(e)}"
            }


# 전역 싱글톤 인스턴스
_global_client = None

def get_tcl_client(port: int = DEFAULT_PORT) -> CaptureTclClient:
    """싱글톤 Tcl 소켓 클라이언트를 반환합니다."""
    global _global_client
    if _global_client is None or _global_client.port != port:
        _global_client = CaptureTclClient(port=port)
    return _global_client

def send_tcl_command(tcl_cmd: str, port: int = DEFAULT_PORT) -> Dict[str, Any]:
    """간편하게 Tcl 명령을 실행하는 헬퍼 함수"""
    client = get_tcl_client(port)
    return client.eval_tcl(tcl_cmd)


if __name__ == "__main__":
    # CLI 모드: 인자가 있으면 해당 Tcl 명령을 실행하고, 없으면 연결 테스트 수행
    args = sys.argv[1:]
    client = get_tcl_client()

    if args:
        cmd = " ".join(args)
        res = client.eval_tcl(cmd)
        if res.get("status") == "ok":
            print(res.get("result", ""))
            sys.exit(0)
        else:
            print(f"[ERROR] {res.get('error', 'Unknown error')}", file=sys.stderr)
            sys.exit(1)
    else:
        print("[Tcl Bridge 테스트] 127.0.0.1:18000 연결 테스트...")
        if client.connect():
            print(">> 연결 성공! Capture Tcl 버전 확인 중...")
            res = client.eval_tcl("info patchlevel")
            print(">> 응답:", res)
            client.close()
        else:
            print(">> 연결 실패: OrCAD Capture가 실행 중인지 확인해주세요.")
