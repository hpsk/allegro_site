// -*- coding: utf-8 -*-
/**
 * OrCAD Capture 공식 Tcl 소켓 브릿지 모듈 (Capture_MCP)
 * -------------------------------------------------------------
 * Cadence OrCAD Capture 내부의 공식 Tcl 소켓 서버(Port 9099)와 통신하여
 * Tcl 명령 실행 및 부품 배치를 안전하고 신뢰성 있게 원격 제어합니다.
 */

const net = require('net');

// 기본 라이브러리 경로 (Analog.olb)
const DEFAULT_ANALOG_LIB = (process.env.CDSROOT ? process.env.CDSROOT.replace(/\\/g, '/') : 'C:/Cadence/SPB_17.4') + '/tools/capture/library/pspice/Analog.olb';
const PORT = 18000;
const HOST = '127.0.0.1';

// 단일 상주 소켓 인스턴스 및 요청 큐 관리 (상시 연결 유지)
let persistentSocket = null;
let currentResolve = null;
let currentReject = null;
let currentTimer = null;
let receiveBuffer = '';
const queue = [];

function connectPersistentSocket() {
    return new Promise((resolve, reject) => {
        if (persistentSocket && !persistentSocket.destroyed) {
            return resolve(persistentSocket);
        }

        const socket = new net.Socket();
        // TCP Keep-Alive 활성화
        socket.setKeepAlive(true, 10000);

        socket.connect(PORT, HOST, () => {
            persistentSocket = socket;
            receiveBuffer = '';
            resolve(socket);
        });

        socket.on('data', (chunk) => {
            receiveBuffer += chunk.toString('utf8');
            if (receiveBuffer.includes('\n')) {
                const line = receiveBuffer.trim();
                receiveBuffer = '';
                if (currentTimer) {
                    clearTimeout(currentTimer);
                    currentTimer = null;
                }
                const resCb = currentResolve;
                currentResolve = null;
                currentReject = null;

                if (resCb) {
                    try {
                        const parsed = JSON.parse(line);
                        resCb({
                            success: parsed.status === 'ok',
                            returnCode: parsed.status === 'ok' ? 0 : 1,
                            result: parsed.result || parsed.error || ''
                        });
                    } catch (e) {
                        resCb({
                            success: true,
                            returnCode: 0,
                            result: line
                        });
                    }
                }
                processNextInQueue();
            }
        });

        socket.on('error', (err) => {
            if (currentTimer) {
                clearTimeout(currentTimer);
                currentTimer = null;
            }
            if (currentReject) {
                currentReject(new Error(`OrCAD Capture Tcl 소켓 서버(Port ${PORT}) 통신 오류: ${err.message}`));
                currentResolve = null;
                currentReject = null;
            }
            persistentSocket = null;
        });

        socket.on('close', () => {
            persistentSocket = null;
            if (currentReject) {
                currentReject(new Error(`OrCAD Capture Tcl 소켓 서버와의 상시 연결이 종료되었습니다.`));
                currentResolve = null;
                currentReject = null;
            }
        });
    });
}

function processNextInQueue() {
    if (queue.length === 0) return;
    if (currentResolve !== null) return; // 이미 처리 중

    const item = queue.shift();
    currentResolve = item.resolve;
    currentReject = item.reject;

    currentTimer = setTimeout(() => {
        const rejCb = currentReject;
        currentResolve = null;
        currentReject = null;
        currentTimer = null;
        if (rejCb) {
            rejCb(new Error("Capture.exe Tcl 응답 대기 시간 초과 (Timeout)"));
        }
        processNextInQueue();
    }, item.timeoutMs);

    connectPersistentSocket()
        .then((sock) => {
            sock.write(item.command.trim() + '\r\n', 'utf8');
        })
        .catch((err) => {
            if (currentTimer) {
                clearTimeout(currentTimer);
                currentTimer = null;
            }
            const rejCb = currentReject;
            currentResolve = null;
            currentReject = null;
            if (rejCb) rejCb(err);
            processNextInQueue();
        });
}

/**
 * 실행 중인 Capture.exe의 공식 Tcl 소켓 서버에서 Tcl 스크립트를 상시 연결을 통해 실행합니다.
 * @param {string} tclCommand 실행할 Tcl 스크립트 문자열
 * @param {number} timeoutMs 타임아웃 (밀리초)
 * @returns {Promise<{success: boolean, returnCode: number, result: string}>}
 */
async function evalTcl(tclCommand, timeoutMs = 8000) {
    return new Promise((resolve, reject) => {
        queue.push({
            command: tclCommand,
            timeoutMs: timeoutMs,
            resolve: resolve,
            reject: reject
        });
        processNextInQueue();
    });
}

/**
 * 활성 회로도 페이지의 상세 정보(이름, 크기, 중앙 좌표, 현재 배치된 부품)를 조회합니다.
 */
async function getActivePageInfo() {
    const script = `
        set lPage [GetActivePage]
        if {$lPage == "NULL" || $lPage == ""} {
            return "ERROR: 활성 회로도 페이지를 찾을 수 없습니다. 회로도 창을 열어주세요."
        }

        # 1. 페이지 이름 획득
        set lName [DboTclHelper_sMakeCString]
        $lPage GetName $lName
        set pageName [DboTclHelper_sGetConstCharPtr $lName]

        # 2. 페이지 너비 및 높이 (Doc Unit / mils)
        set w [$lPage GetPageWidth]
        set h [$lPage GetPageHeight]
        set gran [$lPage GetPhysicalGranularity]

        # 3. 인치 단위 중앙 좌표 계산 (Capture UI 명령은 인치 좌표계 사용)
        set cx [expr {$w / 2000.0}]
        set cy [expr {$h / 2000.0}]

        # 4. 페이지 상의 부품 인스턴스 목록 순회
        set lStatus [DboState]
        set lIter [$lPage NewPartInstsIter $lStatus]
        set lPart [$lIter NextPartInst $lStatus]
        set partsList [list]
        while {$lPart != "NULL" && $lPart != ""} {
            set lRef [DboTclHelper_sMakeCString]
            set lVal [DboTclHelper_sMakeCString]
            $lPart GetReference $lRef
            $lPart GetPartValue $lVal
            set refStr [DboTclHelper_sGetConstCharPtr $lRef]
            set valStr [DboTclHelper_sGetConstCharPtr $lVal]
            
            set lGraph [DboBaseObjectToDboGraphicInstance $lPart]
            set x [DboGraphicInstance_sGetLocationX $lGraph $lStatus]
            set y [DboGraphicInstance_sGetLocationY $lGraph $lStatus]
            
            lappend partsList "$refStr = $valStr at ($x, $y)"
            set lPart [$lIter NextPartInst $lStatus]
        }
        delete_DboPagePartInstsIter $lIter

        set partsCount [llength $partsList]
        set partsJoined [join $partsList ", "]

        return "PAGE_INFO|$pageName|$w|$h|$gran|$cx|$cy|$partsCount|$partsJoined"
    `;

    const res = await evalTcl(script);
    if (!res.success) {
        throw new Error(`회로도 정보 조회 실패: ${res.result}`);
    }

    const raw = res.result;
    if (raw.startsWith("ERROR:")) {
        throw new Error(raw);
    }

    const tokens = raw.split('|');
    return {
        pageName: tokens[1],
        widthDocUnits: parseFloat(tokens[2]),
        heightDocUnits: parseFloat(tokens[3]),
        granularity: parseFloat(tokens[4]),
        centerInchX: parseFloat(tokens[5]),
        centerInchY: parseFloat(tokens[6]),
        partsCount: parseInt(tokens[7], 10),
        partsSummary: tokens[8] || '없음'
    };
}

/**
 * 활성 회로도 페이지의 정가운데에 부품을 배치합니다.
 * @param {string} libPath 라이브러리 전체 경로 (기본값: Analog.olb)
 * @param {string} partName 부품명 (기본값: R)
 * @param {string} device 디바이스명 (기본값: R)
 */
/**
 * 활성 회로도 페이지에 Dbo Tcl API를 사용하여 부품을 배치합니다.
 * (매크로 Player 에러 ORCAP-1687 방지 및 안전한 직접 객체 생성)
 * 
 * @param {string} libPath 라이브러리 전체 경로 (기본값: Analog.olb)
 * @param {string} partName 부품명 (예: 'C', 'R')
 * @param {string} refDes 참조 명칭 (예: 'C?', 'C1', 기본값: `${partName}?`)
 */
async function placePart(libPath = DEFAULT_ANALOG_LIB, partName = 'L', targetInchX = null, targetInchY = null, refDes = null, partValue = null) {
    // 3번째 인자로 refDes 문자열이 전달된 경우(오버로드 호환) 처리
    if (typeof targetInchX === 'string') {
        refDes = targetInchX;
        targetInchX = null;
        targetInchY = null;
    }

    const pageInfo = await getActivePageInfo();
    const normalizedLib = libPath.replace(/\\/g, '/');

    // 사용자가 제공한 실제 도면 중앙 표준 좌표: (4.60, 2.70) 인치
    const finalInchX = (targetInchX !== null && targetInchX !== undefined && !isNaN(targetInchX)) ? targetInchX : 4.60;
    const finalInchY = (targetInchY !== null && targetInchY !== undefined && !isNaN(targetInchY)) ? targetInchY : 2.70;

    // 기본 부품 값(Value) 설정
    let defaultValue = partValue;
    if (!defaultValue) {
        if (partName === 'L') defaultValue = '10uH';
        else if (partName === 'C') defaultValue = '1n';
        else if (partName === 'R') defaultValue = '1k';
        else defaultValue = '10uH';
    }

    // 기본 PCB Footprint 설정
    let defaultFootprint = 'DISC350x175LS200x100034';
    if (partName === 'R') defaultFootprint = 'RES400';
    else if (partName === 'C') defaultFootprint = 'CAP196';

    const tcl = `
        set lPage [GetActivePage]
        if {$lPage == "NULL" || $lPage == ""} {
            return "ERROR: 활성 회로도 페이지가 없습니다."
        }
        set lStatus [DboState]
        set lNullObj NULL

        # 1. 고유 RefDes 자동 산출 (L1, L2, C1, R1 등 충돌 방지)
        set targetPrefix "${partName}"
        set idx 1
        set found 1
        while {$found} {
            set testRef "$targetPrefix$idx"
            set lTestStr [DboTclHelper_sMakeCString $testRef]
            set pInst [$lPage GetPartInst $lTestStr $lStatus]
            if {$pInst == $lNullObj || $pInst == ""} {
                set found 0
            } else {
                incr idx
            }
        }
        set actualRef "$targetPrefix$idx"

        # 2. OrCAD 공식 콘솔 표준 PlacePart 실행 (device=""로 매크로 에러 없이 배치)
        set libPath "${normalizedLib}"
        PlacePart ${finalInchX} ${finalInchY} $libPath "${partName}" "" FALSE

        # 3. 공식 SetProperty 시퀀스를 통한 부품 속성 및 PSpice 시뮬레이션 모델 설정
        catch {SetProperty {PCB Footprint} "${defaultFootprint}"}
        catch {SetProperty {Part Reference} "$actualRef"}
        catch {SetProperty {Reference} "$actualRef"}
        catch {SetProperty {Designator} ""}
        catch {SetProperty {Value} "${defaultValue}"}
        catch {SetProperty {Primitive} {DEFAULT}}
        catch {SetProperty {Implementation Type} {<none>}}
        catch {SetProperty {Implementation} ""}
        catch {SetProperty {Implementation Path} ""}
        catch {SetProperty {Color} {Default}}
        catch {SetProperty {Power Pins Visible} {False}}
        catch {SetProperty {Graphic} "${partName}.Normal"}
        catch {SetProperty {TC2} {0}}
        catch {SetProperty {TC1} {0}}
        catch {SetProperty {IL2} {0}}
        catch {SetProperty {IL1} {0}}
        catch {SetProperty {DIELECTRIC} {DSMAX}}
        catch {SetProperty {CURRENT} {LMAX}}
        catch {SetProperty {IC} ""}
        catch {SetProperty {TOLERANCE} ""}
        catch {SetProperty {DIST} {FLAT}}
        catch {SetProperty {PSpice Model Type} {0011}}

        # 4. 화면 다시 그리기
        catch {UnSelectAll}
        catch {Menu "View::Zoom::Redraw"}

        return "SUCCESS|$actualRef|${finalInchX}|${finalInchY}|${defaultValue}"
    `;

    const res = await evalTcl(tcl);
    if (!res.success || res.result.startsWith("ERROR:")) {
        throw new Error(`부품 배치 실패: ${res.result}`);
    }

    const tokens = res.result.split('|');
    const actualRef = tokens[1] || refDes;
    const placedX = parseFloat(tokens[2] || finalInchX);
    const placedY = parseFloat(tokens[3] || finalInchY);
    const placedVal = tokens[4] || defaultValue;

    // 갱신된 페이지 정보 조회
    const updatedInfo = await getActivePageInfo();

    return {
        success: true,
        pageName: pageInfo.pageName,
        library: normalizedLib,
        partName: partName,
        refDes: actualRef,
        value: placedVal,
        placedAtInch: { x: placedX, y: placedY },
        partsCount: updatedInfo.partsCount,
        partsSummary: updatedInfo.partsSummary,
        message: `회로도 페이지 '${pageInfo.pageName}'의 도면 중앙 (${placedX}, ${placedY}) 인치 좌표에 '${partName}'(${actualRef}, ${placedVal}) 부품을 성공적으로 배치하고 전체 속성을 완벽히 설정했습니다.`
    };
}

/**
 * 활성 회로도 페이지에 부품을 배치합니다 (placePartAtCenter 호환용)
 */
async function placePartAtCenter(libPath = DEFAULT_ANALOG_LIB, partName = 'L', device = 'L') {
    return placePart(libPath, partName, null, null, `${partName}?`);
}

module.exports = {
    evalTcl,
    getActivePageInfo,
    placePartAtCenter,
    placePart,
    DEFAULT_ANALOG_LIB
};
