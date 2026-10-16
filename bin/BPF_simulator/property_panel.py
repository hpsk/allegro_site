# -*- coding: utf-8 -*-
"""
우측 부품 개별 속성 편집 패널 (ComponentPropertyPanel)
- 부품별 개별 설정 지원 (리스트 목록 UI 제거)
- 회로도 클릭 또는 패널 내 부품 선택기로 활성 부품 전환
- 커패시터와 인덕터의 개별 ESR(등가 직렬 저항) 설정 포함
- R 또는 ESR이 0이면 1p (1e-12 Ω)으로 시뮬레이션 처리
- SPICE 서브서킷(.SUBCKT) 개별 지정 지원
"""

from PySide6 import QtWidgets, QtCore, QtGui
import rlc_standards as rlc
import re

# 회로 소자 순서 및 기본 명칭 정의
ALL_COMPONENTS = ['L1', 'L2', 'L3', 'L4', 'L5', 'C1', 'L6', 'C2', 'L7', 'C3']

COMP_DESCRIPTIONS = {
    'L1': '직렬 인덕터 1',
    'L2': '직렬 인덕터 2',
    'L3': '직렬 인덕터 3',
    'L4': '직렬 인덕터 4',
    'L5': '병렬 1 인덕터',
    'C1': '병렬 1 커패시터',
    'L6': '병렬 2 인덕터',
    'C2': '병렬 2 커패시터',
    'L7': '병렬 3 인덕터',
    'C3': '병렬 3 커패시터',
}

# RLC 단위 변환 배수 및 지원 단위 목록
UNIT_MULTIPLIERS = {
    # 인덕턴스 단위
    'pH': 1e-12, 'nH': 1e-9, 'uH': 1e-6, 'mH': 1e-3, 'H': 1.0,
    # 커패시턴스 단위
    'fF': 1e-15, 'pF': 1e-12, 'nF': 1e-9, 'uF': 1e-6, 'mF': 1e-3,
    # 저항 단위
    'mΩ': 1e-3, 'Ω': 1.0, 'kΩ': 1e3, 'MΩ': 1e6
}

COMP_UNITS = {
    'L': ['pH', 'nH', 'uH', 'mH', 'H'],
    'C': ['fF', 'pF', 'nF', 'uF', 'mF'],
    'R': ['mΩ', 'Ω', 'kΩ', 'MΩ']
}


def split_val_and_unit(val: float, comp_type: str) -> tuple[float, str]:
    """공칭값과 소자 타입으로부터 가장 적절한 (숫자, 단위)를 분해하여 반환합니다."""
    units = COMP_UNITS.get(comp_type, ['nH' if comp_type == 'L' else ('pF' if comp_type == 'C' else 'Ω')])
    if val <= 0:
        return 0.0, units[1] if len(units) > 1 else units[0]

    for u in units:
        mult = UNIT_MULTIPLIERS[u]
        scaled = val / mult
        if 0.1 <= scaled < 999.999:
            return round(scaled, 4), u

    default_u = 'nH' if comp_type == 'L' else ('pF' if comp_type == 'C' else 'Ω')
    return round(val / UNIT_MULTIPLIERS[default_u], 4), default_u


class ActiveComponentCard(QtWidgets.QFrame):
    """
    선택된 부품 개별 속성 상세 편집 카드
    - 공칭값 및 오차율 선택
    - 부품 개별 ESR (등가 직렬 저항) 입력 (0 입력 시 1pΩ 치환 안내)
    - SPICE 서브서킷 (.SUBCKT) 모델 설정
    """

    value_changed = QtCore.Signal(str, float)
    esr_changed = QtCore.Signal(str, float)
    tolerance_changed = QtCore.Signal(str, str)
    spice_model_changed = QtCore.Signal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_name = 'L1'
        self.current_type = 'L'
        self.current_val = 22e-9
        self.current_esr = 0.35
        self.current_tol = '10% (E12)'
        self.available_values = []
        self.current_subckt_text = ''
        self.current_subckt_name = ''

        self._init_ui()

    def _init_ui(self):
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setStyleSheet("""
            ActiveComponentCard {
                background-color: #202030;
                border: 2px solid #00e5ff;
                border-radius: 6px;
                padding: 6px;
            }
            QLabel#badge {
                background-color: #00e5ff;
                color: #000000;
                font-weight: bold;
                font-size: 13px;
                border-radius: 4px;
                padding: 2px 8px;
            }
            QLabel#desc {
                color: #e0e0f0;
                font-size: 12px;
                font-weight: bold;
            }
            QLabel#big_val {
                color: #ffff00;
                font-size: 17px;
                font-weight: bold;
                font-family: monospace;
            }
            QTabWidget::pane {
                border: 1px solid #3c3c56;
                background-color: #1a1a26;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #242436;
                color: #aaaaaa;
                padding: 5px 12px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background-color: #383854;
                color: #00ffff;
                border-bottom: 2px solid #00ffff;
            }
            QComboBox, QLineEdit, QDoubleSpinBox {
                background-color: #161622;
                color: #ffffff;
                border: 1px solid #444460;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 12.5px;
                font-weight: bold;
                min-height: 28px;
            }
            QComboBox QAbstractItemView {
                background-color: #181826;
                color: #ffffff;
                selection-background-color: #2b3a55;
                selection-color: #00ffff;
                border: 1px solid #444460;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                min-height: 28px;
                padding: 4px 10px;
                color: #ffffff;
                background-color: #181826;
                font-size: 12.5px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #28283c;
                color: #00ffff;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #2b3a55;
                color: #00ffff;
                font-weight: bold;
            }
            QComboBox#combo_val {
                color: #ffff00;
                font-size: 13.5px;
                font-weight: bold;
                min-height: 30px;
                padding: 2px 8px;
            }
            QPushButton {
                background-color: #34344e;
                color: #00ffff;
                border: 1px solid #4a4a6c;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
                padding: 4px 10px;
                min-height: 28px;
            }
            QPushButton:hover {
                background-color: #46466a;
                color: #ffffff;
            }
            QPlainTextEdit {
                background-color: #14141e;
                color: #98c379;
                font-family: Consolas, monospace;
                font-size: 11px;
                border: 1px solid #36364e;
                border-radius: 3px;
            }
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 1. 헤더: 소자 이름 배지, 설명, 현재값
        header_layout = QtWidgets.QHBoxLayout()
        self.lbl_badge = QtWidgets.QLabel("L1")
        self.lbl_badge.setObjectName("badge")
        header_layout.addWidget(self.lbl_badge)

        self.lbl_desc = QtWidgets.QLabel("(직렬 인덕터 1)")
        self.lbl_desc.setObjectName("desc")
        header_layout.addWidget(self.lbl_desc)

        header_layout.addStretch()

        self.lbl_big_val = QtWidgets.QLabel("18 nH")
        self.lbl_big_val.setObjectName("big_val")
        header_layout.addWidget(self.lbl_big_val)
        layout.addLayout(header_layout)

        # 2. 탭 위젯 (표준 RLC/ESR 설정 vs SPICE 모델 설정)
        self.tabs = QtWidgets.QTabWidget()

        # --- 탭 1: 표준 RLC 판매값 및 개별 ESR ---
        tab_rlc = QtWidgets.QWidget()
        rlc_layout = QtWidgets.QVBoxLayout(tab_rlc)
        rlc_layout.setContentsMargins(8, 8, 8, 8)
        rlc_layout.setSpacing(8)

        # 행 1: 오차율 선택 및 [수치] [단위] 분리 직접 입력 / 스냅
        row_tol = QtWidgets.QHBoxLayout()
        lbl_tol = QtWidgets.QLabel("오차율:")
        lbl_tol.setStyleSheet("font-weight: bold; color: #cccccc; font-size: 11px;")
        row_tol.addWidget(lbl_tol)

        self.combo_tol = QtWidgets.QComboBox()
        self.combo_tol.setMinimumHeight(28)
        self.combo_tol.currentTextChanged.connect(self._on_tol_changed)
        row_tol.addWidget(self.combo_tol)

        row_tol.addSpacing(6)
        lbl_in = QtWidgets.QLabel("수치 입력:")
        lbl_in.setStyleSheet("font-weight: bold; color: #00ffff; font-size: 11px;")
        row_tol.addWidget(lbl_in)

        # 1) 숫자 입력 스핀박스 (예: 22, 6.8, 100)
        self.spin_direct_val = QtWidgets.QDoubleSpinBox()
        self.spin_direct_val.setRange(0.0001, 999999.0)
        self.spin_direct_val.setDecimals(3)
        self.spin_direct_val.setSingleStep(1.0)
        self.spin_direct_val.setMinimumWidth(80)
        self.spin_direct_val.setMinimumHeight(28)
        self.spin_direct_val.setStyleSheet("font-size: 13px; font-weight: bold; color: #ffffff;")
        self.spin_direct_val.valueChanged.connect(self._on_direct_val_changed)
        row_tol.addWidget(self.spin_direct_val)

        # 2) 단위 선택 콤보박스 (예: nH, pF 등)
        self.combo_unit = QtWidgets.QComboBox()
        self.combo_unit.setMinimumWidth(68)
        self.combo_unit.setMinimumHeight(28)
        self.combo_unit.setStyleSheet("font-size: 13px; font-weight: bold; color: #00ffff;")
        self.combo_unit.currentTextChanged.connect(self._on_unit_changed)
        row_tol.addWidget(self.combo_unit)

        # 3) 스냅 버튼
        self.btn_snap = QtWidgets.QPushButton("스냅")
        self.btn_snap.setMinimumHeight(28)
        self.btn_snap.setToolTip("입력한 값을 가장 가까운 표준 E-시리즈 판매 공칭값으로 스냅합니다.")
        self.btn_snap.clicked.connect(self._on_snap_clicked)
        row_tol.addWidget(self.btn_snap)
        rlc_layout.addLayout(row_tol)

        # 행 2: 판매 공칭값 단계별 조절 ([◀ 이전값] [콤보박스] [다음값 ▶])
        row_step = QtWidgets.QHBoxLayout()
        self.btn_prev = QtWidgets.QPushButton("◀ 이전값")
        self.btn_prev.setMinimumHeight(30)
        self.btn_prev.clicked.connect(self._step_prev)
        row_step.addWidget(self.btn_prev)

        self.combo_val = QtWidgets.QComboBox()
        self.combo_val.setObjectName("combo_val")
        self.combo_val.setMinimumHeight(30)
        self.combo_val.setMaxVisibleItems(18)  # 드롭다운 리스트 항목 크기 대폭 확대
        self.combo_val.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.combo_val.currentIndexChanged.connect(self._on_combo_val_changed)
        row_step.addWidget(self.combo_val)

        self.btn_next = QtWidgets.QPushButton("다음값 ▶")
        self.btn_next.setMinimumHeight(30)
        self.btn_next.clicked.connect(self._step_next)
        row_step.addWidget(self.btn_next)
        rlc_layout.addLayout(row_step)

        # 행 3: 부품 개별 ESR 설정 및 우측 RLC 적용 버튼
        row_esr = QtWidgets.QHBoxLayout()
        lbl_esr_title = QtWidgets.QLabel("부품 개별 ESR (등가 직렬 저항):")
        lbl_esr_title.setStyleSheet("color: #ffaa00; font-weight: bold; font-size: 11.5px;")
        row_esr.addWidget(lbl_esr_title)

        self.spin_esr = QtWidgets.QDoubleSpinBox()
        self.spin_esr.setRange(0.0, 50.0)
        self.spin_esr.setSingleStep(0.05)
        self.spin_esr.setValue(self.current_esr)
        self.spin_esr.setSuffix(" Ω")
        self.spin_esr.valueChanged.connect(self._on_esr_changed)
        row_esr.addWidget(self.spin_esr)

        row_esr.addSpacing(6)

        # 저항값 입력하는 칸 오른쪽에 작고 깔끔하게 배치되는 RLC 적용 버튼
        self.btn_apply_rlc = QtWidgets.QPushButton("⚡ RLC 적용")
        self.btn_apply_rlc.setStyleSheet("""
            QPushButton {
                background-color: #1e7e34;
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                padding: 3px 10px;
                border: 1px solid #28a745;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #218838;
                border-color: #34d058;
            }
            QPushButton:pressed {
                background-color: #19692c;
            }
        """)
        self.btn_apply_rlc.setToolTip("현재 RLC 공칭값 및 개별 ESR을 회로에 즉시 적용하고 시뮬레이션을 수행합니다.")
        self.btn_apply_rlc.clicked.connect(self._apply_rlc_element)
        row_esr.addWidget(self.btn_apply_rlc)

        row_esr.addStretch()
        rlc_layout.addLayout(row_esr)

        self.tabs.addTab(tab_rlc, "RLC 소자")

        # --- 탭 2: SPICE 서브서킷 (.SUBCKT) ---
        tab_spice = QtWidgets.QWidget()
        spice_layout = QtWidgets.QVBoxLayout(tab_spice)
        spice_layout.setContentsMargins(8, 8, 8, 8)
        spice_layout.setSpacing(6)

        info_lbl = QtWidgets.QLabel("※ 핀1과 핀2는 회로도 노드에 맞춰 자동 연결됩니다.")
        info_lbl.setStyleSheet("color: #79b8ff; font-size: 10.5px; font-weight: normal;")
        spice_layout.addWidget(info_lbl)

        self.edit_subckt = QtWidgets.QPlainTextEdit()
        self.edit_subckt.setPlaceholderText(".SUBCKT 모델명 핀1 핀2\n...\n.ENDS")
        self.edit_subckt.setMinimumHeight(95)
        spice_layout.addWidget(self.edit_subckt)

        btn_row = QtWidgets.QHBoxLayout()
        self.btn_template = QtWidgets.QPushButton("기본 템플릿 삽입")
        self.btn_template.clicked.connect(self._insert_template)
        btn_row.addWidget(self.btn_template)

        self.btn_load_lib = QtWidgets.QPushButton("파일 불러오기...")
        self.btn_load_lib.clicked.connect(self._load_spice_file)
        btn_row.addWidget(self.btn_load_lib)

        btn_row.addStretch()

        self.btn_apply_spice = QtWidgets.QPushButton("SPICE 모델 적용")
        self.btn_apply_spice.setStyleSheet("background-color: #0d598a; color: #ffffff; font-weight: bold;")
        self.btn_apply_spice.clicked.connect(self._apply_spice_model)
        btn_row.addWidget(self.btn_apply_spice)

        self.btn_clear_spice = QtWidgets.QPushButton("기본값 복원")
        self.btn_clear_spice.clicked.connect(self._clear_spice_model)
        btn_row.addWidget(self.btn_clear_spice)

        spice_layout.addLayout(btn_row)
        self.tabs.addTab(tab_spice, "SPICE 모델 (.SUBCKT)")

        layout.addWidget(self.tabs)

    def set_active_component(self, name: str, comp_type: str, val: float, esr_val: float, tol: str, spice_model: dict = None):
        """활성 부품 정보로 카드 UI 갱신"""
        self.current_name = name
        self.current_type = comp_type
        self.current_val = float(val)
        self.current_esr = float(esr_val)
        self.current_tol = tol

        self.lbl_badge.setText(name)
        color = "#00e5ff" if comp_type == 'L' else ("#ff66cc" if comp_type == 'C' else "#ffaa00")
        self.lbl_badge.setStyleSheet(f"background-color: {color}; color: #000000; font-weight: bold; font-size: 13px; border-radius: 4px; padding: 2px 8px;")

        desc_text = COMP_DESCRIPTIONS.get(name, '')
        self.lbl_desc.setText(f"({desc_text})")

        self.combo_tol.blockSignals(True)
        self.combo_tol.clear()
        self.combo_tol.addItems(list(rlc.TOLERANCE_MAP[comp_type].keys()))
        self.combo_tol.setCurrentText(tol)
        self.combo_tol.blockSignals(False)

        # 단위 콤보박스에 해당 소자 타입 전용 단위 목록 로드
        self.combo_unit.blockSignals(True)
        self.combo_unit.clear()
        self.combo_unit.addItems(COMP_UNITS.get(comp_type, ['nH']))
        self.combo_unit.blockSignals(False)

        self.spin_esr.blockSignals(True)
        self.spin_esr.setValue(self.current_esr)
        self.spin_esr.blockSignals(False)

        self._refresh_available_values()

        if spice_model and spice_model.get('mode') == 'subckt' and spice_model.get('text'):
            self.current_subckt_text = spice_model['text']
            self.current_subckt_name = spice_model.get('model_name', '')
            self.edit_subckt.setPlainText(self.current_subckt_text)
            self.lbl_big_val.setText(f"[{self.current_subckt_name}]")
            self.tabs.setCurrentIndex(1)
        else:
            self.current_subckt_text = ''
            self.current_subckt_name = ''
            self.edit_subckt.clear()
            self._sync_ui()
            self.tabs.setCurrentIndex(0)

    def _refresh_available_values(self):
        """
        RLC 기본 콤보박스 목록 갱신:
        - rlc_values.json 파일이 존재하면 R, L, C 분류별로 정의된 목록을 최우선 로드하여 사용
        - JSON에 해당 소자 타입 항목이 없거나 비어있는 경우 기존 E-시리즈 공칭값 생성 로직으로 fallback
        """
        loaded_dict = rlc.load_rlc_values_json()
        comp_items = loaded_dict.get(self.current_type.upper(), [])

        self.available_values = []
        display_texts = []

        if comp_items:
            for v, txt in comp_items:
                self.available_values.append(v)
                display_texts.append(txt)
        else:
            base_list = rlc.get_e_series_base(self.current_type, self.current_tol)
            if self.current_type == 'L':
                min_v, max_v = 1e-9, 1e-5
            elif self.current_type == 'C':
                min_v, max_v = 0.5e-12, 1e-7
            else:
                min_v, max_v = 0.1, 1e6

            self.available_values = rlc.generate_available_values(base_list, min_v, max_v)
            display_texts = [rlc.format_engineering(v, self.current_type) for v in self.available_values]

        self.combo_val.blockSignals(True)
        self.combo_val.clear()
        for v, txt in zip(self.available_values, display_texts):
            self.combo_val.addItem(txt, v)
        self.combo_val.blockSignals(False)

    def _sync_ui(self):
        """현재 공칭값에 가장 근접한 콤보박스 항목 선택 및 수치/단위 입력란 동기화"""
        diffs = [abs(v - self.current_val) for v in self.available_values]
        best_idx = 0
        if diffs:
            best_idx = int(diffs.index(min(diffs)))
            self.current_val = self.available_values[best_idx]

        self.combo_val.blockSignals(True)
        self.combo_val.setCurrentIndex(best_idx)
        self.combo_val.blockSignals(False)

        val_text = rlc.format_engineering(self.current_val, self.current_type)
        self.lbl_big_val.setText(val_text)

        # 수치 스핀박스 및 단위 콤보박스 분리 동기화
        num, u = split_val_and_unit(self.current_val, self.current_type)
        self.spin_direct_val.blockSignals(True)
        self.spin_direct_val.setValue(num)
        self.spin_direct_val.blockSignals(False)

        self.combo_unit.blockSignals(True)
        self.combo_unit.setCurrentText(u)
        self.combo_unit.blockSignals(False)

    def _on_tol_changed(self, new_tol: str):
        self.current_tol = new_tol
        self._refresh_available_values()
        self._sync_ui()
        self.tolerance_changed.emit(self.current_name, self.current_tol)
        self.value_changed.emit(self.current_name, self.current_val)

    def _on_combo_val_changed(self, idx: int):
        if idx >= 0 and idx < len(self.available_values):
            self.current_val = self.available_values[idx]
            val_text = rlc.format_engineering(self.current_val, self.current_type)
            self.lbl_big_val.setText(val_text)

            # 수치/단위 분리 동기화
            num, u = split_val_and_unit(self.current_val, self.current_type)
            self.spin_direct_val.blockSignals(True)
            self.spin_direct_val.setValue(num)
            self.spin_direct_val.blockSignals(False)

            self.combo_unit.blockSignals(True)
            self.combo_unit.setCurrentText(u)
            self.combo_unit.blockSignals(False)

            self.value_changed.emit(self.current_name, self.current_val)

    def _on_direct_val_changed(self, val: float):
        """수치 입력 스핀박스 변경 시 즉시 결합 계산 및 회로 반영"""
        u = self.combo_unit.currentText()
        mult = UNIT_MULTIPLIERS.get(u, 1e-9)
        self.current_val = float(val) * mult
        self.lbl_big_val.setText(rlc.format_engineering(self.current_val, self.current_type))
        self.value_changed.emit(self.current_name, self.current_val)

    def _on_unit_changed(self, text: str):
        """단위 콤보박스 변경 시 즉시 결합 계산 및 회로 반영"""
        num = self.spin_direct_val.value()
        mult = UNIT_MULTIPLIERS.get(text, 1e-9)
        self.current_val = float(num) * mult
        self.lbl_big_val.setText(rlc.format_engineering(self.current_val, self.current_type))
        self.value_changed.emit(self.current_name, self.current_val)

    def _on_snap_clicked(self):
        """입력된 [수치]*[단위] 값을 가장 가까운 표준 E-시리즈 공칭값으로 스냅 및 적용"""
        num = self.spin_direct_val.value()
        u = self.combo_unit.currentText()
        mult = UNIT_MULTIPLIERS.get(u, 1e-9)
        raw_val = float(num) * mult

        base_list = rlc.get_e_series_base(self.current_type, self.current_tol)
        snapped = rlc.snap_to_e_series(raw_val, base_list)
        self.current_val = snapped
        self._sync_ui()
        self.value_changed.emit(self.current_name, self.current_val)

    def _on_esr_changed(self, val: float):
        self.current_esr = float(val)
        self.esr_changed.emit(self.current_name, self.current_esr)

    def _step_prev(self):
        idx = self.combo_val.currentIndex()
        if idx > 0:
            self.combo_val.setCurrentIndex(idx - 1)

    def _step_next(self):
        idx = self.combo_val.currentIndex()
        if idx < self.combo_val.count() - 1:
            self.combo_val.setCurrentIndex(idx + 1)

    def _insert_template(self):
        if self.current_type == 'L':
            tmpl = (
                f"* High-Q Inductor Model\n"
                f".SUBCKT IND_HQ_1 1 2\n"
                f"L1 1 3 {self.current_val * 1e9:.2f}n\n"
                f"R1 3 2 {self.current_esr:.3f}\n"
                f"Cp 1 2 0.12p\n"
                f".ENDS IND_HQ_1"
            )
        else:
            tmpl = (
                f"* Low-ESR Capacitor Model\n"
                f".SUBCKT CAP_HQ_1 1 2\n"
                f"C1 1 3 {self.current_val * 1e12:.2f}p\n"
                f"R1 3 2 {self.current_esr:.3f}\n"
                f"Ls 2 0 0.25n\n"
                f".ENDS CAP_HQ_1"
            )
        self.edit_subckt.setPlainText(tmpl)

    def _load_spice_file(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "SPICE 서브서킷 파일 열기", "", "SPICE Netlist (*.cir *.sub *.lib *.sp *.txt);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    self.edit_subckt.setPlainText(f.read())
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "파일 열기 실패", str(e))

    def _apply_spice_model(self):
        text = self.edit_subckt.toPlainText().strip()
        if not text:
            QtWidgets.QMessageBox.warning(self, "입력 필요", ".SUBCKT 모델 텍스트를 입력해주세요.")
            return

        match = re.search(r"^\s*\.SUBCKT\s+(\S+)", text, re.IGNORECASE | re.MULTILINE)
        if not match:
            QtWidgets.QMessageBox.warning(self, "형식 오류", ".SUBCKT (모델명) (핀1) (핀2) 형식이어야 합니다.")
            return

        model_name = match.group(1)
        self.current_subckt_name = model_name
        self.current_subckt_text = text
        self.lbl_big_val.setText(f"[{model_name}]")

        self.spice_model_changed.emit(self.current_name, 'subckt', text)

    def _apply_rlc_element(self):
        """
        RLC 소자 적용 버튼 클릭 시:
        - 해당 부품의 SPICE 서브서킷 모드를 해제(value 모드로 전환)
        - 상단 배지에서 SPICE 모델명을 지우고 현재 RLC 공칭값으로 복원
        - RLC 공칭값 및 개별 ESR 값을 즉시 회로에 반영하고 시뮬레이션 결과 갱신
        """
        self.current_subckt_name = ''
        self.current_subckt_text = ''
        self.edit_subckt.clear()
        val_text = rlc.format_engineering(self.current_val, self.current_type)
        self.lbl_big_val.setText(val_text)

        # 수치 스핀박스 및 단위 콤보박스 동기화
        num, u = split_val_and_unit(self.current_val, self.current_type)
        self.spin_direct_val.blockSignals(True)
        self.spin_direct_val.setValue(num)
        self.spin_direct_val.blockSignals(False)

        self.combo_unit.blockSignals(True)
        self.combo_unit.setCurrentText(u)
        self.combo_unit.blockSignals(False)

        self.spice_model_changed.emit(self.current_name, 'value', '')
        self.value_changed.emit(self.current_name, self.current_val)
        self.esr_changed.emit(self.current_name, self.current_esr)

    def _clear_spice_model(self):
        self.current_subckt_name = ''
        self.current_subckt_text = ''
        self.edit_subckt.clear()
        self._sync_ui()
        self.tabs.setCurrentIndex(0)
        self.spice_model_changed.emit(self.current_name, 'value', '')


class ComponentPropertyPanel(QtWidgets.QWidget):
    """
    회로도 옆 개별 속성 편집 패널
    - 리스트 목록 UI를 제거하고 개별 부품 상세 설정에 집중
    - 상단 부품 선택 콤보박스 및 빠른 전환 버튼 제공
    - 회로도 부품 클릭과 양방향 완벽 동기화
    """

    component_value_changed = QtCore.Signal(str, float)
    component_esr_changed = QtCore.Signal(str, float)
    sys_param_changed = QtCore.Signal(str, float)
    component_selected = QtCore.Signal(str)
    spice_model_changed = QtCore.Signal(str, str, str)

    def __init__(self, initial_components: dict, initial_esr: dict, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(380)
        self.setMaximumWidth(520)

        # 소자별 현재 상태 저장소
        self.components = dict(initial_components)
        self.esr_values = dict(initial_esr)
        self.tolerances = {}
        for name in ALL_COMPONENTS:
            ctype = 'L' if name.startswith('L') else 'C'
            self.tolerances[name] = rlc.DEFAULT_TOLERANCE[ctype]

        self.spice_models = {}
        self.active_component = 'L1'
        self.quick_buttons = {}

        self._init_ui()

    @property
    def current_comp(self) -> str:
        """하위 호환성을 위한 현재 활성 부품 이름 반환"""
        return self.active_component

    @current_comp.setter
    def current_comp(self, val: str):
        self.active_component = val

    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(8)

        # 1. 상단 안내 배너
        info_banner = QtWidgets.QFrame()
        info_banner.setStyleSheet("""
            QFrame {
                background-color: #172030;
                border: 1px solid #283a54;
                border-radius: 4px;
                padding: 4px;
            }
            QLabel {
                color: #79b8ff;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        info_layout = QtWidgets.QHBoxLayout(info_banner)
        info_layout.setContentsMargins(6, 4, 6, 4)
        lbl_info = QtWidgets.QLabel("💡 회로도에서 부품을 클릭하거나 아래에서 선택하여 개별 속성을 편집합니다.")
        info_layout.addWidget(lbl_info)
        main_layout.addWidget(info_banner)

        # 2. 부품 빠른 선택기 (Quick Component Selector)
        selector_box = QtWidgets.QGroupBox("부품 선택 (Select Component)")
        selector_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11px;
                color: #00ffff;
                border: 1px solid #36364a;
                border-radius: 4px;
                margin-top: 6px;
                padding-top: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
            QPushButton {
                background-color: #222232;
                border: 1px solid #3c3c54;
                border-radius: 3px;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 6px;
            }
            QPushButton:hover {
                background-color: #35354e;
            }
        """)
        selector_layout = QtWidgets.QVBoxLayout(selector_box)
        selector_layout.setContentsMargins(8, 6, 8, 6)
        selector_layout.setSpacing(6)

        # 드롭다운 콤보박스 행
        combo_row = QtWidgets.QHBoxLayout()
        lbl_combo = QtWidgets.QLabel("선택 부품:")
        lbl_combo.setStyleSheet("color: #cccccc; font-weight: bold; font-size: 11px;")
        combo_row.addWidget(lbl_combo)

        self.combo_component = QtWidgets.QComboBox()
        self.combo_component.setMaxVisibleItems(12)
        self.combo_component.setStyleSheet("""
            QComboBox {
                background-color: #161622;
                color: #ffff00;
                border: 1px solid #ffaa00;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12.5px;
                font-weight: bold;
                min-height: 28px;
            }
            QComboBox QAbstractItemView {
                background-color: #181826;
                color: #ffffff;
                selection-background-color: #2b3a55;
                selection-color: #ffff00;
                border: 1px solid #ffaa00;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                min-height: 28px;
                padding: 4px 10px;
                color: #ffffff;
                background-color: #181826;
                font-size: 12px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #28283c;
                color: #ffff00;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #2b3a55;
                color: #ffff00;
                font-weight: bold;
            }
        """)
        for name in ALL_COMPONENTS:
            desc = COMP_DESCRIPTIONS.get(name, '')
            self.combo_component.addItem(f"{name} : {desc}", name)
        self.combo_component.currentIndexChanged.connect(self._on_combo_component_selected)
        combo_row.addWidget(self.combo_component, stretch=1)
        selector_layout.addLayout(combo_row)

        # 퀵 선택 버튼 행 (직렬 인덕터 & 병렬 탱크)
        btn_grid = QtWidgets.QHBoxLayout()
        btn_grid.setSpacing(4)

        # 직렬 인덕터 그룹
        lbl_s = QtWidgets.QLabel("직렬:")
        lbl_s.setStyleSheet("color: #00e5ff; font-weight: bold; font-size: 10px;")
        btn_grid.addWidget(lbl_s)
        for name in ['L1', 'L2', 'L3', 'L4']:
            btn = QtWidgets.QPushButton(name)
            btn.setFixedWidth(34)
            btn.setStyleSheet("color: #00e5ff;")
            btn.clicked.connect(lambda _, n=name: self.select_component(n))
            self.quick_buttons[name] = btn
            btn_grid.addWidget(btn)

        btn_grid.addSpacing(6)

        # 병렬 소자 그룹
        lbl_p = QtWidgets.QLabel("병렬:")
        lbl_p.setStyleSheet("color: #ff66cc; font-weight: bold; font-size: 10px;")
        btn_grid.addWidget(lbl_p)
        for name in ['L5', 'C1', 'L6', 'C2', 'L7', 'C3']:
            btn = QtWidgets.QPushButton(name)
            btn.setFixedWidth(34)
            color = "#00e5ff" if name.startswith('L') else "#ff66cc"
            btn.setStyleSheet(f"color: {color};")
            btn.clicked.connect(lambda _, n=name: self.select_component(n))
            self.quick_buttons[name] = btn
            btn_grid.addWidget(btn)

        selector_layout.addLayout(btn_grid)
        main_layout.addWidget(selector_box)

        # 3. 선택된 부품 상세 편집 카드
        self.active_card = ActiveComponentCard()
        self.active_card.value_changed.connect(self._on_card_value_changed)
        self.active_card.esr_changed.connect(self._on_card_esr_changed)
        self.active_card.tolerance_changed.connect(self._on_card_tolerance_changed)
        self.active_card.spice_model_changed.connect(self._on_card_spice_changed)
        main_layout.addWidget(self.active_card)

        # 4. 시스템 설정 (포트 Z0)
        sys_box = QtWidgets.QGroupBox("시스템 설정 (System Parameters)")
        sys_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11px;
                color: #cccccc;
                border: 1px solid #36364a;
                border-radius: 4px;
                margin-top: 6px;
                padding-top: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
            QLabel { color: #aaaaaa; font-size: 11px; }
            QDoubleSpinBox {
                background-color: #1e1e2c;
                color: #ffaa00;
                border: 1px solid #444458;
                border-radius: 3px;
                padding: 3px 6px;
                font-weight: bold;
            }
        """)
        sys_layout = QtWidgets.QHBoxLayout(sys_box)
        sys_layout.setContentsMargins(8, 6, 8, 6)

        sys_layout.addWidget(QtWidgets.QLabel("포트(Z0):"))
        self.spin_z0 = QtWidgets.QDoubleSpinBox()
        self.spin_z0.setRange(0.0, 300.0)
        self.spin_z0.setValue(50.0)
        self.spin_z0.setSuffix(" Ω")
        self.spin_z0.valueChanged.connect(lambda v: self.sys_param_changed.emit('Z0', v))
        sys_layout.addWidget(self.spin_z0)

        sys_layout.addStretch()
        main_layout.addWidget(sys_box)

        # 하단 여백 채우기 (리스트 목록 UI가 제거되어 깔끔하고 여유로운 배치 유지)
        main_layout.addStretch()

        # 기본 부품(L1) 선택 초기화
        self.select_component('L1')

    def _on_combo_component_selected(self, idx: int):
        """부품 드롭다운 선택 시 해당 부품 활성화"""
        if idx >= 0:
            name = self.combo_component.itemData(idx)
            if name and name != self.active_component:
                self.select_component(name)

    def update_component_dict(self, components: dict, esr_values: dict = None, comp_types: dict = None):
        """외부(넷리스트 적용 등)에서 소자 목록이 변경되었을 때 콤보박스 및 내부 딕셔너리 갱신"""
        self.components = dict(components)
        if esr_values:
            self.esr_values.update(esr_values)

        self.combo_component.blockSignals(True)
        self.combo_component.clear()
        for name in self.components:
            desc = COMP_DESCRIPTIONS.get(name, f"저항 {name}" if name.startswith('R') else f"소자 {name}")
            self.combo_component.addItem(f"{name} : {desc}", name)
        self.combo_component.blockSignals(False)

        # 활성 소자가 새 소자 목록에 있으면 유지, 없으면 첫 번째 소자 선택
        if self.active_component in self.components:
            self.select_component(self.active_component)
        elif self.components:
            first_name = list(self.components.keys())[0]
            self.select_component(first_name)

    def select_component(self, name: str, spice_model: dict = None):
        """특정 부품을 활성화하고 카드 편집기에 반영"""
        if name not in self.components:
            return

        self.active_component = name

        # 콤보박스에 해당 소자가 없으면 동적으로 추가
        idx = self.combo_component.findData(name)
        if idx < 0:
            desc = COMP_DESCRIPTIONS.get(name, f"저항 {name}" if name.startswith('R') else f"소자 {name}")
            self.combo_component.addItem(f"{name} : {desc}", name)
            idx = self.combo_component.findData(name)

        # 콤보박스 동기화
        if idx >= 0 and self.combo_component.currentIndex() != idx:
            self.combo_component.blockSignals(True)
            self.combo_component.setCurrentIndex(idx)
            self.combo_component.blockSignals(False)

        # 퀵 버튼 하이라이트 갱신
        for btn_name, btn in self.quick_buttons.items():
            if btn_name == name:
                color = "#00e5ff" if name.startswith('L') else ("#ff66cc" if name.startswith('C') else "#ffaa00")
                btn.setStyleSheet(f"background-color: #383858; border: 2px solid #ffaa00; color: {color}; font-weight: bold;")
            else:
                color = "#00e5ff" if btn_name.startswith('L') else ("#ff66cc" if btn_name.startswith('C') else "#ffaa00")
                btn.setStyleSheet(f"background-color: #222232; border: 1px solid #3c3c54; color: {color};")

        # 소자 타입 판별 (R: 저항, L: 인덕터, C: 커패시터)
        if name.startswith('R'):
            comp_type = 'R'
        elif name.startswith('L'):
            comp_type = 'L'
        else:
            comp_type = 'C'

        val = self.components.get(name, 1000.0 if comp_type == 'R' else (18e-9 if comp_type == 'L' else 6.8e-12))
        esr_val = self.esr_values.get(name, 0.0 if comp_type == 'R' else 0.35)
        tol = self.tolerances.get(name, rlc.DEFAULT_TOLERANCE.get(comp_type, '5% (E24)'))

        if spice_model is None:
            spice_model = self.spice_models.get(name, {'mode': 'value', 'text': '', 'model_name': ''})

        self.active_card.set_active_component(name, comp_type, val, esr_val, tol, spice_model)
        self.component_selected.emit(name)

    def _on_card_value_changed(self, name: str, val: float):
        """활성 카드의 공칭값 변경 처리"""
        self.components[name] = float(val)
        self.component_value_changed.emit(name, val)

    def _on_card_esr_changed(self, name: str, esr_val: float):
        """활성 카드의 개별 ESR 변경 처리"""
        self.esr_values[name] = float(esr_val)
        self.component_esr_changed.emit(name, esr_val)

    def _on_card_tolerance_changed(self, name: str, tol: str):
        """활성 카드의 오차율 변경 처리"""
        self.tolerances[name] = tol

    def _on_card_spice_changed(self, name: str, mode: str, text: str):
        """활성 카드의 SPICE 모델 변경 처리"""
        match = re.search(r"^\s*\.SUBCKT\s+(\S+)", text, re.IGNORECASE | re.MULTILINE)
        mname = match.group(1) if match else ''
        self.spice_models[name] = {
            'mode': mode,
            'text': text,
            'model_name': mname
        }
        self.spice_model_changed.emit(name, mode, text)

    def update_component_value(self, name: str, val: float, esr_val: float = None):
        """외부(프리셋, 기본값 복원 등)로부터 부품값 및 ESR 업데이트"""
        if name in self.components:
            self.components[name] = float(val)
            if esr_val is not None:
                self.esr_values[name] = float(esr_val)

            if name == self.active_component:
                comp_type = 'L' if name.startswith('L') else 'C'
                tol = self.tolerances.get(name, rlc.DEFAULT_TOLERANCE[comp_type])
                cur_esr = self.esr_values.get(name, 0.35)
                sm = self.spice_models.get(name, {'mode': 'value', 'text': '', 'model_name': ''})
                self.active_card.set_active_component(name, comp_type, val, cur_esr, tol, sm)
