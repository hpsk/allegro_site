# -*- coding: utf-8 -*-
"""
하단 S-파라미터 분석기 결과 그래프 및 인터랙티브 프로브 위젯 (NetworkAnalyzerWidget)
- 인터랙티브 마우스 십자선 프로브 (실시간 주파수 및 Tr1~Tr4 수치 판독)
- NGSpice 결과 데이터 테이블 프로브 뷰어 지원
- X축 범위(Start/Stop) 및 X Scale (Linear / Log) 조절
- Y축 범위(Y Min/Max) 및 Y Scale (Log (dB) / Linear (Mag)) 조절
- 트레이스 선택 체크박스:
  [✓] Tr1 : S11  (노랑)
  [✓] Tr2 : S12  (연두)
  [✓] Tr3 : S21  (시안)
  [✓] Tr4 : S22  (마젠타)
"""

import warnings
import logging
warnings.filterwarnings("ignore")
logging.getLogger('matplotlib').setLevel(logging.ERROR)

from PySide6 import QtWidgets, QtCore, QtGui
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import numpy as np

matplotlib.rcParams['font.sans-serif'] = ['Malgun Gothic', '맑은 고딕', 'Segoe UI', 'DejaVu Sans']
matplotlib.rcParams['font.monospace'] = ['Consolas', 'Courier New', 'DejaVu Sans Mono']
matplotlib.rcParams['axes.unicode_minus'] = False


class ProbeDataDialog(QtWidgets.QDialog):
    """
    ngspice / 해석 시뮬레이션 결과의 전 주파수 데이터 테이블 프로브 다이얼로그
    """

    point_selected = QtCore.Signal(float)

    def __init__(self, sim_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("시뮬레이션 결과 데이터 프로브 테이블")
        self.resize(750, 500)
        self.sim_data = sim_data

        layout = QtWidgets.QVBoxLayout(self)

        # 상단 검색 필터 바
        search_layout = QtWidgets.QHBoxLayout()
        search_layout.addWidget(QtWidgets.QLabel("주파수 탐색 (MHz):"))
        self.edit_search = QtWidgets.QLineEdit()
        self.edit_search.setPlaceholderText("예: 210.0")
        self.edit_search.textChanged.connect(self._filter_table)
        search_layout.addWidget(self.edit_search)

        eng_name = self.sim_data.get('engine_type', '')
        if eng_name:
            is_ng = 'NGSpice' in eng_name
            color = '#00ff66' if is_ng else '#00e5ff'
            lbl_eng = QtWidgets.QLabel(f"해석 엔진: {eng_name}")
            lbl_eng.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 11px; padding: 2px 8px; border: 1px solid {color}; border-radius: 3px;")
            search_layout.addWidget(lbl_eng)

        btn_copy = QtWidgets.QPushButton("전체 데이터 클립보드 복사")
        btn_copy.clicked.connect(self._copy_clipboard)
        search_layout.addWidget(btn_copy)

        btn_csv = QtWidgets.QPushButton("💾 CSV 파일로 저장")
        btn_csv.clicked.connect(self._save_csv)
        search_layout.addWidget(btn_csv)
        layout.addLayout(search_layout)

        # 테이블
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Freq (MHz)", "S11 (dB)", "S12 (dB)", "S21 (dB)", "S22 (dB)",
            "|S11|", "|S12|", "|S21|", "|S22|"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table)

        self._populate_table()

    def _populate_table(self):
        if not self.sim_data:
            return
        freq_mhz = self.sim_data['freq'] / 1e6
        s11_db = self.sim_data['s11_db']
        s12_db = self.sim_data['s12_db']
        s21_db = self.sim_data['s21_db']
        s22_db = self.sim_data['s22_db']

        s11_mag = self.sim_data.get('s11_mag', 10.0 ** (s11_db / 20.0))
        s12_mag = self.sim_data.get('s12_mag', 10.0 ** (s12_db / 20.0))
        s21_mag = self.sim_data.get('s21_mag', 10.0 ** (s21_db / 20.0))
        s22_mag = self.sim_data.get('s22_mag', 10.0 ** (s22_db / 20.0))

        n = len(freq_mhz)
        self.table.setRowCount(n)

        for i in range(n):
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(f"{freq_mhz[i]:.4f}"))
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"{s11_db[i]:.3f}"))
            self.table.setItem(i, 2, QtWidgets.QTableWidgetItem(f"{s12_db[i]:.3f}"))
            self.table.setItem(i, 3, QtWidgets.QTableWidgetItem(f"{s21_db[i]:.3f}"))
            self.table.setItem(i, 4, QtWidgets.QTableWidgetItem(f"{s22_db[i]:.3f}"))

            self.table.setItem(i, 5, QtWidgets.QTableWidgetItem(f"{s11_mag[i]:.4f}"))
            self.table.setItem(i, 6, QtWidgets.QTableWidgetItem(f"{s12_mag[i]:.4f}"))
            self.table.setItem(i, 7, QtWidgets.QTableWidgetItem(f"{s21_mag[i]:.4f}"))
            self.table.setItem(i, 8, QtWidgets.QTableWidgetItem(f"{s22_mag[i]:.4f}"))

    def _filter_table(self, query: str):
        q = query.strip()
        if not q:
            for i in range(self.table.rowCount()):
                self.table.setRowHidden(i, False)
            return
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item and q in item.text():
                self.table.setRowHidden(i, False)
            else:
                self.table.setRowHidden(i, True)

    def _on_row_double_clicked(self, row, col):
        item = self.table.item(row, 0)
        if item:
            f_val = float(item.text())
            self.point_selected.emit(f_val)
            self.accept()

    def _copy_clipboard(self):
        lines = ["Freq(MHz)\tS11(dB)\tS12(dB)\tS21(dB)\tS22(dB)"]
        for i in range(self.table.rowCount()):
            if not self.table.isRowHidden(i):
                row_txt = "\t".join(self.table.item(i, c).text() for c in range(5))
                lines.append(row_txt)
        QtWidgets.QApplication.clipboard().setText("\n".join(lines))
        QtWidgets.QMessageBox.information(self, "복사 완료", "테이블 데이터가 클립보드에 복사되었습니다.")

    def _save_csv(self):
        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "시뮬레이션 결과 CSV 저장", "simulation_results.csv", "CSV Files (*.csv);;All Files (*)"
        )
        if not filepath:
            return
        try:
            freqs = self.sim_data['freq']
            freqs_mhz = freqs / 1e6
            s11_db = self.sim_data['s11_db']
            s12_db = self.sim_data['s12_db']
            s21_db = self.sim_data['s21_db']
            s22_db = self.sim_data['s22_db']
            s11_mag = self.sim_data.get('s11_mag', 10.0 ** (s11_db / 20.0))
            s12_mag = self.sim_data.get('s12_mag', 10.0 ** (s12_db / 20.0))
            s21_mag = self.sim_data.get('s21_mag', 10.0 ** (s21_db / 20.0))
            s22_mag = self.sim_data.get('s22_mag', 10.0 ** (s22_db / 20.0))
            eng = self.sim_data.get('engine_type', '')

            with open(filepath, 'w', encoding='utf-8-sig') as f:
                f.write("Freq_Hz,Freq_MHz,S11_dB,S12_dB,S21_dB,S22_dB,S11_Mag,S12_Mag,S21_Mag,S22_Mag,Engine\n")
                for i in range(len(freqs)):
                    f.write(
                        f"{freqs[i]:.4e},{freqs_mhz[i]:.6f},"
                        f"{s11_db[i]:.4f},{s12_db[i]:.4f},{s21_db[i]:.4f},{s22_db[i]:.4f},"
                        f"{s11_mag[i]:.6f},{s12_mag[i]:.6f},{s21_mag[i]:.6f},{s22_mag[i]:.6f},"
                        f"{eng}\n"
                    )
            QtWidgets.QMessageBox.information(self, "저장 완료", f"CSV 파일이 성공적으로 저장되었습니다:\n{filepath}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "저장 실패", str(e))


class NetworkAnalyzerWidget(QtWidgets.QWidget):
    """
    S-파라미터 4-포트 (S11, S12, S21, S22) 분석 및 실시간 프로브 위젯
    """

    axis_params_changed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(380)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        # 마커 및 프로브 위치 (MHz)
        self.mkr1_freq_mhz = 210.0
        self.mkr2_freq_mhz = 235.0
        self.probe_freq_mhz = 210.0
        self.probe_active = False

        self.sim_data = None

        self._init_ui()

    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # 1. 상단 컨트롤 바
        control_frame = QtWidgets.QFrame()
        control_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a26;
                border: 1px solid #333348;
                border-radius: 4px;
                color: #e0e0e0;
            }
            QLabel {
                font-weight: bold;
                font-size: 11px;
                color: #cccccc;
            }
            QDoubleSpinBox, QSpinBox {
                background-color: #242436;
                color: #ffffff;
                border: 1px solid #444460;
                border-radius: 3px;
                padding: 2px 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QComboBox {
                background-color: #242436;
                color: #00ffff;
                border: 1px solid #444460;
                border-radius: 3px;
                padding: 2px 4px;
                font-size: 11px;
                font-weight: bold;
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
                min-height: 24px;
                padding: 3px 8px;
                color: #ffffff;
                background-color: #181826;
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
            QCheckBox {
                font-size: 11px;
                font-weight: bold;
                spacing: 4px;
            }
            QPushButton {
                background-color: #2e2e42;
                color: #79b8ff;
                border: 1px solid #444460;
                border-radius: 3px;
                padding: 3px 8px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #3e3e58;
                color: #ffffff;
            }
        """)
        top_vlayout = QtWidgets.QVBoxLayout(control_frame)
        top_vlayout.setContentsMargins(6, 4, 6, 4)
        top_vlayout.setSpacing(6)

        # 행 1: 트레이스 체크박스 + 마커 + 프로브 테이블 버튼
        row1 = QtWidgets.QHBoxLayout()
        row1.setSpacing(10)

        lbl_traces = QtWidgets.QLabel("트레이스:")
        lbl_traces.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: bold;")
        row1.addWidget(lbl_traces)

        self.chk_s11 = QtWidgets.QCheckBox("Tr1 : S11")
        self.chk_s11.setStyleSheet("QCheckBox { color: #ffff00; }")
        self.chk_s11.setChecked(True)
        self.chk_s11.toggled.connect(self.redraw_plot)
        row1.addWidget(self.chk_s11)

        self.chk_s12 = QtWidgets.QCheckBox("Tr2 : S12")
        self.chk_s12.setStyleSheet("QCheckBox { color: #00ff66; }")
        self.chk_s12.setChecked(True)
        self.chk_s12.toggled.connect(self.redraw_plot)
        row1.addWidget(self.chk_s12)

        self.chk_s21 = QtWidgets.QCheckBox("Tr3 : S21")
        self.chk_s21.setStyleSheet("QCheckBox { color: #00ffff; }")
        self.chk_s21.setChecked(True)
        self.chk_s21.toggled.connect(self.redraw_plot)
        row1.addWidget(self.chk_s21)

        self.chk_s22 = QtWidgets.QCheckBox("Tr4 : S22")
        self.chk_s22.setStyleSheet("QCheckBox { color: #ff00ff; }")
        self.chk_s22.setChecked(True)
        self.chk_s22.toggled.connect(self.redraw_plot)
        row1.addWidget(self.chk_s22)

        row1.addSpacing(10)

        lbl_m1 = QtWidgets.QLabel("Mkr 1:")
        lbl_m1.setStyleSheet("color: #00ffff;")
        row1.addWidget(lbl_m1)
        self.spin_mkr1 = QtWidgets.QDoubleSpinBox()
        self.spin_mkr1.setRange(0.001, 10000.0)
        self.spin_mkr1.setValue(self.mkr1_freq_mhz)
        self.spin_mkr1.setSuffix(" MHz")
        self.spin_mkr1.valueChanged.connect(self._on_mkr_changed)
        row1.addWidget(self.spin_mkr1)

        lbl_m2 = QtWidgets.QLabel("Mkr 2:")
        lbl_m2.setStyleSheet("color: #ff00ff;")
        row1.addWidget(lbl_m2)
        self.spin_mkr2 = QtWidgets.QDoubleSpinBox()
        self.spin_mkr2.setRange(0.001, 10000.0)
        self.spin_mkr2.setValue(self.mkr2_freq_mhz)
        self.spin_mkr2.setSuffix(" MHz")
        self.spin_mkr2.valueChanged.connect(self._on_mkr_changed)
        row1.addWidget(self.spin_mkr2)

        row1.addSpacing(10)

        # 마커(mks) 뒤 총 데이터 수 (기본값: 500)
        lbl_pts = QtWidgets.QLabel("총 데이터 수:")
        lbl_pts.setStyleSheet("color: #79b8ff; font-weight: bold;")
        row1.addWidget(lbl_pts)

        self.spin_num_points = QtWidgets.QSpinBox()
        self.spin_num_points.setRange(10, 50000)
        self.spin_num_points.setValue(500)
        self.spin_num_points.setSingleStep(50)
        self.spin_num_points.setSuffix(" pt")
        self.spin_num_points.setToolTip("시뮬레이션 주파수 스윕 총 데이터 수 (기본값: 500)")
        self.spin_num_points.valueChanged.connect(self._on_axis_range_changed)
        row1.addWidget(self.spin_num_points)

        row1.addStretch()

        # 프로브 데이터 테이블 버튼
        self.btn_probe_table = QtWidgets.QPushButton("📊 결과 데이터 프로브 테이블")
        self.btn_probe_table.setToolTip("ngspice 및 전체 해석 결과의 전 주파수 데이터 테이블을 확인하고 프로빙합니다.")
        self.btn_probe_table.clicked.connect(self._open_probe_table)
        row1.addWidget(self.btn_probe_table)

        # 결과 CSV 다운로드 버튼
        self.btn_export_csv = QtWidgets.QPushButton("💾 결과 CSV 다운로드")
        self.btn_export_csv.setStyleSheet("QPushButton { background-color: #1b3d2b; color: #7ee787; border: 1px solid #238636; } QPushButton:hover { background-color: #238636; color: #ffffff; }")
        self.btn_export_csv.setToolTip("현재 시뮬레이션 결과 파형 데이터를 CSV 파일로 저장합니다.")
        self.btn_export_csv.clicked.connect(self._export_csv)
        row1.addWidget(self.btn_export_csv)

        top_vlayout.addLayout(row1)

        # 행 2: X축 및 Y축 조절
        row2 = QtWidgets.QHBoxLayout()
        row2.setSpacing(10)

        row2.addWidget(QtWidgets.QLabel("X축:"))
        row2.addWidget(QtWidgets.QLabel("Start:"))
        self.spin_x_start = QtWidgets.QDoubleSpinBox()
        self.spin_x_start.setRange(0.001, 10000.0)
        self.spin_x_start.setValue(0.1)
        self.spin_x_start.setSuffix(" MHz")
        self.spin_x_start.valueChanged.connect(self._on_axis_range_changed)
        row2.addWidget(self.spin_x_start)

        row2.addWidget(QtWidgets.QLabel("Stop:"))
        self.spin_x_stop = QtWidgets.QDoubleSpinBox()
        self.spin_x_stop.setRange(0.01, 100000.0)
        self.spin_x_stop.setValue(500.0)
        self.spin_x_stop.setSuffix(" MHz")
        self.spin_x_stop.valueChanged.connect(self._on_axis_range_changed)
        row2.addWidget(self.spin_x_stop)

        row2.addWidget(QtWidgets.QLabel("Scale:"))
        self.combo_x_scale = QtWidgets.QComboBox()
        self.combo_x_scale.addItems(["Linear", "Log"])
        self.combo_x_scale.currentTextChanged.connect(self._on_x_scale_changed)
        row2.addWidget(self.combo_x_scale)

        row2.addSpacing(15)

        row2.addWidget(QtWidgets.QLabel("Y축:"))
        row2.addWidget(QtWidgets.QLabel("Min:"))
        self.spin_y_min = QtWidgets.QDoubleSpinBox()
        self.spin_y_min.setRange(-200.0, 100.0)
        self.spin_y_min.setValue(-50.0)
        self.spin_y_min.setSingleStep(5.0)
        self.spin_y_min.valueChanged.connect(self.redraw_plot)
        row2.addWidget(self.spin_y_min)

        row2.addWidget(QtWidgets.QLabel("Max:"))
        self.spin_y_max = QtWidgets.QDoubleSpinBox()
        self.spin_y_max.setRange(-100.0, 200.0)
        self.spin_y_max.setValue(10.0)
        self.spin_y_max.setSingleStep(5.0)
        self.spin_y_max.valueChanged.connect(self.redraw_plot)
        row2.addWidget(self.spin_y_max)

        row2.addWidget(QtWidgets.QLabel("Format:"))
        self.combo_y_scale = QtWidgets.QComboBox()
        self.combo_y_scale.addItems(["Log (dB)", "Linear (Mag)"])
        self.combo_y_scale.currentTextChanged.connect(self._on_y_scale_changed)
        row2.addWidget(self.combo_y_scale)

        row2.addStretch()
        top_vlayout.addLayout(row2)

        main_layout.addWidget(control_frame)

        # 2. 실시간 프로브 표시 바 (마우스 커서 위치 수치 판독)
        self.probe_bar = QtWidgets.QFrame()
        self.probe_bar.setStyleSheet("""
            QFrame {
                background-color: #121824;
                border: 1px solid #1f3048;
                border-radius: 3px;
                padding: 2px 8px;
            }
            QLabel {
                font-family: Consolas, monospace;
                font-size: 11.5px;
                font-weight: bold;
            }
        """)
        probe_bar_layout = QtWidgets.QHBoxLayout(self.probe_bar)
        probe_bar_layout.setContentsMargins(4, 2, 4, 2)
        self.lbl_probe_val = QtWidgets.QLabel("🎯 프로브: 그래프 위에 마우스를 올리거나 클릭하여 주파수별 정밀 수치를 확인하세요.")
        self.lbl_probe_val.setStyleSheet("color: #00ffff;")
        probe_bar_layout.addWidget(self.lbl_probe_val)
        main_layout.addWidget(self.probe_bar)

        # 3. Matplotlib Figure & Canvas
        self.fig = Figure(facecolor='#0a0a0e', edgecolor='#1e1e28', dpi=100)
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setStyleSheet("background-color: #0a0a0e; border: 1px solid #222233;")
        main_layout.addWidget(self.canvas)

        # 마우스 인터랙션 (호버 프로브 & 클릭)
        self.canvas.mpl_connect('motion_notify_event', self._on_canvas_motion)
        self.canvas.mpl_connect('button_press_event', self._on_canvas_click)

        self.ax = self.fig.add_axes([0.07, 0.12, 0.90, 0.74])
        self._setup_axes()

    def _setup_axes(self):
        self.ax.set_facecolor('#000000')
        self.ax.grid(True, which='both', color='#262626', linestyle='-', linewidth=0.8)

        is_log_x = (self.combo_x_scale.currentText() == "Log")
        if is_log_x:
            self.ax.set_xscale('log')
        else:
            self.ax.set_xscale('linear')

        x_min = max(0.001, self.spin_x_start.value())
        x_max = max(x_min + 0.001, self.spin_x_stop.value())
        self.ax.set_xlim(x_min, x_max)

        y_min = self.spin_y_min.value()
        y_max = self.spin_y_max.value()
        if y_max <= y_min:
            y_max = y_min + 1.0
        self.ax.set_ylim(y_min, y_max)

        self.ax.tick_params(colors='#888888', labelsize=9)
        for spine in self.ax.spines.values():
            spine.set_color('#444455')

        self.ax.set_xlabel("Frequency (MHz)", color='#aaaaaa', fontsize=9.5, labelpad=4)
        is_linear_y = (self.combo_y_scale.currentText().startswith("Linear"))
        y_label = "Magnitude |S| (Linear)" if is_linear_y else "Log Mag (dB)"
        self.ax.set_ylabel(y_label, color='#aaaaaa', fontsize=9.5, labelpad=4)

    def _on_x_scale_changed(self, text: str):
        self._setup_axes()
        self.axis_params_changed.emit()

    def _on_y_scale_changed(self, text: str):
        if text.startswith("Linear"):
            self.spin_y_min.setValue(0.0)
            self.spin_y_max.setValue(1.0)
            self.spin_y_min.setSingleStep(0.1)
            self.spin_y_max.setSingleStep(0.1)
        else:
            self.spin_y_min.setValue(-50.0)
            self.spin_y_max.setValue(10.0)
            self.spin_y_min.setSingleStep(5.0)
            self.spin_y_max.setSingleStep(5.0)
        self.redraw_plot()

    def _on_axis_range_changed(self):
        self.axis_params_changed.emit()

    def _on_mkr_changed(self):
        self.mkr1_freq_mhz = self.spin_mkr1.value()
        self.mkr2_freq_mhz = self.spin_mkr2.value()
        self.redraw_plot()

    def _on_canvas_motion(self, event):
        """마우스 이동 시 실시간 프로브 수치 판독 및 안내"""
        if event.inaxes != self.ax or event.xdata is None or self.sim_data is None:
            return

        f_cur = event.xdata
        self._update_probe_readout(f_cur)

    def _on_canvas_click(self, event):
        """마우스 클릭 시 프로브 위치 고정 및 마커 이동"""
        if event.inaxes != self.ax or event.xdata is None or self.sim_data is None:
            return

        click_f = event.xdata
        self.probe_freq_mhz = click_f
        self.probe_active = True
        self._update_probe_readout(click_f)

        d1 = abs(click_f - self.mkr1_freq_mhz)
        d2 = abs(click_f - self.mkr2_freq_mhz)
        if event.button == 1:
            self.spin_mkr1.setValue(click_f)
        elif event.button == 3:
            self.spin_mkr2.setValue(click_f)

    def _update_probe_readout(self, freq_mhz: float):
        """프로브 바 텍스트 갱신"""
        if self.sim_data is None:
            return

        freq_arr = self.sim_data['freq'] / 1e6
        is_linear_y = (self.combo_y_scale.currentText().startswith("Linear"))

        if is_linear_y:
            s11_arr = self.sim_data.get('s11_mag', 10.0 ** (self.sim_data['s11_db'] / 20.0))
            s12_arr = self.sim_data.get('s12_mag', 10.0 ** (self.sim_data['s12_db'] / 20.0))
            s21_arr = self.sim_data.get('s21_mag', 10.0 ** (self.sim_data['s21_db'] / 20.0))
            s22_arr = self.sim_data.get('s22_mag', 10.0 ** (self.sim_data['s22_db'] / 20.0))
            fmt = lambda v: f"{v:6.4f}"
        else:
            s11_arr = self.sim_data['s11_db']
            s12_arr = self.sim_data['s12_db']
            s21_arr = self.sim_data['s21_db']
            s22_arr = self.sim_data['s22_db']
            fmt = lambda v: f"{v:6.2f} dB"

        p_s11 = float(np.interp(freq_mhz, freq_arr, s11_arr))
        p_s12 = float(np.interp(freq_mhz, freq_arr, s12_arr))
        p_s21 = float(np.interp(freq_mhz, freq_arr, s21_arr))
        p_s22 = float(np.interp(freq_mhz, freq_arr, s22_arr))

        t1 = f"Tr1(S11): <span style='color:#ffff00;'>{fmt(p_s11)}</span>" if self.chk_s11.isChecked() else ""
        t2 = f"Tr2(S12): <span style='color:#00ff66;'>{fmt(p_s12)}</span>" if self.chk_s12.isChecked() else ""
        t3 = f"Tr3(S21): <span style='color:#00ffff;'>{fmt(p_s21)}</span>" if self.chk_s21.isChecked() else ""
        t4 = f"Tr4(S22): <span style='color:#ff00ff;'>{fmt(p_s22)}</span>" if self.chk_s22.isChecked() else ""

        traces = " &nbsp;|&nbsp; ".join([t for t in [t1, t2, t3, t4] if t])
        eng = self.sim_data.get('engine_type', 'Engine')
        is_ng = 'NGSpice' in eng
        eng_color = '#00ff66' if is_ng else '#00e5ff'
        sim_t = self.sim_data.get('sim_time', '')
        t_info = f" ({sim_t})" if sim_t else ""
        txt = f"🎯 <b>프로브</b> [ <b>{freq_mhz:8.3f} MHz</b> ] &nbsp;&nbsp; {traces} &nbsp;&nbsp; <span style='color:{eng_color}; font-weight:bold;'>[{eng}{t_info}]</span>"
        self.lbl_probe_val.setText(txt)

    def _open_probe_table(self):
        """ngspice/해석 데이터 프로브 테이블 다이얼로그 열기"""
        if not self.sim_data:
            QtWidgets.QMessageBox.information(self, "데이터 없음", "현재 표시할 시뮬레이션 결과 데이터가 없습니다.")
            return

        dlg = ProbeDataDialog(self.sim_data, self)
        dlg.point_selected.connect(lambda f: self.spin_mkr1.setValue(f))
        dlg.exec()

    def _export_csv(self):
        """현재 시뮬레이션 결과 데이터를 CSV 파일로 저장"""
        if not self.sim_data:
            QtWidgets.QMessageBox.information(self, "데이터 없음", "저장할 시뮬레이션 결과 데이터가 없습니다.")
            return

        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "시뮬레이션 결과 CSV 저장", "bpf_simulation_results.csv", "CSV Files (*.csv);;All Files (*)"
        )
        if not filepath:
            return

        try:
            freqs = self.sim_data['freq']
            freqs_mhz = freqs / 1e6
            s11_db = self.sim_data['s11_db']
            s12_db = self.sim_data['s12_db']
            s21_db = self.sim_data['s21_db']
            s22_db = self.sim_data['s22_db']
            s11_mag = self.sim_data.get('s11_mag', 10.0 ** (s11_db / 20.0))
            s12_mag = self.sim_data.get('s12_mag', 10.0 ** (s12_db / 20.0))
            s21_mag = self.sim_data.get('s21_mag', 10.0 ** (s21_db / 20.0))
            s22_mag = self.sim_data.get('s22_mag', 10.0 ** (s22_db / 20.0))
            eng = self.sim_data.get('engine_type', '')

            with open(filepath, 'w', encoding='utf-8-sig') as f:
                f.write("Freq_Hz,Freq_MHz,S11_dB,S12_dB,S21_dB,S22_dB,S11_Mag,S12_Mag,S21_Mag,S22_Mag,Engine\n")
                for i in range(len(freqs)):
                    f.write(
                        f"{freqs[i]:.4e},{freqs_mhz[i]:.6f},"
                        f"{s11_db[i]:.4f},{s12_db[i]:.4f},{s21_db[i]:.4f},{s22_db[i]:.4f},"
                        f"{s11_mag[i]:.6f},{s12_mag[i]:.6f},{s21_mag[i]:.6f},{s22_mag[i]:.6f},"
                        f"{eng}\n"
                    )
            QtWidgets.QMessageBox.information(self, "저장 완료", f"CSV 파일이 성공적으로 저장되었습니다:\n{filepath}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "저장 실패", f"CSV 저장 중 오류가 발생했습니다: {e}")

    def get_axis_params(self) -> dict:
        return {
            'start_freq': max(1e3, self.spin_x_start.value() * 1e6),
            'stop_freq': max(1e4, self.spin_x_stop.value() * 1e6),
            'num_points': int(self.spin_num_points.value()),
            'x_scale': self.combo_x_scale.currentText(),
            'y_scale': self.combo_y_scale.currentText(),
        }

    def update_simulation_data(self, sim_data: dict):
        self.sim_data = sim_data
        self.redraw_plot()
        if self.probe_active:
            self._update_probe_readout(self.probe_freq_mhz)
        else:
            self._update_probe_readout(self.mkr1_freq_mhz)

    def redraw_plot(self):
        self.ax.clear()
        self._setup_axes()

        if self.sim_data is None:
            self.canvas.draw_idle()
            return

        freq_mhz = self.sim_data['freq'] / 1e6
        is_linear_y = (self.combo_y_scale.currentText().startswith("Linear"))

        if is_linear_y:
            s11 = self.sim_data.get('s11_mag', 10.0 ** (self.sim_data['s11_db'] / 20.0))
            s12 = self.sim_data.get('s12_mag', 10.0 ** (self.sim_data['s12_db'] / 20.0))
            s21 = self.sim_data.get('s21_mag', 10.0 ** (self.sim_data['s21_db'] / 20.0))
            s22 = self.sim_data.get('s22_mag', 10.0 ** (self.sim_data['s22_db'] / 20.0))
            ref_val = 1.0
            unit_str = ""
        else:
            s11 = self.sim_data['s11_db']
            s12 = self.sim_data['s12_db']
            s21 = self.sim_data['s21_db']
            s22 = self.sim_data['s22_db']
            ref_val = 0.0
            unit_str = " dB"

        self.ax.axhline(ref_val, color='#555566', linestyle='--', linewidth=0.8, alpha=0.7)

        # 트레이스 선
        if self.chk_s11.isChecked():
            self.ax.plot(freq_mhz, s11, color='#ffff00', linewidth=1.8, label='Tr1:S11')
        if self.chk_s12.isChecked():
            self.ax.plot(freq_mhz, s12, color='#00ff66', linewidth=1.8, label='Tr2:S12')
        if self.chk_s21.isChecked():
            self.ax.plot(freq_mhz, s21, color='#00ffff', linewidth=2.0, label='Tr3:S21')
        if self.chk_s22.isChecked():
            self.ax.plot(freq_mhz, s22, color='#ff00ff', linewidth=1.8, label='Tr4:S22')

        # 마커 계산
        m1_f = self.mkr1_freq_mhz
        m2_f = self.mkr2_freq_mhz

        s11_m1 = float(np.interp(m1_f, freq_mhz, s11))
        s12_m1 = float(np.interp(m1_f, freq_mhz, s12))
        s21_m1 = float(np.interp(m1_f, freq_mhz, s21))
        s22_m1 = float(np.interp(m1_f, freq_mhz, s22))

        s11_m2 = float(np.interp(m2_f, freq_mhz, s11))
        s12_m2 = float(np.interp(m2_f, freq_mhz, s12))
        s21_m2 = float(np.interp(m2_f, freq_mhz, s21))
        s22_m2 = float(np.interp(m2_f, freq_mhz, s22))

        # 마커 수직선 및 포인트
        self.ax.axvline(m1_f, color='#00e5ff', linestyle=':', linewidth=1.0, alpha=0.8)
        self.ax.axvline(m2_f, color='#ff00e5', linestyle=':', linewidth=1.0, alpha=0.8)

        if self.chk_s21.isChecked():
            self.ax.plot([m1_f], [s21_m1], marker='v', markersize=7, color='#00ffff')
            self.ax.plot([m2_f], [s21_m2], marker='v', markersize=7, color='#00ffff')
        if self.chk_s11.isChecked():
            self.ax.plot([m1_f], [s11_m1], marker='^', markersize=6, color='#ffff00')
            self.ax.plot([m2_f], [s11_m2], marker='^', markersize=6, color='#ffff00')
        if self.chk_s12.isChecked():
            self.ax.plot([m1_f], [s12_m1], marker='o', markersize=5, color='#00ff66')
            self.ax.plot([m2_f], [s12_m2], marker='o', markersize=5, color='#00ff66')
        if self.chk_s22.isChecked():
            self.ax.plot([m1_f], [s22_m1], marker='^', markersize=6, color='#ff00ff')
            self.ax.plot([m2_f], [s22_m2], marker='^', markersize=6, color='#ff00ff')

        # 프로브 고정 위치가 있으면 보라색 점선 및 다이아몬드 포인트 표시
        if self.probe_active:
            pf = self.probe_freq_mhz
            self.ax.axvline(pf, color='#ffaa00', linestyle='--', linewidth=1.2, alpha=0.85)
            p_s21 = float(np.interp(pf, freq_mhz, s21))
            self.ax.plot([pf], [p_s21], marker='D', markersize=6, color='#ffaa00')

        # 상단 텍스트 오버레이: 해석 엔진 배지 및 마커 판독 박스
        self.fig.texts.clear()
        eng_name = self.sim_data.get('engine_type', 'ABCD Matrix')
        is_ng = 'NGSpice' in eng_name
        if is_ng:
            badge_color = '#00ff66'   # 선명한 형광 녹색
            badge_bg = '#062612'
            sim_t = self.sim_data.get('sim_time', '')
            t_info = f" | {sim_t}" if sim_t else ""
            badge_text = f"● Engine: {eng_name}{t_info} ({len(freq_mhz)}pt)"
        else:
            badge_color = '#00e5ff'   # 시안색
            badge_bg = '#061c28'
            badge_text = f"● Engine: {eng_name} ({len(freq_mhz)}pt)"

        self.fig.text(0.07, 0.942, badge_text, color=badge_color, fontsize=9.5, family='sans-serif', weight='bold',
                      bbox=dict(boxstyle='round,pad=0.4', facecolor=badge_bg, edgecolor=badge_color, linewidth=1.2))

        m1_s11_txt = f"S11:{s11_m1:6.2f}{unit_str}" if self.chk_s11.isChecked() else "S11: OFF"
        m1_s12_txt = f"S12:{s12_m1:6.2f}{unit_str}" if self.chk_s12.isChecked() else "S12: OFF"
        m1_s21_txt = f"S21:{s21_m1:6.2f}{unit_str}" if self.chk_s21.isChecked() else "S21: OFF"
        m1_s22_txt = f"S22:{s22_m1:6.2f}{unit_str}" if self.chk_s22.isChecked() else "S22: OFF"

        m2_s11_txt = f"S11:{s11_m2:6.2f}{unit_str}" if self.chk_s11.isChecked() else "S11: OFF"
        m2_s12_txt = f"S12:{s12_m2:6.2f}{unit_str}" if self.chk_s12.isChecked() else "S12: OFF"
        m2_s21_txt = f"S21:{s21_m2:6.2f}{unit_str}" if self.chk_s21.isChecked() else "S21: OFF"
        m2_s22_txt = f"S22:{s22_m2:6.2f}{unit_str}" if self.chk_s22.isChecked() else "S22: OFF"

        mkr_text = (
            f" 1  {m1_f:8.3f} MHz | {m1_s11_txt} | {m1_s12_txt} | {m1_s21_txt} | {m1_s22_txt}\n"
            f" 2  {m2_f:8.3f} MHz | {m2_s11_txt} | {m2_s12_txt} | {m2_s21_txt} | {m2_s22_txt}"
        )
        self.fig.text(0.31, 0.925, mkr_text, color='#ffffff', fontsize=8.5, family='monospace',
                      bbox=dict(boxstyle='square,pad=0.35', facecolor='#11111a', edgecolor='#333348', alpha=0.9))

        self.canvas.draw_idle()
