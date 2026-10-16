# -*- coding: utf-8 -*-
"""
RLC 대역통과 필터(BPF) 시뮬레이터 & S-Parameter 분석기 메인 애플리케이션
- 커패시터/인덕터 개별 ESR 속성 반영 및 R=0 시 1pΩ 치환
- ngspice 시뮬레이션 결과 실시간 프로브(Probe) 및 데이터 테이블 지원
- SPICE 서브서킷(.SUBCKT) 핀1, 핀2 자동 매핑
- Tr1(S11)~Tr4(S22) 개별 체크박스 토글 및 X/Y Log/Linear 스케일 제어
"""

import sys
import os
import subprocess
import warnings
import logging
import json

# 불필요한 콘솔 경고 메시지 억제
warnings.filterwarnings("ignore")
logging.getLogger('matplotlib').setLevel(logging.ERROR)

from PySide6 import QtWidgets, QtCore, QtGui

import rlc_standards as rlc
import circuit_engine as ce
from schematic_widget import CircuitSchematicWidget
from property_panel import ComponentPropertyPanel
from analyzer_widget import NetworkAnalyzerWidget


__version__ = "0.2.2"
__author__ = "행복찾기"



def get_app_icon() -> QtGui.QIcon:
    """앱 아이콘 파일 탐색 및 QIcon 객체 반환"""
    search_dirs = [
        getattr(sys, '_MEIPASS', ''),
        os.path.dirname(os.path.abspath(__file__)),
        os.getcwd(),
    ]
    for d in search_dirs:
        if d:
            ico_path = os.path.join(d, 'app_icon.ico')
            if os.path.exists(ico_path):
                return QtGui.QIcon(ico_path)
            png_path = os.path.join(d, 'app_icon.png')
            if os.path.exists(png_path):
                return QtGui.QIcon(png_path)
    return QtGui.QIcon()


class BPFMainWindow(QtWidgets.QMainWindow):
    """
    BPF 시뮬레이터 메인 윈도우
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"RLC 대역통과 필터(BPF) 시뮬레이터 & S-Parameter 분석기 v{__version__} [제작: {__author__}]")
        self.setWindowIcon(get_app_icon())
        self.resize(1340, 920)
        self.setMinimumSize(1020, 720)

        # 회로 해석 엔진 초기화
        self.engine = ce.CircuitEngine()

        self._init_ui()
        self._apply_dark_theme()

        # NGSpice 가용성 확인 및 UI 상태 동기화 (ngspice 없을 시 비활성화)
        self._update_ngspice_availability()

        # 초기 계산 및 UI 동기화
        self._run_simulation()

    def _apply_dark_theme(self):
        """전문가용 RF 계측기 스타일 다크 테마 적용"""
        app = QtWidgets.QApplication.instance()
        if app:
            font = QtGui.QFont("Malgun Gothic", 9)
            app.setFont(font)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #12121a;
                color: #e0e0e0;
            }
            QToolBar {
                background-color: #1a1a24;
                border-bottom: 1px solid #2e2e3e;
                padding: 4px;
                spacing: 8px;
            }
            QToolButton {
                background-color: #2b2b3d;
                color: #ffffff;
                border: 1px solid #44445c;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: bold;
                font-size: 11px;
            }
            QToolButton:hover {
                background-color: #3d3d56;
                border-color: #00ffff;
                color: #00ffff;
            }
            QToolButton:pressed {
                background-color: #1e1e2c;
            }
            QStatusBar {
                background-color: #1a1a24;
                color: #888899;
                font-size: 11px;
                border-top: 1px solid #2e2e3e;
            }
            QSplitter::handle {
                background-color: #2b2b3b;
            }
            QSplitter::handle:hover {
                background-color: #00e5ff;
            }
            QComboBox QAbstractItemView {
                background-color: #1a1a28;
                color: #ffffff;
                selection-background-color: #00ffff;
                selection-color: #000000;
                border: 1px solid #444466;
            }
        """)

    def _init_ui(self):
        # 1. 상단 툴바 구성
        toolbar = self.addToolBar("기능")
        toolbar.setMovable(False)

        # 1) 기본값 복원 버튼
        btn_reset = QtWidgets.QToolButton()
        btn_reset.setText("기본값")
        btn_reset.setToolTip("기본 BPF 회로 소자값 및 기본 설정으로 초기화 복원합니다.")
        btn_reset.clicked.connect(self._reset_to_default)
        toolbar.addWidget(btn_reset)

        # 2) 로드 버튼 (JSON 파일 불러오기)
        btn_load = QtWidgets.QToolButton()
        btn_load.setText("로드")
        btn_load.setToolTip("저장된 회로도 및 설정 JSON 파일을 불러와 회로와 설정을 복원합니다.")
        btn_load.clicked.connect(self._load_project_json)
        toolbar.addWidget(btn_load)

        # 3) 저장 버튼 (JSON 파일로 저장)
        btn_save = QtWidgets.QToolButton()
        btn_save.setText("저장")
        btn_save.setToolTip("현재 회로도와 시뮬레이션 설정값을 JSON 파일로 저장합니다.")
        btn_save.clicked.connect(self._save_project_json)
        toolbar.addWidget(btn_save)

        toolbar.addSeparator()

        # 4) Spice 넷리스트 버튼
        btn_netlist = QtWidgets.QToolButton()
        btn_netlist.setText("Spice 넷리스트")
        btn_netlist.setToolTip("SPICE 넷리스트를 직접 입력/편집하여 회로도를 변경하거나 기본 템플릿을 로드합니다.")
        btn_netlist.clicked.connect(self._show_spice_netlist)
        toolbar.addWidget(btn_netlist)

        toolbar.addSeparator()

        # 5) 결과 CSV 저장 버튼
        btn_csv = QtWidgets.QToolButton()
        btn_csv.setText("결과 CSV 저장")
        btn_csv.setToolTip("현재 시뮬레이션 결과 파형(주파수 및 S11~S22)을 CSV 파일로 저장합니다.")
        btn_csv.clicked.connect(self._export_csv)
        toolbar.addWidget(btn_csv)

        # 6) .S2P 저장 버튼
        btn_s2p = QtWidgets.QToolButton()
        btn_s2p.setText(".S2P 저장")
        btn_s2p.setToolTip("현재 S-파라미터를 산업 표준 Touchstone 2포트 (.s2p) 파일로 저장합니다.")
        btn_s2p.clicked.connect(self._export_touchstone)
        toolbar.addWidget(btn_s2p)

        toolbar.addSeparator()

        # 7) NGSpice 로그 버튼
        btn_ngspice_log = QtWidgets.QToolButton()
        btn_ngspice_log.setText("NGSpice 로그")
        btn_ngspice_log.setToolTip("최근 NGSpice가 실행한 실제 넷리스트 및 해석 콘솔 출력(STDOUT/STDERR) 로그를 확인합니다.")
        btn_ngspice_log.clicked.connect(self._show_ngspice_log)
        toolbar.addWidget(btn_ngspice_log)

        toolbar.addSeparator()

        # 8) 설정 버튼 (NGSpice 실행 파일 경로 및 환경 설정)
        btn_settings = QtWidgets.QToolButton()
        btn_settings.setText("설정")
        btn_settings.setToolTip("NGSpice 실행 파일 경로 및 프로그램 환경 설정을 지정합니다.")
        btn_settings.clicked.connect(self._show_settings_dialog)
        toolbar.addWidget(btn_settings)

        # 2. 메인 스플리터 (상/하 분할)
        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.setCentralWidget(main_splitter)

        # --- 상단 섹션: 좌측 회로도 + 우측 속성 패널 ---
        top_container = QtWidgets.QWidget()
        top_layout = QtWidgets.QHBoxLayout(top_container)
        top_layout.setContentsMargins(4, 4, 4, 4)
        top_layout.setSpacing(6)

        # 상단 좌측: 회로도 위젯 (NGSpice 체크박스 포함)
        self.schematic_widget = CircuitSchematicWidget()
        self.schematic_widget.update_components(
            self.engine.components, self.engine.spice_models,
            self.engine.component_nodes, self.engine.comp_types
        )
        top_layout.addWidget(self.schematic_widget, stretch=6)

        # 상단 우측: 회로도 옆 속성 패널 (개별 ESR 포함)
        self.property_panel = ComponentPropertyPanel(self.engine.components, self.engine.esr_values)
        top_layout.addWidget(self.property_panel, stretch=4)

        main_splitter.addWidget(top_container)

        # --- 하단 섹션: S-파라미터 분석기 화면 (실시간 프로브 기능 포함) ---
        self.analyzer_widget = NetworkAnalyzerWidget()
        main_splitter.addWidget(self.analyzer_widget)

        main_splitter.setSizes([380, 500])

        # 3. 이벤트 시그널-슬롯 연결
        self.schematic_widget.component_clicked.connect(self._on_schematic_component_clicked)
        self.property_panel.component_selected.connect(self.schematic_widget.set_selected_component)

        # 회로도 상단 NGSpice 체크박스 토글
        self.schematic_widget.ngspice_toggled.connect(self._on_ngspice_toggled)

        # 속성 패널 소자 공칭값 변경
        self.property_panel.component_value_changed.connect(self._on_component_changed)
        # 속성 패널 소자 개별 ESR 변경
        self.property_panel.component_esr_changed.connect(self._on_component_esr_changed)
        # SPICE 서브서킷 모델 변경
        self.property_panel.spice_model_changed.connect(self._on_spice_model_changed)
        # 시스템 파라미터(Z0) 변경
        self.property_panel.sys_param_changed.connect(self._on_sys_param_changed)

        # 하단 분석기 X축 범위 및 스케일 변경
        self.analyzer_widget.axis_params_changed.connect(self._on_axis_params_changed)

        self.statusBar().showMessage("준비 완료 | 부품별 ESR 및 R=0 시 1pΩ 치환 규칙이 적용되었습니다.")

    def _on_schematic_component_clicked(self, name: str):
        spice_model = self.engine.get_spice_model(name)
        self.property_panel.select_component(name, spice_model)

    def _on_ngspice_toggled(self, checked: bool):
        self.engine.sys_params['use_ngspice'] = checked
        mode_text = "NGSpice (Spice64)" if checked else "ABCD 전송행렬"
        self.statusBar().showMessage(f"시뮬레이션 엔진 전환: {mode_text}")
        self._run_simulation()

    def _on_component_changed(self, name: str, val: float):
        self.engine.set_component(name, val)
        self.schematic_widget.update_components(
            self.engine.components, self.engine.spice_models,
            self.engine.component_nodes, self.engine.comp_types
        )
        self._run_simulation()
        ctype = self.schematic_widget.comp_types.get(name, 'L')
        self.statusBar().showMessage(f"소자 변경: {name} = {rlc.format_engineering(val, ctype)}")

    def _on_component_esr_changed(self, name: str, esr_val: float):
        """소자의 개별 ESR 값 변경 처리"""
        self.engine.set_component_esr(name, esr_val)
        self._run_simulation()
        rule_note = " (1pΩ 적용)" if esr_val <= 0 else ""
        self.statusBar().showMessage(f"소자 {name} ESR 변경: {esr_val:.3f} Ω{rule_note}")

    def _on_spice_model_changed(self, name: str, mode: str, text: str):
        self.engine.set_spice_model(name, mode, text)

        if mode == 'subckt':
            self.engine.sys_params['use_ngspice'] = True
            self.schematic_widget.set_ngspice_checked(True)
            self.statusBar().showMessage(f"소자 {name}에 SPICE 서브서킷 적용 -> NGSpice 자동 활성화")
        else:
            self.statusBar().showMessage(f"소자 {name} RLC 소자 공칭값으로 복원 및 적용 완료")

        self.schematic_widget.update_components(
            self.engine.components, self.engine.spice_models,
            self.engine.component_nodes, self.engine.comp_types
        )
        self._run_simulation()

    def _on_sys_param_changed(self, param_name: str, val: float):
        self.engine.sys_params[param_name] = val
        self._run_simulation()
        self.statusBar().showMessage(f"시스템 파라미터 변경: {param_name} = {val}")

    def _on_axis_params_changed(self):
        axis_params = self.analyzer_widget.get_axis_params()
        self.engine.sys_params['start_freq'] = axis_params['start_freq']
        self.engine.sys_params['stop_freq'] = axis_params['stop_freq']
        if 'num_points' in axis_params:
            self.engine.sys_params['num_points'] = axis_params['num_points']
        self._run_simulation()

    def _run_simulation(self):
        axis_params = self.analyzer_widget.get_axis_params()
        x_scale = axis_params.get('x_scale', 'Linear')
        if 'num_points' in axis_params:
            self.engine.sys_params['num_points'] = axis_params['num_points']

        sim_data = self.engine.calculate_s_parameters(x_scale=x_scale)
        self.analyzer_widget.update_simulation_data(sim_data)

        eng = sim_data.get('engine_type', '')
        t_str = sim_data.get('sim_time', '')
        t_info = f" ({t_str})" if t_str else ""
        self.statusBar().showMessage(f"시뮬레이션 완료 | 해석 엔진: {eng}{t_info}")

    def _reset_to_default(self):
        """기본 BPF 설계값 및 기본 ESR로 초기화 복원"""
        self.engine.reset_to_defaults()

        self.property_panel.update_component_dict(self.engine.components, self.engine.esr_values, self.engine.comp_types)
        self.property_panel.select_component('L1')

        self.schematic_widget.set_ngspice_checked(False)
        self.schematic_widget.update_components(
            self.engine.components, self.engine.spice_models,
            self.engine.component_nodes, self.engine.comp_types
        )
        self._run_simulation()
        self.statusBar().showMessage("기본 BPF 소자값 및 설정으로 복원되었습니다.")

    def _save_project_json(self):
        """현재 회로도 소자값, 개별 ESR, SPICE 모델 및 시뮬레이션 설정값을 JSON 파일로 저장"""
        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "회로 및 설정 JSON 저장", "bpf_circuit_config.json", "JSON Files (*.json);;All Files (*)"
        )
        if not filepath:
            return

        try:
            axis_params = self.analyzer_widget.get_axis_params()
            data = {
                "file_type": "BPF_CIRCUIT_CONFIG",
                "version": __version__,
                "saved_time": QtCore.QDateTime.currentDateTime().toString(QtCore.Qt.ISODate),
                "components": dict(self.engine.components),
                "esr_values": dict(self.engine.esr_values),
                "spice_models": dict(self.engine.spice_models),
                "custom_circuit_netlist": self.engine.custom_circuit_netlist,
                "sys_params": {
                    "Z0": float(self.engine.sys_params.get('Z0', 50.0)),
                    "start_freq": float(self.engine.sys_params.get('start_freq', 100e3)),
                    "stop_freq": float(self.engine.sys_params.get('stop_freq', 500e6)),
                    "num_points": int(self.engine.sys_params.get('num_points', 500)),
                    "use_ngspice": bool(self.engine.sys_params.get('use_ngspice', False))
                },
                "analyzer_settings": {
                    "start_mhz": float(self.analyzer_widget.spin_x_start.value()),
                    "stop_mhz": float(self.analyzer_widget.spin_x_stop.value()),
                    "num_points": int(self.analyzer_widget.spin_num_points.value()),
                    "x_scale": self.analyzer_widget.combo_x_scale.currentText(),
                    "y_min": float(self.analyzer_widget.spin_y_min.value()),
                    "y_max": float(self.analyzer_widget.spin_y_max.value()),
                    "y_scale": self.analyzer_widget.combo_y_scale.currentText(),
                    "mkr1_mhz": float(self.analyzer_widget.spin_mkr1.value()),
                    "mkr2_mhz": float(self.analyzer_widget.spin_mkr2.value()),
                    "trace_s11": self.analyzer_widget.chk_s11.isChecked(),
                    "trace_s12": self.analyzer_widget.chk_s12.isChecked(),
                    "trace_s21": self.analyzer_widget.chk_s21.isChecked(),
                    "trace_s22": self.analyzer_widget.chk_s22.isChecked(),
                }
            }

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.statusBar().showMessage(f"회로도 및 설정 저장 완료: {filepath}")
            QtWidgets.QMessageBox.information(self, "저장 완료", f"회로도 및 설정이 성공적으로 저장되었습니다:\n{filepath}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "저장 오류", f"JSON 파일 저장 중 오류가 발생했습니다:\n{e}")

    def _load_project_json(self):
        """저장된 회로도 및 설정 JSON 파일을 불러와 회로와 설정을 복원"""
        filepath, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "회로 및 설정 JSON 불러오기", "", "JSON Files (*.json);;All Files (*)"
        )
        if not filepath:
            return

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, dict):
                raise ValueError("올바른 JSON 데이터 형식이 아닙니다.")

            # 1. 회로 소자값 복원
            saved_comps = data.get('components', {})
            if saved_comps:
                self.engine.components = dict(saved_comps)

            # 2. 개별 ESR 값 복원
            saved_esr = data.get('esr_values', {})
            if saved_esr:
                self.engine.esr_values = dict(saved_esr)

            # 3. SPICE 모델 복원
            saved_models = data.get('spice_models', {})
            if saved_models:
                self.engine.spice_models = dict(saved_models)

            # 4. 커스텀 넷리스트 복원
            self.engine.custom_circuit_netlist = data.get('custom_circuit_netlist', None)

            # 5. 시스템 파라미터 복원
            saved_sys = data.get('sys_params', {})
            if saved_sys:
                self.engine.sys_params.update(saved_sys)
                use_ng = saved_sys.get('use_ngspice', False)
                self.schematic_widget.set_ngspice_checked(use_ng)
                if 'Z0' in saved_sys and hasattr(self.property_panel, 'spin_z0'):
                    self.property_panel.spin_z0.blockSignals(True)
                    self.property_panel.spin_z0.setValue(float(saved_sys['Z0']))
                    self.property_panel.spin_z0.blockSignals(False)

            # 6. 속성 편집 패널 UI 동기화
            self.property_panel.components = dict(self.engine.components)
            self.property_panel.esr_values = dict(self.engine.esr_values)
            self.property_panel.spice_models = dict(self.engine.spice_models)
            for name, val in self.engine.components.items():
                esr_v = self.engine.esr_values.get(name, 0.35)
                self.property_panel.update_component_value(name, val, esr_v)

            curr_name = self.property_panel.active_component
            if curr_name in self.engine.components:
                self.property_panel.select_component(curr_name)
            else:
                self.property_panel.select_component('L1')

            # 7. 분석기 설정 복원
            ana_cfg = data.get('analyzer_settings', {})
            if ana_cfg:
                if 'start_mhz' in ana_cfg:
                    self.analyzer_widget.spin_x_start.setValue(ana_cfg['start_mhz'])
                if 'stop_mhz' in ana_cfg:
                    self.analyzer_widget.spin_x_stop.setValue(ana_cfg['stop_mhz'])
                if 'num_points' in ana_cfg:
                    self.analyzer_widget.spin_num_points.setValue(ana_cfg['num_points'])
                if 'x_scale' in ana_cfg:
                    self.analyzer_widget.combo_x_scale.setCurrentText(ana_cfg['x_scale'])
                if 'y_min' in ana_cfg:
                    self.analyzer_widget.spin_y_min.setValue(ana_cfg['y_min'])
                if 'y_max' in ana_cfg:
                    self.analyzer_widget.spin_y_max.setValue(ana_cfg['y_max'])
                if 'y_scale' in ana_cfg:
                    self.analyzer_widget.combo_y_scale.setCurrentText(ana_cfg['y_scale'])
                if 'mkr1_mhz' in ana_cfg:
                    self.analyzer_widget.spin_mkr1.setValue(ana_cfg['mkr1_mhz'])
                if 'mkr2_mhz' in ana_cfg:
                    self.analyzer_widget.spin_mkr2.setValue(ana_cfg['mkr2_mhz'])
                if 'trace_s11' in ana_cfg:
                    self.analyzer_widget.chk_s11.setChecked(ana_cfg['trace_s11'])
                if 'trace_s12' in ana_cfg:
                    self.analyzer_widget.chk_s12.setChecked(ana_cfg['trace_s12'])
                if 'trace_s21' in ana_cfg:
                    self.analyzer_widget.chk_s21.setChecked(ana_cfg['trace_s21'])
                if 'trace_s22' in ana_cfg:
                    self.analyzer_widget.chk_s22.setChecked(ana_cfg['trace_s22'])

            # 8. 회로도 및 시뮬레이션 재실행
            self.schematic_widget.update_components(
                self.engine.components, self.engine.spice_models,
                self.engine.component_nodes, self.engine.comp_types
            )
            self._run_simulation()
            self.statusBar().showMessage(f"회로 및 설정 불러오기 완료: {filepath}")
            QtWidgets.QMessageBox.information(self, "로드 완료", f"회로도 및 설정이 성공적으로 로드되었습니다:\n{filepath}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "로드 오류", f"JSON 파일 불러오기 중 오류가 발생했습니다:\n{e}")

    def _export_csv(self):
        """현재 시뮬레이션 결과 파형(주파수 및 S11~S22)을 CSV 파일로 저장"""
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "시뮬레이션 결과 CSV 파일 저장", "bpf_simulation_results.csv", "CSV Files (*.csv);;All Files (*)"
        )
        if file_path:
            try:
                self.engine.export_results_csv(file_path)
                QtWidgets.QMessageBox.information(self, "저장 완료", f"시뮬레이션 결과가 CSV 파일로 성공적으로 저장되었습니다:\n{file_path}")
                self.statusBar().showMessage(f"CSV 저장 완료: {file_path}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "저장 오류", f"CSV 파일 저장 중 오류가 발생했습니다:\n{str(e)}")

    def _show_spice_netlist(self):
        """
        SPICE 넷리스트 편집기 다이얼로그
        - 넷리스트 값을 직접 편집하여 회로도에 즉시 반영
        - Port 1('in')에서 Port 2('out') 연결 논리 검증 및 오류 시 이전 상태로 복원
        - 기본값 템플릿 로드 기능 제공
        """
        curr_netlist = self.engine.generate_pure_circuit_netlist()

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("SPICE 넷리스트 편집 및 회로 반영")
        dlg.resize(650, 560)
        dlg_layout = QtWidgets.QVBoxLayout(dlg)
        dlg_layout.setSpacing(8)

        # 상단 안내 레이블
        info_lbl = QtWidgets.QLabel(
            "<b>※ SPICE 넷리스트 직접 편집 및 회로 반영</b><br>"
            "<span style='color: #88aacc;'>• 신호 입력은 <b>'in'</b>(Port 1), 출력은 <b>'out'</b>(Port 2), 접지는 <b>'0'</b> 이어야 합니다.<br>"
            "• 넷리스트 수정 후 <b>[ ⚡ 회로도 및 시뮬레이션 적용 ]</b>을 누르면 회로도가 갱신됩니다.<br>"
            "• 구문 오류나 연결 논리 불일치 시 에러 메시지와 함께 이전 상태로 자동 복원됩니다.</span>"
        )
        info_lbl.setStyleSheet("background-color: #1a2233; border: 1px solid #2e4466; border-radius: 4px; padding: 6px;")
        dlg_layout.addWidget(info_lbl)

        # 넷리스트 텍스트 에디터 (편집 가능)
        txt_edit = QtWidgets.QPlainTextEdit()
        txt_edit.setPlainText(curr_netlist)
        txt_edit.setReadOnly(False)
        txt_edit.setFont(QtGui.QFont("Consolas", 10))
        txt_edit.setStyleSheet(
            "background-color: #0d1117; color: #7ee787; border: 1px solid #2e4466; "
            "border-radius: 4px; padding: 4px; font-family: Consolas, monospace;"
        )
        dlg_layout.addWidget(txt_edit)

        # 하단 버튼 영역
        btn_box = QtWidgets.QHBoxLayout()

        # [ 📄 기본 템플릿 로드 ]
        btn_template = QtWidgets.QPushButton("📄 기본 템플릿 로드")
        btn_template.setToolTip("L1=L4=22n, L2=L3=27n, C1=C3=6.8p, C2=7.5p, L5=L7=100n, L6=220n 기본 템플릿을 불러옵니다.")
        btn_template.setStyleSheet("background-color: #2b3d56; color: #ffffff; padding: 6px 12px; font-weight: bold; border-radius: 4px;")

        def _load_template():
            tmpl = self.engine.get_default_netlist_template()
            txt_edit.setPlainText(tmpl)

        btn_template.clicked.connect(_load_template)
        btn_box.addWidget(btn_template)

        # [ 📋 클립보드 복사 ]
        btn_copy = QtWidgets.QPushButton("📋 복사")
        btn_copy.setStyleSheet("background-color: #3b3b4d; color: #ffffff; padding: 6px 10px; border-radius: 4px;")
        btn_copy.clicked.connect(lambda: (
            QtWidgets.QApplication.clipboard().setText(txt_edit.toPlainText()),
            QtWidgets.QMessageBox.information(dlg, "복사 완료", "현재 넷리스트가 클립보드에 복사되었습니다.")
        ))
        btn_box.addWidget(btn_copy)

        btn_box.addStretch()

        # [ ⚡ 회로도 및 시뮬레이션 적용 ]
        btn_apply = QtWidgets.QPushButton("⚡ 회로도 및 시뮬레이션 적용")
        btn_apply.setStyleSheet("background-color: #00aa55; color: #ffffff; font-weight: bold; padding: 6px 14px; border-radius: 4px;")

        def _apply_netlist():
            input_text = txt_edit.toPlainText()
            # 이전 상태 안전 백업
            backup_components = dict(self.engine.components)
            backup_esr = dict(self.engine.esr_values)
            backup_spice = {k: dict(v) for k, v in self.engine.spice_models.items()}

            success, msg = self.engine.apply_and_validate_netlist(input_text)
            if not success:
                # 에러 발생 시 이전 상태로 복원
                self.engine.components = backup_components
                self.engine.esr_values = backup_esr
                self.engine.spice_models = backup_spice
                QtWidgets.QMessageBox.critical(
                    dlg,
                    "넷리스트 로직 검증 실패 (이전 상태 복원)",
                    f"입력한 넷리스트에 오류가 발생하여 이전 상태로 복원되었습니다:\n\n{msg}"
                )
                return

            # 검증 성공 -> 회로도 및 속성 패널 갱신 (커스텀 넷리스트는 NGSpice로 해석)
            self.schematic_widget.set_ngspice_checked(True)
            self.schematic_widget.update_components(
                self.engine.components, self.engine.spice_models,
                self.engine.component_nodes, self.engine.comp_types
            )
            self.property_panel.update_component_dict(
                self.engine.components, self.engine.esr_values, self.engine.comp_types
            )

            # 시뮬레이션 재실행
            self._run_simulation()

            QtWidgets.QMessageBox.information(
                dlg,
                "넷리스트 적용 완료",
                "SPICE 넷리스트가 성공적으로 검증되어 회로도와 시뮬레이션에 반영되었습니다."
            )
            dlg.accept()

        btn_apply.clicked.connect(_apply_netlist)
        btn_box.addWidget(btn_apply)

        # [ 닫기 ]
        btn_close = QtWidgets.QPushButton("닫기")
        btn_close.setStyleSheet("background-color: #444455; color: #ffffff; padding: 6px 12px; border-radius: 4px;")
        btn_close.clicked.connect(dlg.reject)
        btn_box.addWidget(btn_close)

        dlg_layout.addLayout(btn_box)
        dlg.exec()

    def _update_ngspice_availability(self):
        """NGSpice 실행 파일의 설치/가용 여부를 확인하고 UI(체크박스, 상태바)에 반영합니다."""
        is_avail = self.engine.is_ngspice_available()
        self.schematic_widget.set_ngspice_available(is_avail)

        if not is_avail:
            # ngspice가 없으면 강제로 ABCD 모드로 전환
            self.engine.sys_params['use_ngspice'] = False
            self.statusBar().showMessage(
                "ngspice 실행 파일을 찾을 수 없어 NGSpice 시뮬레이션이 비활성화되었습니다. "
                "상단 [설정] 버튼에서 경로를 지정하세요.",
                8000
            )
        else:
            source = getattr(self.engine, 'ngspice_detected_source', '')
            source_txt = f" ({source})" if source else ""
            self.statusBar().showMessage(
                f"NGSpice 준비 완료: {self.engine.ngspice_path}{source_txt}",
                5000
            )

    def _show_settings_dialog(self):
        """NGSpice 실행 경로 및 프로그램 환경 설정을 지정하는 다이얼로그 표시"""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("프로그램 환경 설정 (Settings)")
        dlg.resize(680, 420)
        dlg.setMinimumWidth(550)

        dlg_layout = QtWidgets.QVBoxLayout(dlg)
        dlg_layout.setSpacing(12)

        # 1. NGSpice 경로 설정 그룹박스
        group_ngspice = QtWidgets.QGroupBox("  NGSpice 시뮬레이션 엔진 설정  ")
        group_ngspice.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #3d3d56;
                border-radius: 6px;
                margin-top: 20px;
                padding-top: 18px;
                padding-bottom: 10px;
                padding-left: 10px;
                padding-right: 10px;
                background-color: #161622;
                color: #e0e0e0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 6px;
                color: #00ffff;
            }
        """)
        grp_layout = QtWidgets.QVBoxLayout(group_ngspice)
        grp_layout.setSpacing(8)

        lbl_desc = QtWidgets.QLabel(
            "<span style='color:#e2e8f0; font-size:12px;'>SPICE 시뮬레이션에 사용할 <b>ngspice.exe</b> 또는 <b>ngspice_con.exe</b>의 전체 경로를 지정합니다.</span><br>"
            "<span style='color:#94a3b8; font-size:11px;'>"
            "자동 탐색 우선순위: <b>1. 실행 파일 폴더 (.\\) → 2. .\\ngspice\\bin → 3. .\\ngspice\\Spice64\\bin → 4. 시스템 환경변수(PATH)</b>"
            "</span>"
        )
        lbl_desc.setWordWrap(True)
        grp_layout.addWidget(lbl_desc)


        # 경로 입력창 + 찾아보기 버튼
        path_box = QtWidgets.QHBoxLayout()
        txt_path = QtWidgets.QLineEdit()
        txt_path.setPlaceholderText("ngspice.exe 실행 파일 전체 경로 입력 또는 [찾아보기] 선택...")
        txt_path.setText(self.engine.ngspice_path or "")
        txt_path.setStyleSheet("""
            QLineEdit {
                background-color: #0d1117;
                color: #58a6ff;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 6px 8px;
                font-family: Consolas, monospace;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #00ffff;
            }
        """)
        path_box.addWidget(txt_path, stretch=1)

        btn_browse = QtWidgets.QPushButton("찾아보기...")
        btn_browse.setStyleSheet("background-color: #2b2b3d; color: #ffffff; border: 1px solid #44445c; border-radius: 4px; padding: 6px 12px; font-weight: bold;")

        def _on_browse():
            cur_p = txt_path.text().strip()
            init_dir = os.path.dirname(cur_p) if cur_p and os.path.exists(os.path.dirname(cur_p)) else ce.get_app_base_dir()
            fname, _ = QtWidgets.QFileDialog.getOpenFileName(
                dlg,
                "ngspice 실행 파일 선택 (ngspice.exe / ngspice_con.exe)",
                init_dir,
                "실행 파일 (*.exe);;모든 파일 (*.*)"
            )
            if fname:
                txt_path.setText(os.path.abspath(fname))
                _on_test()

        btn_browse.clicked.connect(_on_browse)
        path_box.addWidget(btn_browse)
        grp_layout.addLayout(path_box)

        # 버튼 행: [경로 테스트] & [자동 재탐색]
        btn_action_box = QtWidgets.QHBoxLayout()
        btn_test = QtWidgets.QPushButton("경로 테스트 및 버전 확인")
        btn_test.setStyleSheet("background-color: #1e3a2b; color: #00ff66; border: 1px solid #00aa44; border-radius: 4px; padding: 5px 10px; font-weight: bold;")

        btn_auto = QtWidgets.QPushButton("기본 우선순위로 자동 재탐색")
        btn_auto.setStyleSheet("background-color: #2a2a3c; color: #00ffff; border: 1px solid #0088aa; border-radius: 4px; padding: 5px 10px;")

        btn_action_box.addWidget(btn_test)
        btn_action_box.addWidget(btn_auto)
        btn_action_box.addStretch()
        grp_layout.addLayout(btn_action_box)

        # 상태 안내 레이블
        lbl_status = QtWidgets.QLabel()
        lbl_status.setWordWrap(True)
        lbl_status.setStyleSheet("padding: 4px 6px; border-radius: 4px;")

        def _update_status_display(valid: bool, msg: str):
            if valid:
                lbl_status.setText(f"<b style='color:#00ff66;'>● [정상 인식]</b> {msg}")
                lbl_status.setStyleSheet("background-color: #0b2216; border: 1px solid #00aa44; border-radius: 4px; padding: 6px;")
            else:
                lbl_status.setText(f"<b style='color:#ff5555;'>● [비활성화]</b> {msg}")
                lbl_status.setStyleSheet("background-color: #2b1116; border: 1px solid #aa2233; border-radius: 4px; padding: 6px;")

        def _on_test():
            target = txt_path.text().strip()
            if not target:
                _update_status_display(False, "경로가 비어 있습니다. ngspice 실행 파일을 지정하지 않으면 NGSpice 시뮬레이션이 비활성화됩니다.")
                return False

            if not os.path.isfile(target):
                _update_status_display(False, f"지정한 파일이 존재하지 않습니다: {target}")
                return False

            import tempfile
            test_cir = None
            try:
                # 1. 버전 문자열 추출 시도 (ngspice_con.exe가 동일 폴더에 있거나 대상 파일인 경우)
                version_str = ""
                con_candidate = os.path.join(os.path.dirname(target), "ngspice_con.exe") if os.path.basename(target).lower() != "ngspice_con.exe" else target
                if os.path.isfile(con_candidate):
                    try:
                        v_res = subprocess.run([con_candidate, '-v'], capture_output=True, text=True, timeout=2)
                        for line in (v_res.stdout or "").splitlines():
                            if 'ngspice' in line.lower():
                                version_str = line.strip().strip('*').strip()
                                break
                    except Exception:
                        pass

                # 2. 대상 실행 파일 자체를 배치(-b) 모드로 안전 검증 (종료 명령 포함 넷리스트)
                with tempfile.NamedTemporaryFile(mode='w', suffix='.cir', delete=False, encoding='utf-8') as tf:
                    tf.write("* Test Circuit\n.control\nquit\n.endc\n.end\n")
                    test_cir = tf.name

                res = subprocess.run([target, '-b', test_cir], capture_output=True, text=True, timeout=3)
                if res.returncode == 0 or version_str:
                    first_line = version_str if version_str else f"ngspice 실행 검증 완료 ({os.path.basename(target)})"
                    _update_status_display(True, f"성공적으로 실행됨: <b>{first_line}</b>")
                    return True
                else:
                    _update_status_display(False, f"실행 오류 (리턴코드: {res.returncode})")
                    return False
            except Exception as e:
                _update_status_display(False, f"실행 중 오류 발생: {e}")
                return False
            finally:
                if test_cir and os.path.exists(test_cir):
                    try:
                        os.remove(test_cir)
                    except Exception:
                        pass

        def _on_auto_detect():
            found_p, source = self.engine.redetect_ngspice()
            if found_p:
                txt_path.setText(found_p)
                _on_test()
            else:
                txt_path.setText("")
                _update_status_display(False, "1~4단계 우선순위 경로 및 시스템 PATH에서 ngspice 실행 파일을 찾지 못했습니다.")


        btn_test.clicked.connect(_on_test)
        btn_auto.clicked.connect(_on_auto_detect)
        grp_layout.addWidget(lbl_status)

        # 초기 상태 표시
        _on_test()

        dlg_layout.addWidget(group_ngspice)

        # 2. 설정 파일 정보 안내
        group_info = QtWidgets.QGroupBox("  환경설정 파일 (JSON)  ")
        group_info.setStyleSheet(group_ngspice.styleSheet())

        grp_info_layout = QtWidgets.QVBoxLayout(group_info)
        settings_file = ce.get_settings_file_path()
        lbl_file = QtWidgets.QLabel(f"<span style='color:#cbd5e1; font-size:11px;'>설정 파일 저장 경로:</span><br><span style='color:#00ffff; font-family:Consolas; font-size:11px;'>{settings_file}</span>")

        lbl_file.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        grp_info_layout.addWidget(lbl_file)
        dlg_layout.addWidget(group_info)

        # 3. 하단 다이얼로그 버튼 (저장 및 적용, 취소)
        dlg_layout.addStretch()
        btn_box = QtWidgets.QHBoxLayout()
        btn_save = QtWidgets.QPushButton("저장 및 적용")
        btn_save.setStyleSheet("background-color: #00aa66; color: #ffffff; padding: 7px 18px; border-radius: 4px; font-weight: bold;")

        btn_cancel = QtWidgets.QPushButton("취소")
        btn_cancel.setStyleSheet("background-color: #444455; color: #ffffff; padding: 7px 14px; border-radius: 4px;")

        def _on_save():
            new_path = txt_path.text().strip()
            success = self.engine.set_ngspice_path(new_path)
            self._update_ngspice_availability()

            if success:
                QtWidgets.QMessageBox.information(
                    dlg,
                    "설정 저장 완료",
                    f"ngspice 경로가 성공적으로 저장 및 적용되었습니다:\n{self.engine.ngspice_path}\n\n"
                    f"설정 파일: {settings_file}"
                )
            else:
                QtWidgets.QMessageBox.warning(
                    dlg,
                    "ngspice 비활성화 적용",
                    "유효한 ngspice 실행 파일이 지정되지 않았습니다.\n"
                    "NGSpice 시뮬레이션 기능이 비활성화되며, 고속 ABCD 해석 엔진이 사용됩니다."
                )

            # 회로 시뮬레이션 갱신
            self._run_simulation()
            dlg.accept()

        btn_save.clicked.connect(_on_save)
        btn_cancel.clicked.connect(dlg.reject)

        btn_box.addStretch()
        btn_box.addWidget(btn_save)
        btn_box.addWidget(btn_cancel)
        dlg_layout.addLayout(btn_box)

        dlg.exec()

    def _show_ngspice_log(self):
        """최근 NGSpice 실행 결과 및 콘솔 출력 로그 다이얼로그 표시"""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("NGSpice 실행 결과 및 콘솔 출력 로그")
        dlg.resize(750, 550)
        dlg_layout = QtWidgets.QVBoxLayout(dlg)

        # 정보 헤더
        info_frame = QtWidgets.QFrame()
        info_frame.setStyleSheet("background-color: #1a2233; border: 1px solid #2e4466; border-radius: 4px; padding: 6px;")
        if_layout = QtWidgets.QVBoxLayout(info_frame)
        if_layout.setSpacing(4)

        lbl_exe = QtWidgets.QLabel(f"<b>실행 파일:</b> {self.engine.ngspice_path or '미설정 (상단 [설정]에서 지정 필요)'}")
        lbl_status = QtWidgets.QLabel(f"<b>최근 실행 상태:</b> <span style='color:#00ff66;'>{self.engine.last_ngspice_status}</span>")
        if_layout.addWidget(lbl_exe)
        if_layout.addWidget(lbl_status)
        dlg_layout.addWidget(info_frame)


        # 탭 (콘솔 출력 로그 vs 넷리스트)
        tabs = QtWidgets.QTabWidget()

        # 탭 1: 콘솔 출력 로그 (STDOUT/STDERR)
        log_edit = QtWidgets.QPlainTextEdit()
        log_edit.setReadOnly(True)
        log_edit.setStyleSheet("background-color: #0d1117; color: #58a6ff; font-family: Consolas, monospace; font-size: 11px;")
        full_log = self.engine.last_ngspice_stdout
        if self.engine.last_ngspice_stderr:
            full_log += f"\n\n[STDERR 출력]\n{self.engine.last_ngspice_stderr}"
        if not full_log.strip():
            full_log = "※ 아직 NGSpice 시뮬레이션이 실행되지 않았거나 로그가 없습니다.\n회로도 상단의 'NGSpice 시뮬레이션 [ON]'을 체크하여 시뮬레이션을 실행하세요."
        log_edit.setPlainText(full_log)
        tabs.addTab(log_edit, "NGSpice 콘솔 출력 (STDOUT)")

        # 탭 2: 실제 실행된 SPICE 넷리스트
        netlist_edit = QtWidgets.QPlainTextEdit()
        netlist_edit.setReadOnly(True)
        netlist_edit.setStyleSheet("background-color: #0d1117; color: #7ee787; font-family: Consolas, monospace; font-size: 11px;")
        netlist_edit.setPlainText(self.engine.last_ngspice_netlist or "(실행된 넷리스트 없음)")
        tabs.addTab(netlist_edit, "실행에 사용된 SPICE 넷리스트")

        dlg_layout.addWidget(tabs)

        btn_row = QtWidgets.QHBoxLayout()
        btn_copy = QtWidgets.QPushButton("로그 클립보드 복사")
        btn_copy.clicked.connect(lambda: (QtWidgets.QApplication.clipboard().setText(full_log), QtWidgets.QMessageBox.information(dlg, "복사 완료", "로그가 클립보드에 복사되었습니다.")))
        btn_row.addWidget(btn_copy)

        btn_close = QtWidgets.QPushButton("닫기")
        btn_close.clicked.connect(dlg.accept)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        dlg_layout.addLayout(btn_row)

        dlg.exec()

    def _run_ngspice_verification(self):
        netlist = self.engine.generate_spice_netlist()
        cir_file = os.path.join(os.path.dirname(__file__), 'temp_verify.cir')

        try:
            with open(cir_file, 'w', encoding='utf-8') as f:
                f.write(netlist)

            cmd = [self.engine.ngspice_path, '-b', cir_file]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            QtWidgets.QMessageBox.information(
                self,
                "ngspice 검증 시뮬레이션 완료",
                f"ngspice 시뮬레이션이 성공적으로 완료되었습니다!\n\n"
                f"사용된 실행 파일:\n{self.engine.ngspice_path}\n\n"
                f"로그 미리보기:\n{result.stdout[:350]}\n..."
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "ngspice 실행 오류", f"시뮬레이션 중 오류가 발생했습니다:\n{str(e)}")
        finally:
            if os.path.exists(cir_file):
                try:
                    os.remove(cir_file)
                except Exception:
                    pass

    def _export_touchstone(self):
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Touchstone .s2p 파일 저장", "bpf_filter_simulation.s2p", "Touchstone Files (*.s2p);;All Files (*)"
        )
        if file_path:
            try:
                self.engine.export_touchstone_s2p(file_path)
                QtWidgets.QMessageBox.information(self, "저장 완료", f"파일이 성공적으로 저장되었습니다:\n{file_path}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "저장 오류", f"파일 저장 중 오류가 발생했습니다:\n{str(e)}")


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setWindowIcon(get_app_icon())

    window = BPFMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
