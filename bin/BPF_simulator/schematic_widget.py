# -*- coding: utf-8 -*-
"""
상단 RLC 회로도 인터랙티브 뷰 위젯 (CircuitSchematicWidget)
PySide6 QPainter 기반으로 이미지 1의 BPF 회로도를 고해상도 벡터 그래픽으로 렌더링합니다.
각 소자의 실시간 설정값 표기 및 클릭 선택 이벤트를 지원합니다.
"""

from PySide6 import QtWidgets, QtCore, QtGui
import rlc_standards as rlc


# 기본 RLC BPF 3단 필터의 표준 노드 연결 정보 (in -> n1 -> n2 -> n3 -> out 및 접지 0)
DEFAULT_COMPONENT_NODES = {
    'L1': ('in', 'n1'),
    'L2': ('n1', 'n2'),
    'L3': ('n2', 'n3'),
    'L4': ('n3', 'out'),
    'L5': ('n1', '0'),
    'C1': ('n1', '0'),
    'L6': ('n2', '0'),
    'C2': ('n2', '0'),
    'L7': ('n3', '0'),
    'C3': ('n3', '0'),
}


class CircuitSchematicWidget(QtWidgets.QWidget):
    """
    RLC 대역통과 필터(BPF) 및 커스텀 회로도를 시각적으로 표현하는 커스텀 위젯
    - 소자 선택 시 시그널 방출
    - 상단 우측에 'NGSpice' 시뮬레이션 방법 선택 체크박스 제공
    """

    # 소자가 클릭되었을 때 소자 이름(예: 'L1', 'C2')을 전달하는 시그널
    component_clicked = QtCore.Signal(str)
    # NGSpice 시뮬레이션 방법 토글 시그널
    ngspice_toggled = QtCore.Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(240)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.setMouseTracking(True)

        # 소자 값 딕셔너리 및 SPICE 서브서킷 모델 정보
        self.components = {}
        self.spice_models = {}

        # 소자별 노드 연결 정보 및 소자 타입 매핑 (시작 시 기본 BPF 3단 회로로 초기화하여 항상 회로도 표시)
        self.component_nodes = dict(DEFAULT_COMPONENT_NODES)
        self.comp_types = {
            'L1': 'L', 'L2': 'L', 'L3': 'L', 'L4': 'L',
            'L5': 'L', 'L6': 'L', 'L7': 'L',
            'C1': 'C', 'C2': 'C', 'C3': 'C'
        }


        # 현재 선택된 소자 이름
        self.selected_component = 'L1'
        # 현재 마우스 호버 중인 소자 이름
        self.hovered_component = None

        # 클릭 감지를 위한 소자별 바운딩 박스 캐시
        self.component_rects = {}

        # 상단 오버레이 레이아웃: NGSpice 시뮬레이션 선택 체크박스
        top_layout = QtWidgets.QHBoxLayout(self)
        top_layout.setContentsMargins(12, 8, 12, 0)
        top_layout.setAlignment(QtCore.Qt.AlignTop)

        title_lbl = QtWidgets.QLabel("BPF 회로도 (Bandpass Filter)")
        title_lbl.setStyleSheet("color: #444455; font-weight: bold; font-size: 11px;")
        top_layout.addWidget(title_lbl)

        top_layout.addStretch()

        # [✓] NGSpice 시뮬레이션 선택 체크박스
        self.ngspice_available = True
        self.chk_ngspice = QtWidgets.QCheckBox("NGSpice 시뮬레이션 [OFF]")
        self.chk_ngspice.setToolTip("체크 시 ngspice.exe로 시뮬레이션을 수행하고 결과를 표시합니다.\n체크 해제 시 고속 2-Port ABCD 전송행렬 해석 엔진을 사용합니다.")
        self._apply_chk_ngspice_style(False)
        self.chk_ngspice.toggled.connect(self._on_ngspice_toggled)
        top_layout.addWidget(self.chk_ngspice)

    def _apply_chk_ngspice_style(self, checked: bool):
        if not getattr(self, 'ngspice_available', True):
            self.chk_ngspice.setText("NGSpice [미설치/비활성]")
            self.chk_ngspice.setStyleSheet("""
                QCheckBox {
                    color: #888899;
                    font-weight: bold;
                    font-size: 11px;
                    background-color: #222230;
                    border: 1px dashed #44445c;
                    border-radius: 4px;
                    padding: 3px 8px;
                }
            """)
            return

        if checked:
            self.chk_ngspice.setText("NGSpice 시뮬레이션 [ON]")
            self.chk_ngspice.setStyleSheet("""
                QCheckBox {
                    color: #00ff66;
                    font-weight: bold;
                    font-size: 11px;
                    background-color: #082414;
                    border: 1.5px solid #00ff66;
                    border-radius: 4px;
                    padding: 3px 8px;
                }
            """)
        else:
            self.chk_ngspice.setText("NGSpice 시뮬레이션 [OFF]")
            self.chk_ngspice.setStyleSheet("""
                QCheckBox {
                    color: #475569;
                    font-weight: bold;
                    font-size: 11px;
                    background-color: #f1f5f9;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    padding: 3px 8px;
                }
            """)

    def _on_ngspice_toggled(self, checked: bool):
        self._apply_chk_ngspice_style(checked)
        self.ngspice_toggled.emit(checked)

    def set_ngspice_checked(self, checked: bool):
        self.chk_ngspice.blockSignals(True)
        self.chk_ngspice.setChecked(checked)
        self._apply_chk_ngspice_style(checked)
        self.chk_ngspice.blockSignals(False)

    def set_ngspice_available(self, available: bool):
        """NGSpice 실행 파일의 설치/가용 여부에 따라 체크박스를 활성화 또는 비활성화합니다."""
        self.ngspice_available = available
        self.chk_ngspice.setEnabled(available)
        if not available:
            self.chk_ngspice.blockSignals(True)
            self.chk_ngspice.setChecked(False)
            self.chk_ngspice.blockSignals(False)
            self.chk_ngspice.setText("NGSpice [미설치/비활성]")
            self.chk_ngspice.setToolTip(
                "ngspice 실행 파일(ngspice.exe)을 찾을 수 없습니다.\n"
                "상단 [설정] 버튼에서 ngspice 경로를 지정하면 활성화됩니다."
            )
            self.chk_ngspice.setStyleSheet("""
                QCheckBox {
                    color: #888899;
                    font-weight: bold;
                    font-size: 11px;
                    background-color: #222230;
                    border: 1px dashed #44445c;
                    border-radius: 4px;
                    padding: 3px 8px;
                }
            """)
        else:
            self.chk_ngspice.setToolTip(
                "체크 시 ngspice.exe로 시뮬레이션을 수행하고 결과를 표시합니다.\n"
                "체크 해제 시 고속 2-Port ABCD 전송행렬 해석 엔진을 사용합니다."
            )
            self._apply_chk_ngspice_style(self.chk_ngspice.isChecked())


    def update_components(self, comp_dict: dict, spice_models: dict = None, comp_nodes: dict = None, comp_types: dict = None):
        """소자 값, SPICE 모델, 노드 연결 및 소자 타입 정보를 갱신하고 회로도를 다시 그립니다."""
        self.components = dict(comp_dict)
        if spice_models:
            self.spice_models = dict(spice_models)
        if comp_nodes is not None:
            self.component_nodes = dict(comp_nodes)
        elif not self.component_nodes:
            self.component_nodes = dict(DEFAULT_COMPONENT_NODES)

        if comp_types is not None:
            self.comp_types.update(comp_types)
        else:
            for k in self.components:
                if k not in self.comp_types:
                    self.comp_types[k] = k[0].upper()
        self.update()


    def set_selected_component(self, name: str):
        """외부에서 특정 소자를 선택했을 때 회로도에 하이라이트 반영"""
        if self.selected_component != name:
            self.selected_component = name
            self.update()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        """마우스 이동 시 호버 상태 감지"""
        pos = event.position().toPoint()
        old_hover = self.hovered_component
        self.hovered_component = None

        for name, rect in self.component_rects.items():
            if rect.contains(pos):
                self.hovered_component = name
                break

        if old_hover != self.hovered_component:
            if self.hovered_component:
                self.setCursor(QtCore.Qt.PointingHandCursor)
            else:
                self.setCursor(QtCore.Qt.ArrowCursor)
            self.update()

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        """소자 클릭 시 선택 시그널 방출"""
        if event.button() == QtCore.Qt.LeftButton:
            pos = event.position().toPoint()
            for name, rect in self.component_rects.items():
                if rect.contains(pos):
                    self.selected_component = name
                    self.component_clicked.emit(name)
                    self.update()
                    break

    def paintEvent(self, event: QtGui.QPaintEvent):
        """회로도 벡터 그래픽 렌더링"""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing)

        w = self.width()
        h = self.height()

        # 1. 배경: 미려한 도트 그리드 스타일 (이미지 1의 배경 재현)
        painter.fillRect(0, 0, w, h, QtGui.QColor(252, 252, 253))
        dot_color = QtGui.QColor(210, 215, 225)
        painter.setPen(QtGui.QPen(dot_color, 1))
        grid_step = 20
        for x in range(10, w, grid_step):
            for y in range(10, h, grid_step):
                painter.drawPoint(x, y)

        # 2. 회로 레이아웃 좌표 계산
        margin_x = 65
        usable_w = w - (margin_x * 2)
        center_y = int(h * 0.38)     # 직렬 선로 수평 높이
        shunt_len = int(h * 0.40)    # 병렬 션트 길이
        gnd_y = center_y + shunt_len # 접지 단자 Y 좌표
        shunt_mid_y = center_y + shunt_len * 0.45

        # 바운딩 박스 초기화
        self.component_rects.clear()

        # 스타일 펜 정의
        wire_pen = QtGui.QPen(QtGui.QColor(115, 85, 225), 1.8)     # 보라색 결선 와이어 (첨부 이미지 색상)
        wire_pen.setCapStyle(QtCore.Qt.RoundCap)
        node_pen = QtGui.QPen(QtGui.QColor(220, 30, 140), 2.0)    # 분홍색 분기 노드 펜
        node_brush = QtGui.QBrush(QtGui.QColor(220, 30, 140))

        # 회로 소자 및 노드 분석
        comp_nodes = self.component_nodes
        comp_keys = list(self.components.keys())

        # 포트 단자 박스 렌더링
        x_p1 = margin_x
        x_p2 = margin_x + usable_w
        self._draw_port_box(painter, x_p1, center_y, "Port 1 (50Ω)", True)
        self._draw_port_box(painter, x_p2, center_y, "Port 2 (50Ω)", False)

        # 주 신호 경로의 중간 노드들 추출 (예: 'n1', 'n2', 'n3' 등)
        intermediate_nodes = []
        for k in comp_keys:
            n1, n2 = comp_nodes.get(k, ('in', 'out'))
            for n in (n1, n2):
                if n not in ('0', 'in', 'out') and n not in intermediate_nodes:
                    intermediate_nodes.append(n)

        # 자연스러운 노드 순서 정렬 (n1, n2, n3 등)
        intermediate_nodes.sort()

        # 신호 경로 상의 전체 노드 시퀀스: ['in', ...intermediate_nodes, 'out']
        path_nodes = ['in'] + intermediate_nodes + ['out']
        num_segments = len(path_nodes) - 1

        # 각 노드의 X 좌표 매핑
        node_x = {}
        for idx, node in enumerate(path_nodes):
            node_x[node] = x_p1 + (usable_w * idx / float(num_segments))

        # 3. 주 신호선 (수평 와이어) 그리기
        painter.setPen(wire_pen)
        painter.drawLine(QtCore.QPointF(x_p1, center_y), QtCore.QPointF(x_p2, center_y))

        # 4. 직렬 구간별 소자 그리기
        drawn_components = set()
        for i in range(num_segments):
            u, v = path_nodes[i], path_nodes[i+1]
            # u와 v를 잇는 소자들 탐색
            segs = [k for k in comp_keys if set(comp_nodes.get(k, ())) == {u, v}]
            cx = (node_x[u] + node_x[v]) / 2.0

            if len(segs) == 1:
                k = segs[0]
                drawn_components.add(k)
                ctype = self.comp_types.get(k, k[0].upper())
                if ctype == 'R':
                    self._draw_horizontal_resistor(painter, k, cx, center_y)
                elif ctype == 'L':
                    self._draw_series_inductor(painter, k, cx, center_y)
                elif ctype == 'C':
                    self._draw_series_capacitor(painter, k, cx, center_y)
            elif len(segs) >= 2:
                # 2개 이상일 때는 위/아래 브랜치로 분기 (예: L1||C1 병렬 공진, 또는 L4||L8)
                k_top = segs[0]
                k_bot = segs[1]
                drawn_components.add(k_top)
                drawn_components.add(k_bot)
                split_x1 = node_x[u] + 14.0
                split_x2 = node_x[v] - 14.0
                offset_y = 28.0

                # 분기 와이어 (보라색)
                painter.setPen(wire_pen)
                painter.fillRect(QtCore.QRectF(split_x1, center_y - 2, split_x2 - split_x1, 4), QtGui.QColor(252, 252, 253))
                painter.drawLine(QtCore.QPointF(split_x1, center_y), QtCore.QPointF(split_x1, center_y - offset_y))
                painter.drawLine(QtCore.QPointF(split_x1, center_y - offset_y), QtCore.QPointF(split_x2, center_y - offset_y))
                painter.drawLine(QtCore.QPointF(split_x2, center_y - offset_y), QtCore.QPointF(split_x2, center_y))

                painter.drawLine(QtCore.QPointF(split_x1, center_y), QtCore.QPointF(split_x1, center_y + offset_y))
                painter.drawLine(QtCore.QPointF(split_x1, center_y + offset_y), QtCore.QPointF(split_x2, center_y + offset_y))
                painter.drawLine(QtCore.QPointF(split_x2, center_y + offset_y), QtCore.QPointF(split_x2, center_y))

                painter.setPen(node_pen)
                painter.setBrush(node_brush)
                painter.drawEllipse(QtCore.QPointF(split_x1, center_y), 3.0, 3.0)
                painter.drawEllipse(QtCore.QPointF(split_x2, center_y), 3.0, 3.0)

                # 상단 소자
                ct_top = self.comp_types.get(k_top, k_top[0].upper())
                if ct_top == 'R':
                    self._draw_horizontal_resistor(painter, k_top, cx, center_y - offset_y)
                elif ct_top == 'L':
                    self._draw_series_inductor(painter, k_top, cx, center_y - offset_y)
                elif ct_top == 'C':
                    self._draw_series_capacitor(painter, k_top, cx, center_y - offset_y)

                # 하단 소자
                ct_bot = self.comp_types.get(k_bot, k_bot[0].upper())
                if ct_bot == 'R':
                    self._draw_horizontal_resistor(painter, k_bot, cx, center_y + offset_y)
                elif ct_bot == 'L':
                    self._draw_series_inductor(painter, k_bot, cx, center_y + offset_y)
                elif ct_bot == 'C':
                    self._draw_series_capacitor(painter, k_bot, cx, center_y + offset_y)

        # 5. in ~ out 직접 바이패스 소자가 남아있는 경우
        bypass_segs = [k for k in comp_keys if set(comp_nodes.get(k, ())) == {'in', 'out'} and k not in drawn_components]
        for k in bypass_segs:
            drawn_components.add(k)
            bypass_y = center_y - 42.0
            painter.setPen(wire_pen)
            painter.drawLine(QtCore.QPointF(x_p1 + 10, center_y), QtCore.QPointF(x_p1 + 10, bypass_y))
            painter.drawLine(QtCore.QPointF(x_p1 + 10, bypass_y), QtCore.QPointF(x_p2 - 10, bypass_y))
            painter.drawLine(QtCore.QPointF(x_p2 - 10, bypass_y), QtCore.QPointF(x_p2 - 10, center_y))

            painter.setPen(node_pen)
            painter.setBrush(node_brush)
            painter.drawEllipse(QtCore.QPointF(x_p1 + 10, center_y), 3.0, 3.0)
            painter.drawEllipse(QtCore.QPointF(x_p2 - 10, center_y), 3.0, 3.0)

            mid_x = (x_p1 + x_p2) / 2.0
            ctype = self.comp_types.get(k, k[0].upper())
            if ctype == 'R':
                self._draw_horizontal_resistor(painter, k, mid_x, bypass_y)
            elif ctype == 'L':
                self._draw_series_inductor(painter, k, mid_x, bypass_y)
            elif ctype == 'C':
                self._draw_series_capacitor(painter, k, mid_x, bypass_y)

        # 6. 각 노드별 병렬 션트(Shunt to GND) 소자 그리기
        for node in path_nodes:
            shunts = [k for k in comp_keys if set(comp_nodes.get(k, ())) == {node, '0'}]
            if not shunts:
                continue

            # 기본 X 좌표 결정
            if node == 'in':
                nx = x_p1 + min(48.0, usable_w / float(max(1, num_segments)) * 0.35)
            elif node == 'out':
                nx = x_p2 - min(48.0, usable_w / float(max(1, num_segments)) * 0.35)
            else:
                nx = node_x[node]

            if len(shunts) == 1:
                # 단일 션트 소자
                k = shunts[0]
                drawn_components.add(k)

                painter.setPen(wire_pen)
                painter.drawLine(QtCore.QPointF(nx, center_y), QtCore.QPointF(nx, gnd_y))

                painter.setPen(node_pen)
                painter.setBrush(node_brush)
                painter.drawEllipse(QtCore.QPointF(nx, center_y), 3.5, 3.5)
                painter.drawEllipse(QtCore.QPointF(nx, gnd_y), 3.0, 3.0)

                ctype = self.comp_types.get(k, k[0].upper())
                if ctype == 'R':
                    self._draw_vertical_resistor(painter, k, nx, shunt_mid_y)
                elif ctype == 'L':
                    self._draw_shunt_inductor(painter, k, nx, shunt_mid_y)
                elif ctype == 'C':
                    self._draw_shunt_capacitor(painter, k, nx, shunt_mid_y)

                self._draw_ground_symbol(painter, nx, gnd_y)

            elif len(shunts) >= 2:
                # 병렬 탱크 (2개 이상의 션트 소자 분기)
                k1, k2 = shunts[0], shunts[1]
                drawn_components.add(k1)
                drawn_components.add(k2)
                b_dx = min(36.0, usable_w / float(max(1, num_segments)) * 0.22)
                x1 = nx - b_dx
                x2 = nx + b_dx

                painter.setPen(wire_pen)
                painter.drawLine(QtCore.QPointF(x1, center_y), QtCore.QPointF(x1, gnd_y))
                painter.drawLine(QtCore.QPointF(x2, center_y), QtCore.QPointF(x2, gnd_y))
                painter.drawLine(QtCore.QPointF(x1, gnd_y), QtCore.QPointF(x2, gnd_y))

                painter.setPen(node_pen)
                painter.setBrush(node_brush)
                for gx in [x1, x2]:
                    painter.drawEllipse(QtCore.QPointF(gx, center_y), 3.5, 3.5)
                    painter.drawEllipse(QtCore.QPointF(gx, gnd_y), 3.0, 3.0)

                ct1 = self.comp_types.get(k1, k1[0].upper())
                if ct1 == 'R':
                    self._draw_vertical_resistor(painter, k1, x1, shunt_mid_y)
                elif ct1 == 'L':
                    self._draw_shunt_inductor(painter, k1, x1, shunt_mid_y)
                elif ct1 == 'C':
                    self._draw_shunt_capacitor(painter, k1, x1, shunt_mid_y)

                ct2 = self.comp_types.get(k2, k2[0].upper())
                if ct2 == 'R':
                    self._draw_vertical_resistor(painter, k2, x2, shunt_mid_y)
                elif ct2 == 'L':
                    self._draw_shunt_inductor(painter, k2, x2, shunt_mid_y)
                elif ct2 == 'C':
                    self._draw_shunt_capacitor(painter, k2, x2, shunt_mid_y)

                self._draw_ground_symbol(painter, nx, gnd_y)

    def _draw_port_box(self, painter: QtGui.QPainter, x: float, y: float, label: str, is_left: bool):
        """포트 단자 사각형 및 라벨 렌더링"""
        box_w, box_h = 10, 10
        rect = QtCore.QRectF(x - (box_w if is_left else 0), y - box_h/2, box_w, box_h)
        painter.setPen(QtGui.QPen(QtGui.QColor(100, 100, 100), 1.5))
        painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))
        painter.drawRect(rect)

        # 텍스트 라벨
        painter.setPen(QtGui.QColor(80, 80, 90))
        painter.setFont(QtGui.QFont("Malgun Gothic", 8, QtGui.QFont.Bold))
        text_rect = QtCore.QRectF(x - 40 if is_left else x + 12, y - 22, 70, 16)
        painter.drawText(text_rect, QtCore.Qt.AlignLeft if not is_left else QtCore.Qt.AlignRight, label)

    def _draw_ground_symbol(self, painter: QtGui.QPainter, x: float, y: float, label: str = "GND"):
        """표준 전자회로 3단 접지(Ground / GND) 기호 렌더링"""
        gnd_pen = QtGui.QPen(QtGui.QColor(70, 70, 90), 1.8)
        gnd_pen.setCapStyle(QtCore.Qt.RoundCap)
        painter.setPen(gnd_pen)

        # 하향 수직 인출선
        painter.drawLine(QtCore.QPointF(x, y), QtCore.QPointF(x, y + 8))

        # 3단 수평선 (점점 좁아지는 표준 접지 심볼)
        w1, w2, w3 = 18.0, 11.0, 5.0
        y1 = y + 8
        y2 = y1 + 4
        y3 = y2 + 4
        painter.drawLine(QtCore.QPointF(x - w1 / 2.0, y1), QtCore.QPointF(x + w1 / 2.0, y1))
        painter.drawLine(QtCore.QPointF(x - w2 / 2.0, y2), QtCore.QPointF(x + w2 / 2.0, y2))
        painter.drawLine(QtCore.QPointF(x - w3 / 2.0, y3), QtCore.QPointF(x + w3 / 2.0, y3))

        # GND 라벨 텍스트
        painter.setPen(QtGui.QColor(90, 90, 110))
        painter.setFont(QtGui.QFont("Malgun Gothic", 7.5, QtGui.QFont.Bold))
        painter.drawText(QtCore.QRectF(x - 20, y3 + 2, 40, 14), QtCore.Qt.AlignCenter, label)


    def _get_val_str(self, name: str) -> str:
        """소자의 공학 단위 문자열 또는 SPICE 서브서킷 모델명 반환"""
        sm = self.spice_models.get(name, {})
        if sm.get('mode') == 'subckt' and sm.get('model_name'):
            return f"[{sm['model_name'][:8]}]"
        val = self.components.get(name, 0.0)
        ctype = self.comp_types.get(name, name[0].upper() if name else 'L')
        return rlc.format_engineering(val, ctype)


    def _draw_highlight(self, painter: QtGui.QPainter, rect: QtCore.QRectF, name: str):
        """선택 또는 호버 하이라이트 박스 그리기"""
        if self.selected_component == name:
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 140, 0), 2.0, QtCore.Qt.DashLine))
            painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 165, 0, 35)))
            painter.drawRoundedRect(rect, 4, 4)
        elif self.hovered_component == name:
            painter.setPen(QtGui.QPen(QtGui.QColor(70, 130, 240, 180), 1.5, QtCore.Qt.DotLine))
            painter.setBrush(QtGui.QBrush(QtGui.QColor(100, 149, 237, 25)))
            painter.drawRoundedRect(rect, 4, 4)

    def _draw_series_inductor(self, painter: QtGui.QPainter, name: str, cx: float, cy: float):
        """수평 직렬 인덕터 그리기 (코일 4턴 + 도트 + 라벨)"""
        w, h = 54, 24
        rect = QtCore.QRectF(cx - w/2, cy - h/2 - 14, w, h + 34)
        self.component_rects[name] = rect.toRect()

        self._draw_highlight(painter, rect, name)

        # 소자 배경 지우개 (와이어 덮기)
        painter.fillRect(QtCore.QRectF(cx - w/2 + 2, cy - 10, w - 4, 20), QtGui.QColor(252, 252, 253))

        # 인덕터 코일 (부드러운 호 4개)
        painter.setPen(QtGui.QPen(QtGui.QColor(40, 70, 200), 2.0))
        r = (w - 6) / 8.0  # 반경
        start_x = cx - (w - 6) / 2.0
        for i in range(4):
            arc_rect = QtCore.QRectF(start_x + i * 2 * r, cy - r, 2 * r, 2 * r)
            painter.drawArc(arc_rect, 0 * 16, 180 * 16)

        # 극성 도트 (Dot convention: 별표 도트 심볼)
        dot_x = cx - w/2 + 7
        dot_y = cy - 14
        painter.setPen(QtGui.QPen(QtGui.QColor(30, 60, 180), 1.5))
        painter.setBrush(QtGui.QBrush(QtGui.QColor(30, 60, 180)))
        painter.drawEllipse(QtCore.QPointF(dot_x, dot_y), 2.5, 2.5)

        # 라벨 및 값 표기 (파란색)
        painter.setFont(QtGui.QFont("Malgun Gothic", 9, QtGui.QFont.Bold))
        painter.drawText(QtCore.QRectF(cx - 25, cy - 30, 50, 16), QtCore.Qt.AlignCenter, name)

        painter.setFont(QtGui.QFont("Malgun Gothic", 8, QtGui.QFont.Normal))
        painter.drawText(QtCore.QRectF(cx - 35, cy + 8, 70, 16), QtCore.Qt.AlignCenter, self._get_val_str(name))

    def _draw_shunt_inductor(self, painter: QtGui.QPainter, name: str, cx: float, cy: float):
        """수직 병렬 인덕터 그리기 (코일 4턴 + 도트 + 라벨)"""
        w, h = 26, 44
        rect = QtCore.QRectF(cx - 36, cy - h/2 - 4, 56, h + 22)
        self.component_rects[name] = rect.toRect()

        self._draw_highlight(painter, rect, name)

        # 와이어 지우개
        painter.fillRect(QtCore.QRectF(cx - 10, cy - h/2 + 2, 20, h - 4), QtGui.QColor(252, 252, 253))

        # 코일 (수직 방향 호 4개)
        painter.setPen(QtGui.QPen(QtGui.QColor(40, 70, 200), 2.0))
        r = (h - 4) / 8.0
        start_y = cy - (h - 4) / 2.0
        for i in range(4):
            arc_rect = QtCore.QRectF(cx - r, start_y + i * 2 * r, 2 * r, 2 * r)
            painter.drawArc(arc_rect, -90 * 16, 180 * 16)

        # 도트 (우측 상단)
        painter.setPen(QtGui.QPen(QtGui.QColor(30, 60, 180), 1.5))
        painter.setBrush(QtGui.QBrush(QtGui.QColor(30, 60, 180)))
        painter.drawEllipse(QtCore.QPointF(cx + 10, cy - h/2 + 5), 2.5, 2.5)

        # 라벨 및 값 표기 (좌측)
        painter.setFont(QtGui.QFont("Malgun Gothic", 9, QtGui.QFont.Bold))
        painter.drawText(QtCore.QRectF(cx - 50, cy - 14, 44, 16), QtCore.Qt.AlignRight, name)

        painter.setFont(QtGui.QFont("Malgun Gothic", 8, QtGui.QFont.Normal))
        painter.drawText(QtCore.QRectF(cx - 60, cy + 2, 54, 16), QtCore.Qt.AlignRight, self._get_val_str(name))

    def _draw_shunt_capacitor(self, painter: QtGui.QPainter, name: str, cx: float, cy: float):
        """수직 병렬 커패시터 그리기 (평행판 2개 + 라벨)"""
        w, h = 24, 28
        rect = QtCore.QRectF(cx - 10, cy - h/2 - 4, 55, h + 22)
        self.component_rects[name] = rect.toRect()

        self._draw_highlight(painter, rect, name)

        # 와이어 지우개
        painter.fillRect(QtCore.QRectF(cx - 12, cy - 8, 24, 16), QtGui.QColor(252, 252, 253))

        # 평행판 2개
        plate_w = 16
        plate_gap = 6
        painter.setPen(QtGui.QPen(QtGui.QColor(40, 70, 200), 2.2))
        painter.drawLine(QtCore.QPointF(cx - plate_w/2, cy - plate_gap/2), QtCore.QPointF(cx + plate_w/2, cy - plate_gap/2))
        painter.drawLine(QtCore.QPointF(cx - plate_w/2, cy + plate_gap/2), QtCore.QPointF(cx + plate_w/2, cy + plate_gap/2))

        # 상하 연결 리드선
        wire_pen = QtGui.QPen(QtGui.QColor(200, 30, 30), 1.8)
        painter.setPen(wire_pen)
        painter.drawLine(QtCore.QPointF(cx, cy - 14), QtCore.QPointF(cx, cy - plate_gap/2))
        painter.drawLine(QtCore.QPointF(cx, cy + plate_gap/2), QtCore.QPointF(cx, cy + 14))

        # 라벨 및 값 표기 (우측)
        painter.setPen(QtGui.QColor(40, 70, 200))
        painter.setFont(QtGui.QFont("Malgun Gothic", 9, QtGui.QFont.Bold))
        painter.drawText(QtCore.QRectF(cx + 12, cy - 14, 40, 16), QtCore.Qt.AlignLeft, name)

        painter.setFont(QtGui.QFont("Malgun Gothic", 8, QtGui.QFont.Normal))
        painter.drawText(QtCore.QRectF(cx + 12, cy + 2, 50, 16), QtCore.Qt.AlignLeft, self._get_val_str(name))

    def _draw_horizontal_resistor(self, painter: QtGui.QPainter, name: str, cx: float, cy: float):
        """수평 직렬 저항 그리기 (미국식 IEEE 표준 지그재그 심볼 + 상하 라벨 표기)"""
        w, h = 56, 24
        rect = QtCore.QRectF(cx - w/2, cy - h/2 - 14, w, h + 34)
        self.component_rects[name] = rect.toRect()

        self._draw_highlight(painter, rect, name)

        # 소자 배경 지우개 (와이어 덮기)
        painter.fillRect(QtCore.QRectF(cx - w/2 + 2, cy - 10, w - 4, 20), QtGui.QColor(252, 252, 253))

        # 저항 지그재그 펜 (첨부 이미지의 오렌지브라운 색상: #C87A28)
        res_color = QtGui.QColor(200, 122, 40)
        res_pen = QtGui.QPen(res_color, 1.9, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
        painter.setPen(res_pen)

        # 좌우 리드선 길이
        lead_len = 9.0
        x_left = cx - w/2 + 4
        x_right = cx + w/2 - 4
        x_start = x_left + lead_len
        x_end = x_right - lead_len

        # 좌측 리드선
        painter.drawLine(QtCore.QPointF(x_left, cy), QtCore.QPointF(x_start, cy))

        # 지그재그 꺾임점 (총 6번 꺾임: 위, 아래, 위, 아래, 위, 아래, 중앙)
        body_len = x_end - x_start
        step = body_len / 7.0
        amp = 6.2  # 지그재그 상하 진폭

        pts = [QtCore.QPointF(x_start, cy)]
        for i in range(1, 7):
            sign = -1.0 if (i % 2 == 1) else 1.0
            pts.append(QtCore.QPointF(x_start + i * step, cy + sign * amp))
        pts.append(QtCore.QPointF(x_end, cy))
        painter.drawPolyline(pts)

        # 우측 리드선
        painter.drawLine(QtCore.QPointF(x_end, cy), QtCore.QPointF(x_right, cy))

        # 라벨 및 값 표기 (상단에 소자명 R1, 하단에 값 1k/50 등)
        painter.setPen(QtGui.QColor(20, 20, 35))
        painter.setFont(QtGui.QFont("Malgun Gothic", 9.5, QtGui.QFont.Bold))
        painter.drawText(QtCore.QRectF(cx - 35, cy - 30, 70, 16), QtCore.Qt.AlignCenter, name)

        painter.setFont(QtGui.QFont("Malgun Gothic", 8.5, QtGui.QFont.Bold))
        painter.drawText(QtCore.QRectF(cx - 35, cy + 8, 70, 16), QtCore.Qt.AlignCenter, self._get_val_str(name))

    def _draw_vertical_resistor(self, painter: QtGui.QPainter, name: str, cx: float, cy: float):
        """수직 병렬/션트 저항 그리기 (첨부 이미지 규격: 보라색 와이어 + 황토색 지그재그 + 우측 라벨)"""
        w, h = 28, 48
        rect = QtCore.QRectF(cx - 16, cy - h/2 - 4, 70, h + 10)
        self.component_rects[name] = rect.toRect()

        self._draw_highlight(painter, rect, name)

        # 와이어 지우개
        painter.fillRect(QtCore.QRectF(cx - 8, cy - h/2 + 2, 16, h - 4), QtGui.QColor(252, 252, 253))

        # 상하 보라색 와이어 리드선 (첨부 이미지의 보라색 와이어 재현)
        wire_pen = QtGui.QPen(QtGui.QColor(115, 85, 225), 1.8, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)
        painter.setPen(wire_pen)
        painter.drawLine(QtCore.QPointF(cx, cy - h/2), QtCore.QPointF(cx, cy - h/2 + 8))
        painter.drawLine(QtCore.QPointF(cx, cy + h/2 - 8), QtCore.QPointF(cx, cy + h/2))

        # 저항 황토색 지그재그 심볼 (첨부 이미지의 오렌지브라운: #C87A28)
        res_color = QtGui.QColor(200, 122, 40)
        res_pen = QtGui.QPen(res_color, 1.9, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
        painter.setPen(res_pen)

        y_top = cy - h/2 + 8
        y_bottom = cy + h/2 - 8
        res_lead = 4.0
        y_start = y_top + res_lead
        y_end = y_bottom - res_lead

        # 저항 상/하 자체 리드선
        painter.drawLine(QtCore.QPointF(cx, y_top), QtCore.QPointF(cx, y_start))
        painter.drawLine(QtCore.QPointF(cx, y_end), QtCore.QPointF(cx, y_bottom))

        # 지그재그 꺾임점 (총 6번 꺾임: 우측, 좌측, 우측, 좌측, 우측, 좌측, 중앙)
        body_len = y_end - y_start
        step = body_len / 7.0
        amp = 5.8  # 좌우 진폭

        pts = [QtCore.QPointF(cx, y_start)]
        for i in range(1, 7):
            sign = 1.0 if (i % 2 == 1) else -1.0  # 첨부 이미지: 첫 번째 꺾임이 우측(↘)
            pts.append(QtCore.QPointF(cx + sign * amp, y_start + i * step))
        pts.append(QtCore.QPointF(cx, y_end))
        painter.drawPolyline(pts)

        # 라벨 및 값 표기 (★첨부 이미지와 정확히 동일: 우측에 소자명 R1, 그 아래 줄에 값 50/1k)
        painter.setPen(QtGui.QColor(20, 20, 35))
        painter.setFont(QtGui.QFont("Malgun Gothic", 10, QtGui.QFont.Bold))
        painter.drawText(QtCore.QRectF(cx + 12, cy - 16, 50, 18), QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, name)

        painter.setFont(QtGui.QFont("Malgun Gothic", 9.5, QtGui.QFont.Normal))
        painter.drawText(QtCore.QRectF(cx + 12, cy + 2, 50, 18), QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, self._get_val_str(name))

    def _draw_series_capacitor(self, painter: QtGui.QPainter, name: str, cx: float, cy: float):
        """수평 직렬 커패시터 그리기 (평행판 2개 + 상하 라벨 표기)"""
        w, h = 54, 28
        rect = QtCore.QRectF(cx - w/2, cy - h/2 - 14, w, h + 34)
        self.component_rects[name] = rect.toRect()

        self._draw_highlight(painter, rect, name)

        # 소자 배경 지우개
        painter.fillRect(QtCore.QRectF(cx - 16, cy - 14, 32, 28), QtGui.QColor(252, 252, 253))

        # 평행판 2개 (수직선)
        plate_h = 20.0
        plate_gap = 6.0
        cap_pen = QtGui.QPen(QtGui.QColor(40, 70, 200), 2.2)
        painter.setPen(cap_pen)
        painter.drawLine(QtCore.QPointF(cx - plate_gap/2, cy - plate_h/2), QtCore.QPointF(cx - plate_gap/2, cy + plate_h/2))
        painter.drawLine(QtCore.QPointF(cx + plate_gap/2, cy - plate_h/2), QtCore.QPointF(cx + plate_gap/2, cy + plate_h/2))

        # 좌우 연결 리드선
        wire_pen = QtGui.QPen(QtGui.QColor(115, 85, 225), 1.8)
        painter.setPen(wire_pen)
        painter.drawLine(QtCore.QPointF(cx - w/2 + 4, cy), QtCore.QPointF(cx - plate_gap/2, cy))
        painter.drawLine(QtCore.QPointF(cx + plate_gap/2, cy), QtCore.QPointF(cx + w/2 - 4, cy))

        # 라벨 및 값 표기 (파란색)
        painter.setPen(QtGui.QColor(30, 60, 180))
        painter.setFont(QtGui.QFont("Malgun Gothic", 9.5, QtGui.QFont.Bold))
        painter.drawText(QtCore.QRectF(cx - 35, cy - 30, 70, 16), QtCore.Qt.AlignCenter, name)

        painter.setFont(QtGui.QFont("Malgun Gothic", 8.5, QtGui.QFont.Bold))
        painter.drawText(QtCore.QRectF(cx - 35, cy + 8, 70, 16), QtCore.Qt.AlignCenter, self._get_val_str(name))


