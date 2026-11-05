# OrCAD Capture Tcl Socket Bridge (orcad-tcl-bridge)

Cadence OrCAD Capture의 **공식 Tcl/Tk 인터프리터**와 외부 프로그램(Python, Node.js, AI 에이전트 등) 간에 실시간으로 **TCL 커맨드를 송수신하고 결과를 반환받는 초경량 소켓 브릿지 시스템**입니다.

OLB 파서나 외부 무거운 라이브러리 의존성 없이, **오직 TCL 커맨드 실행 및 결과 반환에만 집중된 미니멀 패키지**입니다.

---

## 1. 핵심 특징

- **100% 공식 지원 인터페이스**: Cadence OrCAD Capture가 기본 제공하는 공식 Tcl/Tk 콘솔 및 Dbo C++ API만을 사용합니다.
- **포트 18000 상시 유지 (Keep-Alive)**: 단일 소켓 상시 연결 및 요청 큐(Queue) 구조로 지연 없이 초고속 커맨드 실행.
- **외부 의존성 제로 (Zero-Dependency)**:
  - Python: 외부 모듈 설치 불필요 (`socket`, `json` 등 표준 라이브러리만 사용)
  - Node.js: `net` 표준 모듈만 사용
- **한글 윈도우 환경 완벽 호환**: 소켓 통신 채널을 CP949로 동기화하여 한글 도면명, 한글 속성 및 경로 깨짐 방지.
- **자동 기동 지원**: `capAutoLoad` 방식을 채택하여 OrCAD Capture 실행 시 백그라운드 리스너 자동 실행.

---

## 2. 파일 구성

```
orcad-tcl-bridge/
├── capAutoLoad/
│   └── capAutoLoad_capture_mcp.tcl   # OrCAD 기동 시 소켓 서버 자동 실행 부트스트랩
├── capture_mcp/
│   ├── capture_mcp_server.tcl        # 로컬 TCP 소켓 서버 (Port 18000, Tcl 명령 수신 및 JSON 응답)
│   └── README_TCL.txt                # OrCAD 콘솔 수동 제어 명령어 안내문
├── install_tcl_scripts.bat           # %CDSROOT%\tools\capture\tclscripts 에 자동 복사하는 배치 파일
├── tcl_bridge.py                     # Python Tcl 소켓 클라이언트 (CLI 실행 및 Python 모듈)
├── bridge.cjs                        # Node.js Tcl 소켓 클라이언트 (비동기 큐 소켓 브릿지)
└── README.md                         # 본 안내서
```

---

## 3. 설치 방법 (1초 원클릭 설치)

1. 저장소를 클론하거나 압축을 풉니다.
2. **`install_tcl_scripts.bat`** 파일을 더블 클릭하여 실행합니다.
   - 시스템 환경변수 `%CDSROOT%` 또는 기본 설치 경로(`C:\Cadence\SPB_17.4`, `C:\Cadence\SPB_22.1`)를 자동으로 감지하여 `tools\capture\tclscripts\` 폴더에 필수 Tcl 파일들을 복사합니다.

### 수동 설치를 원하는 경우
아래 대상 디렉터리에 `capAutoLoad` 폴더와 `capture_mcp` 폴더를 직접 복사하시면 됩니다:
- 대상: `<Cadence설치경로>\tools\capture\tclscripts\`

---

## 4. 작동 확인

1. **OrCAD Capture**를 실행합니다.
2. 하단 **Command Window**에 아래 환영 배너가 나타나면 정상 구동된 것입니다:

```
==================================================================
[Capture MCP] Tcl 공식 인터페이스 소켓 서버가 시작되었습니다.
 - 바인딩 주소 : 127.0.0.1
 - 포트 번호   : 18000
 - 언어/인코딩 : CP949 (시스템 언어)
 - 제어 방식   : Cadence Capture 공식 Tcl & Dbo C++ API
==================================================================
```

---

## 5. TCL 커맨드 전송 방법

### 5.1 Python 환경

#### A. 터미널 CLI에서 단발 실행
```bash
# 1. 활성 페이지 객체 확인
python tcl_bridge.py "GetActivePage"

# 2. OrCAD Tcl 버전 확인
python tcl_bridge.py "info patchlevel"

# 3. 화면 전체 보기 실행
python tcl_bridge.py "Menu \"View::Zoom::All\""

# 4. 연산 실행
python tcl_bridge.py "expr 100 + 200"
```

#### B. Python 코드에서 모듈로 호출
```python
from tcl_bridge import send_tcl_command

# Tcl 명령 전송
response = send_tcl_command('GetActivePage')
print("응답:", response)
# 출력 예시: {'status': 'ok', 'result': '_DboPage_p'}

# Tcl 스크립트 블록 실행
script = """
set lPage [GetActivePage]
set lName [DboTclHelper_sMakeCString]
$lPage GetName $lName
DboTclHelper_sGetConstCharPtr $lName
"""
res = send_tcl_command(script)
print("현재 열린 페이지 이름:", res.get("result"))
```

---

### 5.2 Node.js 환경

```javascript
const { evalTcl } = require('./bridge.cjs');

async function main() {
    // 단일 명령어 실행
    const res = await evalTcl('GetActivePage');
    console.log('실행 결과:', res);

    // 복합 Tcl 스크립트 실행
    const tcl = `
        set lPage [GetActivePage]
        set w [$lPage GetPageWidth]
        set h [$lPage GetPageHeight]
        return "PAGE_SIZE: $w x $h"
    `;
    const sizeRes = await evalTcl(tcl);
    console.log(sizeRes.result);
}

main();
```

---

## 6. OrCAD Command Window 수동 제어 명령어

OrCAD 하단 Command Window에서 직접 입력할 수 있는 Tcl 프로시저:

| 명령어 | 설명 |
|:---|:---|
| `::capture_mcp::status` | 소켓 서버 상태 및 접속 클라이언트 수 확인 |
| `::capture_mcp::stop_server` | 실행 중인 소켓 서버 중지 |
| `::capture_mcp::start_server 18000` | 포트 18000에서 소켓 서버 다시 시작 |

---

## 7. 통신 프로토콜 규격

- **통신 방식**: TCP Socket (`127.0.0.1:18000`, `SO_KEEPALIVE`)
- **줄바꿈 및 인코딩**: `\r\n` (CRLF), `CP949`
- **응답 규격 (JSON)**:
  - 성공 시: `{"status": "ok", "result": "..."}`
  - 에러 시: `{"status": "error", "error": "..."}`
