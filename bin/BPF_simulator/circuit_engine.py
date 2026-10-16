# -*- coding: utf-8 -*-
"""
BPF 회로 전송행렬(ABCD Matrix) 및 NGSpice 연동 시뮬레이션 엔진
- 부품별 개별 ESR (등가 직렬 저항) 완벽 지원 (인덕터 및 커패시터 개별 적용)
- "R이 0이면 R은 1p (1e-12 Ω)로 시뮬레이션" 규칙 적용
- 2-Port ABCD 고속 해석 및 NGSpice 공식 S-parameter 시뮬레이션 (.SUBCKT 서브서킷 완벽 지원)
- Tr1: S11, Tr2: S12, Tr3: S21, Tr4: S22 계산
- Log (dB) 및 Linear Magnitude 지원
"""

import os
import sys
import re
import subprocess
import tempfile
import time
import json
import shutil
import logging
import numpy as np
import rlc_standards as rlc

# 설정 파일 이름 정의 (exe 파일과 동일 디렉토리의 settings.json)
SETTINGS_FILE_NAME = "settings.json"


def get_app_base_dir() -> str:
    """
    실행 파일(exe) 또는 파이썬 메인 스크립트가 위치한 기준 디렉토리를 반환합니다.
    PyInstaller 패키징 환경(sys.frozen) 및 개발 환경 모두 지원합니다.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_settings_file_path() -> str:
    """설정 파일(settings.json)의 전체 절대 경로를 반환합니다."""
    return os.path.join(get_app_base_dir(), SETTINGS_FILE_NAME)


def load_settings() -> dict:
    """settings.json 설정 파일을 UTF-8로 읽어 반환합니다. 없을 경우 빈 딕셔너리를 반환합니다."""
    path = get_settings_file_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f"settings.json 로드 실패: {e}")
            return {}
    return {}


def save_settings(settings: dict):
    """설정 딕셔너리를 settings.json 파일에 UTF-8 포맷으로 안전하게 저장합니다."""
    path = get_settings_file_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"settings.json 저장 실패: {e}")


def find_ngspice_executable(custom_path: str = None) -> tuple[str, str]:
    """
    ngspice 실행 파일(ngspice.exe / ngspice_con.exe) 경로를 사용자 지정 우선순위에 따라 탐색합니다.
    우선순위 규격:
      0. 사용자 직접 지정 경로 또는 settings.json에 저장된 유효 경로
      1. .\\ 같은 경로 (exe 실행 파일 폴더)
      2. .\\ngspice\\bin
      3. .\\ngspice\\Spice64\\bin
      4. 시스템 환경변수 (PATH)
    위 순서대로 확인하고 없으면 빈 문자열("")과 '미발견'을 반환합니다.

    반환:
      tuple[str, str]: (실행 파일 절대경로, 감지 위치 설명)
    """
    # 0-1. 인자로 전달된 직접 경로 검사
    if custom_path and os.path.isfile(custom_path):
        return os.path.abspath(custom_path), "사용자 직접 지정"

    # 0-2. settings.json에 기존 저장된 경로 검사
    cfg = load_settings()
    saved_path = cfg.get('ngspice_path', '').strip()
    if saved_path and os.path.isfile(saved_path):
        return os.path.abspath(saved_path), "설정 파일(settings.json)"

    base_dir = get_app_base_dir()
    # Windows 실행 파일 이름 후보 (콘솔 출력 캡처에 최적화된 ngspice_con.exe 우선)
    candidate_names = ['ngspice_con.exe', 'ngspice.exe', 'ngspice']


    # 1. .\\ 같은 경로 (exe 실행 파일 폴더)
    for name in candidate_names:
        p = os.path.join(base_dir, name)
        if os.path.isfile(p):
            return os.path.abspath(p), "실행 파일 폴더 (.\\)"

    # 2. .\\ngspice\\bin
    dir_step2 = os.path.join(base_dir, 'ngspice', 'bin')
    for name in candidate_names:
        p = os.path.join(dir_step2, name)
        if os.path.isfile(p):
            return os.path.abspath(p), "ngspice bin 폴더 (.\\ngspice\\bin)"

    # 3. .\\ngspice\\Spice64\\bin
    dir_step3 = os.path.join(base_dir, 'ngspice', 'Spice64', 'bin')
    for name in candidate_names:
        p = os.path.join(dir_step3, name)
        if os.path.isfile(p):
            return os.path.abspath(p), "ngspice Spice64 bin 폴더 (.\\ngspice\\Spice64\\bin)"

    # 4. PATH 환경변수에 설정되어 있는지 확인
    for name in candidate_names:
        which_p = shutil.which(name)
        if which_p and os.path.isfile(which_p):
            return os.path.abspath(which_p), "시스템 환경변수 (PATH)"

    # 위 순서대로 확인하였으나 없는 경우
    return "", "미발견"


# 기본 BPF 설계 소자값 (사용자 지정 표준 기본값)
# L1, L4: 22nH | L2, L3: 27nH | C1, C3: 6.8pF | C2: 7.5pF | L5, L7: 100nH | L6: 220nH
DEFAULT_COMPONENTS = {
    'L1': 22e-9,    # 직렬 1: 22 nH
    'L2': 27e-9,    # 직렬 2: 27 nH
    'L3': 27e-9,    # 직렬 3: 27 nH
    'L4': 22e-9,    # 직렬 4: 22 nH
    'L5': 100e-9,   # 병렬 1 인덕터: 100 nH
    'C1': 6.8e-12,  # 병렬 1 커패시터: 6.8 pF
    'L6': 220e-9,   # 병렬 2 인덕터: 220 nH
    'C2': 7.5e-12,  # 병렬 2 커패시터: 7.5 pF
    'L7': 100e-9,   # 병렬 3 인덕터: 100 nH
    'C3': 6.8e-12,  # 병렬 3 커패시터: 6.8 pF
}

# 기본 부품별 개별 ESR (등가 직렬 저항, 단위: Ω)
DEFAULT_ESR = {
    'L1': 0.35,  # 직렬 인덕터 기본 ESR: 0.35 Ω
    'L2': 0.35,
    'L3': 0.35,
    'L4': 0.35,
    'L5': 0.35,  # 병렬 인덕터 기본 ESR: 0.35 Ω
    'L6': 0.35,
    'L7': 0.35,
    'C1': 0.05,  # 커패시터 기본 ESR: 0.05 Ω
    'C2': 0.05,
    'C3': 0.05,
}

# 회로 소자별 연결 노드 정의 (핀1, 핀2 자동 매핑)
COMPONENT_NODES = {
    'L1': ('in', 'n1'),
    'L5': ('n1', '0'),
    'C1': ('n1', '0'),
    'L2': ('n1', 'n2'),
    'L6': ('n2', '0'),
    'C2': ('n2', '0'),
    'L3': ('n2', 'n3'),
    'L7': ('n3', '0'),
    'C3': ('n3', '0'),
    'L4': ('n3', 'out'),
}

# 기본 시스템 파라미터
DEFAULT_SYS_PARAMS = {
    'Z0': 50.0,            # 포트 임피던스 (50 Ω)
    'start_freq': 100e3,   # 시작 주파수 (100 kHz)
    'stop_freq': 500e6,    # 종료 주파수 (500 MHz)
    'num_points': 500,     # 주파수 포인트 수
    'use_ngspice': False,  # NGSpice 사용 여부
}


def sanitize_resistance(r_val: float) -> float:
    """
    R이 0이거나 0 이하이면 1p (1e-12 ohm)으로 치환합니다.
    (사용자 규칙: 'R이 0이면 R은 1p로 시뮬레이션해줘')
    """
    if r_val <= 0.0 or abs(r_val) < 1e-15:
        return 1e-12  # 1 p-ohm
    return float(r_val)


def normalize_spice_netlist(netlist_text: str) -> str:
    """
    SPICE 넷리스트에서 숫자와 단위 사이의 공백을 자동 결합 정규화합니다.
    예: '22 nH' -> '22nH', '27 nH' -> '27nH', '6.8 pF' -> '6.8pF', '100 nH' -> '100nH'
    노드 0과 값 사이가 붙지 않도록 처음 3개 토큰(소자명 노드1 노드2) 이후의 값/단위만 정규화합니다.
    """
    cleaned_lines = []
    for line in netlist_text.splitlines():
        l_strip = line.strip()
        if not l_strip or l_strip.startswith('*') or l_strip.startswith('.'):
            cleaned_lines.append(line)
            continue
        parts = l_strip.split()
        if len(parts) >= 5 and parts[0][0].upper() in ('R', 'L', 'C', 'V', 'I', 'X'):
            val_cand = parts[3]
            unit_cand = parts[4]
            try:
                float(val_cand)
                is_num = True
            except ValueError:
                is_num = False

            if is_num and re.match(r'^[a-zA-Z\u03a9Ω]+$', unit_cand):
                combined = val_cand + unit_cand
                new_parts = parts[:3] + [combined] + parts[5:]
                cleaned_lines.append(" ".join(new_parts))
                continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


class CircuitEngine:
    """
    RLC 대역통과 필터(BPF) 시뮬레이션 엔진
    - 부품별 개별 ESR 반영
    - R=0 일 때 1pΩ 치환
    - 고속 ABCD 전송 행렬 해석 및 ngspice 연동 지원
    """

    def __init__(self, components: dict = None, esr_dict: dict = None, sys_params: dict = None):
        self.components = dict(DEFAULT_COMPONENTS)
        if components:
            self.components.update(components)

        # 소자별 개별 ESR 딕셔너리
        self.esr_values = dict(DEFAULT_ESR)
        if esr_dict:
            self.esr_values.update(esr_dict)

        self.sys_params = dict(DEFAULT_SYS_PARAMS)
        if sys_params:
            self.sys_params.update(sys_params)

        # 각 소자별 SPICE 서브서킷 모델 설정 저장소
        self.spice_models = {}
        for name in COMPONENT_NODES:
            self.spice_models[name] = {
                'mode': 'value',
                'text': '',
                'model_name': ''
            }

        # 소자별 노드 연결 정보 및 소자 타입(R/L/C) 매핑 저장소
        self.component_nodes = dict(COMPONENT_NODES)
        self.comp_types = {name: ('L' if name.startswith('L') else ('C' if name.startswith('C') else 'R')) for name in self.components}

        # ngspice 실행 파일 경로 및 감지 출처 초기화 (우선순위 1~4단계 자동 탐색 및 settings.json 연동)
        self.ngspice_path, self.ngspice_detected_source = find_ngspice_executable()
        if self.ngspice_path:
            cfg = load_settings()
            if cfg.get('ngspice_path') != self.ngspice_path:
                cfg['ngspice_path'] = self.ngspice_path
                save_settings(cfg)

        # NGSpice 최근 실행 기록 (디버깅 및 사용자 검증용)
        self.last_ngspice_netlist = ''
        self.last_ngspice_stdout = ''
        self.last_ngspice_stderr = ''
        self.last_ngspice_time = 0.0
        self.last_ngspice_status = '미실행'
        # 사용자가 SPICE 넷리스트 에디터를 통해 적용한 커스텀 회로 넷리스트 (소자 추가/병렬 구조 등)
        self.custom_circuit_netlist = None

    def is_ngspice_available(self) -> bool:
        """ngspice 실행 파일이 유효하게 지정되어 있고 실제 존재하는지 확인합니다."""
        if not self.ngspice_path:
            return False
        return os.path.isfile(self.ngspice_path)

    def set_ngspice_path(self, new_path: str) -> bool:
        """
        사용자가 지정한 ngspice 실행 파일 경로를 설정하고 settings.json에 영구 기록합니다.
        유효한 파일이면 True, 비어있거나 없으면 False를 반환합니다.
        """
        clean_path = (new_path or "").strip()
        cfg = load_settings()
        if clean_path and os.path.isfile(clean_path):
            self.ngspice_path = os.path.abspath(clean_path)
            self.ngspice_detected_source = "사용자 직접 지정"
            cfg['ngspice_path'] = self.ngspice_path
            save_settings(cfg)
            return True
        else:
            self.ngspice_path = ""
            self.ngspice_detected_source = "미발견"
            cfg['ngspice_path'] = ""
            save_settings(cfg)
            return False

    def redetect_ngspice(self) -> tuple[str, str]:
        """
        사용자 지정 우선순위(1. .\\ -> 2. .\\ngspice\\bin -> 3. .\\ngspice\\Spice64\\bin -> 4. PATH)에 따라
        ngspice 실행 파일을 다시 자동 탐색하고 settings.json에 저장합니다.
        """
        base_dir = get_app_base_dir()
        candidate_names = ['ngspice_con.exe', 'ngspice.exe', 'ngspice']
        found_path = ""

        source_desc = "미발견"

        # 1. .\\ 같은 경로
        for name in candidate_names:
            p = os.path.join(base_dir, name)
            if os.path.isfile(p):
                found_path, source_desc = os.path.abspath(p), "실행 파일 폴더 (.\\)"
                break

        # 2. .\\ngspice\\bin
        if not found_path:
            d2 = os.path.join(base_dir, 'ngspice', 'bin')
            for name in candidate_names:
                p = os.path.join(d2, name)
                if os.path.isfile(p):
                    found_path, source_desc = os.path.abspath(p), "ngspice bin 폴더 (.\\ngspice\\bin)"
                    break

        # 3. .\\ngspice\\Spice64\\bin
        if not found_path:
            d3 = os.path.join(base_dir, 'ngspice', 'Spice64', 'bin')
            for name in candidate_names:
                p = os.path.join(d3, name)
                if os.path.isfile(p):
                    found_path, source_desc = os.path.abspath(p), "ngspice Spice64 bin 폴더 (.\\ngspice\\Spice64\\bin)"
                    break

        # 4. PATH 환경변수
        if not found_path:
            for name in candidate_names:
                which_p = shutil.which(name)
                if which_p and os.path.isfile(which_p):
                    found_path, source_desc = os.path.abspath(which_p), "시스템 환경변수 (PATH)"
                    break

        if found_path:
            self.ngspice_path = found_path
            self.ngspice_detected_source = source_desc
            cfg = load_settings()
            cfg['ngspice_path'] = found_path
            save_settings(cfg)
        else:
            self.ngspice_path = ""
            self.ngspice_detected_source = "미발견"

        return self.ngspice_path, self.ngspice_detected_source


    def set_component(self, name: str, value: float):
        """소자의 공칭값을 설정합니다."""
        if name in self.components:
            self.components[name] = float(value)

    def get_component(self, name: str) -> float:
        """소자의 현재 공칭값을 반환합니다."""
        return self.components.get(name, 0.0)

    def set_component_esr(self, name: str, esr_value: float):
        """특정 부품의 개별 ESR(등가 직렬 저항)을 설정합니다."""
        if name in self.esr_values:
            self.esr_values[name] = float(esr_value)

    def get_component_esr(self, name: str) -> float:
        """특정 부품의 개별 ESR 값을 반환합니다."""
        return self.esr_values.get(name, 0.0)

    def set_spice_model(self, name: str, mode: str, subckt_text: str = ''):
        """
        소자의 SPICE 모델 설정
        mode: 'value' (기본 RLC 값) 또는 'subckt' (SPICE 서브서킷)
        """
        if name not in self.spice_models:
            return

        model_name = ''
        clean_text = subckt_text.strip()
        if clean_text:
            match = re.search(r"^\s*\.SUBCKT\s+(\S+)", clean_text, re.IGNORECASE | re.MULTILINE)
            if match:
                model_name = match.group(1)

        self.spice_models[name] = {
            'mode': mode,
            'text': clean_text,
            'model_name': model_name
        }

    def get_spice_model(self, name: str) -> dict:
        return self.spice_models.get(name, {'mode': 'value', 'text': '', 'model_name': ''})

    def has_any_subckt(self) -> bool:
        """하나라도 서브서킷 모델이 적용되어 있는지 확인"""
        return any(m['mode'] == 'subckt' and m['text'] for m in self.spice_models.values())

    def calculate_s_parameters(self, freqs: np.ndarray = None, x_scale: str = 'Linear') -> dict:
        """
        주파수에 따른 S11, S12, S21, S22를 계산합니다.
        use_ngspice 옵션이 True이거나 서브서킷이 지정된 경우 NGSpice로 해석합니다.
        """
        if freqs is None:
            f_start = float(self.sys_params['start_freq'])
            f_stop = float(self.sys_params['stop_freq'])
            n_pts = int(self.sys_params['num_points'])
            if x_scale.lower() == 'log':
                freqs = np.logspace(np.log10(max(1.0, f_start)), np.log10(f_stop), n_pts)
            else:
                freqs = np.linspace(f_start, f_stop, n_pts)

        if self.custom_circuit_netlist or self.sys_params.get('use_ngspice', False) or self.has_any_subckt():
            if not self.is_ngspice_available():
                self.last_ngspice_status = "ngspice 실행 파일을 찾을 수 없어 고속 ABCD 모드로 자동 해석되었습니다."
                return self._calculate_with_abcd(freqs)
            return self._calculate_with_ngspice(freqs, x_scale)
        else:
            return self._calculate_with_abcd(freqs)


    def _calculate_with_abcd(self, freqs: np.ndarray) -> dict:
        """2-포트 ABCD 전송 행렬을 이용한 고속 S-파라미터 해석 (소자별 개별 ESR 반영)"""
        z0 = sanitize_resistance(float(self.sys_params['Z0']))

        c = self.components
        esr = self.esr_values

        l1, l2, l3, l4 = c.get('L1', 22e-9), c.get('L2', 27e-9), c.get('L3', 27e-9), c.get('L4', 22e-9)
        l5, l6, l7 = c.get('L5', 100e-9), c.get('L6', 220e-9), c.get('L7', 100e-9)
        c1, c2, c3 = c.get('C1', 6.8e-12), c.get('C2', 7.5e-12), c.get('C3', 6.8e-12)

        # 소자별 개별 ESR 적용 (0이면 1p = 1e-12 ohm 치환)
        r_l1 = sanitize_resistance(esr.get('L1', 0.35))
        r_l2 = sanitize_resistance(esr.get('L2', 0.35))
        r_l3 = sanitize_resistance(esr.get('L3', 0.35))
        r_l4 = sanitize_resistance(esr.get('L4', 0.35))
        r_l5 = sanitize_resistance(esr.get('L5', 0.35))
        r_l6 = sanitize_resistance(esr.get('L6', 0.35))
        r_l7 = sanitize_resistance(esr.get('L7', 0.35))

        r_c1 = sanitize_resistance(esr.get('C1', 0.05))
        r_c2 = sanitize_resistance(esr.get('C2', 0.05))
        r_c3 = sanitize_resistance(esr.get('C3', 0.05))

        omega = 2.0 * np.pi * freqs

        # 직렬 인덕터 임피던스: Z = j*w*L + ESR
        Z1 = 1j * omega * l1 + r_l1
        Z2 = 1j * omega * l2 + r_l2
        Z3 = 1j * omega * l3 + r_l3
        Z4 = 1j * omega * l4 + r_l4

        # 병렬 LC 탱크: L 브랜치와 C 브랜치의 병렬 어드미턴스 합
        # Y_L = 1 / (j*w*L + r_L),  Y_C = 1 / (r_C + 1/(j*w*C))
        Y_L5 = 1.0 / (1j * omega * l5 + r_l5)
        Y_C1 = 1.0 / (r_c1 + 1.0 / (1j * omega * c1))
        Y1 = Y_L5 + Y_C1

        Y_L6 = 1.0 / (1j * omega * l6 + r_l6)
        Y_C2 = 1.0 / (r_c2 + 1.0 / (1j * omega * c2))
        Y2 = Y_L6 + Y_C2

        Y_L7 = 1.0 / (1j * omega * l7 + r_l7)
        Y_C3 = 1.0 / (r_c3 + 1.0 / (1j * omega * c3))
        Y3 = Y_L7 + Y_C3

        ones = np.ones_like(omega, dtype=complex)
        zeros = np.zeros_like(omega, dtype=complex)

        A = ones.copy()
        B = Z1.copy()
        C = zeros.copy()
        D = ones.copy()

        def mat_mul(A, B, C, D, a, b, c, d):
            return (
                A * a + B * c,
                A * b + B * d,
                C * a + D * c,
                C * b + D * d
            )

        A, B, C, D = mat_mul(A, B, C, D, ones, zeros, Y1, ones)
        A, B, C, D = mat_mul(A, B, C, D, ones, Z2, zeros, ones)
        A, B, C, D = mat_mul(A, B, C, D, ones, zeros, Y2, ones)
        A, B, C, D = mat_mul(A, B, C, D, ones, Z3, zeros, ones)
        A, B, C, D = mat_mul(A, B, C, D, ones, zeros, Y3, ones)
        A, B, C, D = mat_mul(A, B, C, D, ones, Z4, zeros, ones)

        delta = A + (B / z0) + (C * z0) + D

        s11 = (A + (B / z0) - (C * z0) - D) / delta
        s21 = 2.0 / delta
        s12 = s21
        s22 = (-A + (B / z0) - (C * z0) + D) / delta

        s11_mag = np.abs(s11)
        s12_mag = np.abs(s12)
        s21_mag = np.abs(s21)
        s22_mag = np.abs(s22)

        s11_db = 20.0 * np.log10(np.clip(s11_mag, 1e-15, None))
        s12_db = 20.0 * np.log10(np.clip(s12_mag, 1e-15, None))
        s21_db = 20.0 * np.log10(np.clip(s21_mag, 1e-15, None))
        s22_db = 20.0 * np.log10(np.clip(s22_mag, 1e-15, None))

        return {
            'freq': freqs,
            's11_db': s11_db,
            's12_db': s12_db,
            's21_db': s21_db,
            's22_db': s22_db,
            's11_mag': s11_mag,
            's12_mag': s12_mag,
            's21_mag': s21_mag,
            's22_mag': s22_mag,
            's11_cplx': s11,
            's12_cplx': s12,
            's21_cplx': s21,
            's22_cplx': s22,
            'engine_type': 'ABCD (전송행렬 고속해석)'
        }

    def _calculate_with_ngspice(self, freqs: np.ndarray, x_scale: str = 'Linear') -> dict:
        """ngspice 연동 S-parameter 해석"""
        t0 = time.time()
        temp_dir = tempfile.gettempdir()
        cir_name = f"ngspice_sp_{os.getpid()}.cir"
        out_name = f"ngspice_sp_out_{os.getpid()}.txt"
        cir_path = os.path.join(temp_dir, cir_name)
        out_txt_path = os.path.join(temp_dir, out_name)

        f_start = float(freqs[0])
        f_stop = float(freqs[-1])
        n_pts = len(freqs)
        ac_mode = 'dec' if x_scale.lower() == 'log' else 'lin'
        pts_param = int(max(10, n_pts // 3)) if ac_mode == 'dec' else n_pts

        netlist = self.generate_spice_netlist_for_sp(f_start, f_stop, pts_param, ac_mode, out_name)
        self.last_ngspice_netlist = netlist

        with open(cir_path, 'w', encoding='utf-8') as f:
            f.write(netlist)

        try:
            cmd = [self.ngspice_path, '-b', cir_name]
            res = subprocess.run(cmd, cwd=temp_dir, capture_output=True, text=True, timeout=12)
            self.last_ngspice_stdout = res.stdout
            self.last_ngspice_stderr = res.stderr

            if os.path.exists(out_txt_path):
                data = np.loadtxt(out_txt_path)
                sim_freq = data[:, 0]
                s11_db = data[:, 1]
                s12_db = data[:, 3]
                s21_db = data[:, 5]
                s22_db = data[:, 7]

                s11_mag = 10.0 ** (s11_db / 20.0)
                s12_mag = 10.0 ** (s12_db / 20.0)
                s21_mag = 10.0 ** (s21_db / 20.0)
                s22_mag = 10.0 ** (s22_db / 20.0)

                duration = time.time() - t0
                self.last_ngspice_time = duration
                self.last_ngspice_status = f"정상 실행 완료 ({duration:.3f}초, {len(sim_freq)}pt)"

                return {
                    'freq': sim_freq,
                    's11_db': s11_db,
                    's12_db': s12_db,
                    's21_db': s21_db,
                    's22_db': s22_db,
                    's11_mag': s11_mag,
                    's12_mag': s12_mag,
                    's21_mag': s21_mag,
                    's22_mag': s22_mag,
                    'engine_type': 'NGSpice (Spice64)',
                    'sim_time': f"{duration:.3f}초"
                }
            else:
                err_msg = res.stderr or res.stdout or "출력 파일이 생성되지 않음"
                self.last_ngspice_status = f"실행 실패 (출력 파일 없음)"
                print("NGSpice failed to generate output:", err_msg[:200])
        except Exception as e:
            self.last_ngspice_status = f"실행 중 예외 발생: {e}"
            print("NGSpice execution failed, falling back to ABCD matrix:", e)
        finally:
            for p in [cir_path, out_txt_path]:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

        fallback = self._calculate_with_abcd(freqs)
        fallback['engine_type'] = 'ABCD (NGSpice 대체)'
        return fallback

    def generate_spice_netlist_for_sp(self, f_start: float, f_stop: float, n_pts: int, ac_mode: str, out_txt_path: str) -> str:
        """
        ngspice 공식 S-parameter 2-Port 측정을 위한 넷리스트를 생성합니다.
        부품별 개별 ESR 반영 및 R=0 일 때 1p 치환 규칙을 적용합니다.
        """
        z0 = sanitize_resistance(float(self.sys_params['Z0']))

        lines = [
            "* RLC BPF 2-Port S-Parameter Simulation for NGSpice",
            f".param Rbase={z0} Vbias_in=0 Vbias_out=0",
            ""
        ]

        if self.custom_circuit_netlist:
            lines.append("* --- User Custom Circuit Netlist ---")
            lines.append(self.custom_circuit_netlist)
        else:
            # 1. 서브서킷 정의 블록 포함
            subckt_definitions = []
            for name, sm in self.spice_models.items():
                if sm['mode'] == 'subckt' and sm['text']:
                    subckt_definitions.append(sm['text'])

            if subckt_definitions:
                lines.append("* --- User SPICE Subcircuit Definitions ---")
                lines.extend(subckt_definitions)
                lines.append("")

            # 2. 회로 부품 인스턴스화 (소자별 개별 ESR 적용)
            lines.append("* --- Filter Circuit Netlist with Individual ESR ---")
            c = self.components
            esr = self.esr_values

            for name, nodes in COMPONENT_NODES.items():
                n1, n2 = nodes
                sm = self.spice_models[name]
                if sm['mode'] == 'subckt' and sm['model_name']:
                    lines.append(f"X_{name} {n1} {n2} {sm['model_name']}")
                else:
                    val = c[name]
                    r_val = sanitize_resistance(esr.get(name, 0.0))
                    int_node = f"int_{name}"

                    if name.startswith('L'):
                        # 인덕터 + 개별 ESR
                        lines.append(f"{name} {n1} {int_node} {val}")
                        lines.append(f"R_esr_{name} {int_node} {n2} {r_val}")
                    elif name.startswith('C'):
                        # 커패시터 + 개별 ESR
                        lines.append(f"{name} {n1} {int_node} {val}")
                        lines.append(f"R_esr_{name} {int_node} {n2} {r_val}")

        # 3. ngspice 공식 S_PARAM 서브서킷 및 제어 스크립트
        lines.extend([
            "",
            "* --- S-Parameter Measurement Driver & Readout ---",
            "X_SP in out S_2_2 S_1_2 S_PARAM",
            "",
            ".SUBCKT S_PARAM 22 66 5 7",
            "RS1 22 2 0.001",
            "RS2 66 6 0.001",
            "RS3 22 6 1e12",
            "RS4 66 2 1e12",
            "Vacdc 1 0 DC 'Vbias_in' AC 1",
            "R1 1 2 'Rbase'",
            "E1 3 0 2 0 2",
            "Vac 3 4 DC 0 AC 1",
            "R_loop 4 5 0.001",
            "R3 5 0 1",
            "E2 7 0 6 0 2",
            "R4 6 8 'Rbase'",
            "Vdc 8 0 DC 'Vbias_out' AC 0",
            ".ends",
            "",
            "* --- Control Script for S-Parameters ---",
            ".control",
            "set noaskquit",
            "set filetype=ascii",
            "op",
            "let Vdcnew=V(X_SP.1)",
            "let Vacdcnew=v(X_SP.8)",
            f"ac {ac_mode} {n_pts} {f_start} {f_stop}",
            "",
            "alter R.X_SP.RS1=1e12",
            "alter R.X_SP.RS2=1e12",
            "alter R.X_SP.RS3=0.001",
            "alter R.X_SP.RS4=0.001",
            "alter V.X_SP.Vacdc DC=op1.Vacdcnew",
            "alter V.X_SP.Vdc DC=op1.Vdcnew",
            "op",
            f"ac {ac_mode} {n_pts} {f_start} {f_stop}",
            "",
            "let s_1_1=ac1.s_2_2",
            "let s_2_1=ac1.s_1_2",
            "let S11db = db(s_1_1)",
            "let S12db = db(s_1_2)",
            "let S21db = db(s_2_1)",
            "let S22db = db(s_2_2)",
            f'wrdata {out_txt_path} S11db S12db S21db S22db',
            "quit",
            ".endc",
            ".end"
        ])

        return "\n".join(lines)

    def generate_spice_netlist(self) -> str:
        """표준 SPICE 넷리스트 텍스트 생성"""
        return self.generate_spice_netlist_for_sp(
            self.sys_params['start_freq'],
            self.sys_params['stop_freq'],
            self.sys_params['num_points'],
            'lin',
            's_param_out.txt'
        )

    def export_touchstone_s2p(self, filepath: str):
        """Touchstone v1.1 (.s2p) 파일 내보내기"""
        res = self.calculate_s_parameters()
        freqs_mhz = res['freq'] / 1e6

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("! Touchstone 2-Port S-Parameter Data File\n")
            f.write(f"! Z0 = {self.sys_params['Z0']} Ohms\n")
            f.write(f"! Engine = {res.get('engine_type', 'Unknown')}\n")
            f.write("# MHZ S DB R 50\n")
            f.write("! Freq(MHz)  S11_dB  S11_deg  S21_dB  S21_deg  S12_dB  S12_deg  S22_dB  S22_deg\n")

            for i in range(len(freqs_mhz)):
                p11 = np.angle(res['s11_cplx'][i], deg=True) if 's11_cplx' in res else 0.0
                p21 = np.angle(res['s21_cplx'][i], deg=True) if 's21_cplx' in res else 0.0
                p12 = np.angle(res['s12_cplx'][i], deg=True) if 's12_cplx' in res else 0.0
                p22 = np.angle(res['s22_cplx'][i], deg=True) if 's22_cplx' in res else 0.0

                f.write(
                    f"{freqs_mhz[i]:10.4f} "
                    f"{res['s11_db'][i]:10.3f} {p11:9.2f} "
                    f"{res['s21_db'][i]:10.3f} {p21:9.2f} "
                    f"{res['s12_db'][i]:10.3f} {p12:9.2f} "
                    f"{res['s22_db'][i]:10.3f} {p22:9.2f}\n"
                )

    def export_results_csv(self, filepath: str):
        """시뮬레이션 결과 파형 데이터를 CSV 파일로 내보내기 (Excel 호환 UTF-8 BOM)"""
        res = self.calculate_s_parameters()
        freqs = res['freq']
        freqs_mhz = freqs / 1e6
        s11_db = res['s11_db']
        s12_db = res['s12_db']
        s21_db = res['s21_db']
        s22_db = res['s22_db']
        s11_mag = res.get('s11_mag', 10.0 ** (s11_db / 20.0))
        s12_mag = res.get('s12_mag', 10.0 ** (s12_db / 20.0))
        s21_mag = res.get('s21_mag', 10.0 ** (s21_db / 20.0))
        s22_mag = res.get('s22_mag', 10.0 ** (s22_db / 20.0))
        engine_str = res.get('engine_type', 'Simulator')

        with open(filepath, 'w', encoding='utf-8-sig') as f:
            f.write("Freq_Hz,Freq_MHz,S11_dB,S12_dB,S21_dB,S22_dB,S11_Mag,S12_Mag,S21_Mag,S22_Mag,Engine\n")
            for i in range(len(freqs)):
                f.write(
                    f"{freqs[i]:.4e},{freqs_mhz[i]:.6f},"
                    f"{s11_db[i]:.4f},{s12_db[i]:.4f},{s21_db[i]:.4f},{s22_db[i]:.4f},"
                    f"{s11_mag[i]:.6f},{s12_mag[i]:.6f},{s21_mag[i]:.6f},{s22_mag[i]:.6f},"
                    f"{engine_str}\n"
                )

    def get_default_netlist_template(self) -> str:
        """기본값 템플릿 넷리스트 텍스트 반환"""
        return (
            "* RLC Bandpass Filter Netlist (기본 템플릿)\n"
            "* Port 1: in, Port 2: out, Ground: 0\n\n"
            "* --- 직렬 인덕터 (Series Inductors) ---\n"
            "L1 in n1 22n\n"
            "L2 n1 n2 27n\n"
            "L3 n2 n3 27n\n"
            "L4 n3 out 22n\n\n"
            "* --- 병렬 공진 소자 (Shunt Resonators) ---\n"
            "L5 n1 0 100n\n"
            "C1 n1 0 6.8p\n"
            "L6 n2 0 220n\n"
            "C2 n2 0 7.5p\n"
            "L7 n3 0 100n\n"
            "C3 n3 0 6.8p\n"
        )

    def generate_pure_circuit_netlist(self) -> str:
        """현재 회로 상태를 반영한 깔끔한 회로 넷리스트 생성"""
        if self.custom_circuit_netlist:
            return self.custom_circuit_netlist

        lines = [
            "* RLC Bandpass Filter Netlist",
            "* Port 1: in, Port 2: out, Ground: 0",
            ""
        ]

        # 서브서킷 정의가 있다면 상단에 추가
        for name, sm in self.spice_models.items():
            if sm['mode'] == 'subckt' and sm['text']:
                lines.append(f"* --- Subcircuit for {name} ---")
                lines.append(sm['text'].strip())
                lines.append("")

        lines.append("* --- 직렬 인덕터 (Series Inductors) ---")
        for name in ['L1', 'L2', 'L3', 'L4']:
            sm = self.spice_models.get(name, {'mode': 'value'})
            n1, n2 = COMPONENT_NODES[name]
            if sm['mode'] == 'subckt' and sm.get('model_name'):
                lines.append(f"X_{name} {n1} {n2} {sm['model_name']}")
            else:
                val_txt = rlc.format_engineering(self.components.get(name, 22e-9), 'L')
                lines.append(f"{name} {n1} {n2} {val_txt}")

        lines.append("")
        lines.append("* --- 병렬 공진 소자 (Shunt Resonators) ---")
        for pair in [('L5', 'C1'), ('L6', 'C2'), ('L7', 'C3')]:
            for name in pair:
                sm = self.spice_models.get(name, {'mode': 'value'})
                n1, n2 = COMPONENT_NODES[name]
                ctype = 'L' if name.startswith('L') else 'C'
                if sm['mode'] == 'subckt' and sm.get('model_name'):
                    lines.append(f"X_{name} {n1} {n2} {sm['model_name']}")
                else:
                    val_txt = rlc.format_engineering(self.components.get(name, 100e-9 if ctype == 'L' else 6.8e-12), ctype)
                    lines.append(f"{name} {n1} {n2} {val_txt}")

        return "\n".join(lines)

    def apply_and_validate_netlist(self, netlist_text: str) -> tuple[bool, str]:
        """
        사용자가 입력한 SPICE 넷리스트를 검증하고 현재 회로 엔진에 적용합니다.
        Port 1 ('in')에서 Port 2 ('out')까지 연결되어야 하며,
        논리가 올바르지 않으면 적용하지 않고 False와 에러 메시지를 반환합니다.
        """
        clean_text = normalize_spice_netlist(netlist_text.strip())
        if not clean_text:
            return False, "넷리스트 내용이 비어 있습니다."

        # 1. 넷리스트 토큰 및 노드 분석
        nodes_found = set()
        subckts = []
        parsed_components = {}
        parsed_nodes = {}
        parsed_types = {}
        parsed_esr = {}

        # 서브서킷 블록 분리
        subckt_blocks = re.findall(r"(?:\.SUBCKT[\s\S]*?\.ENDS(?:\s+\S+)?)", clean_text, re.IGNORECASE)
        for sb in subckt_blocks:
            subckts.append(sb.strip())

        # 일반 소자 라인 파싱
        # 서브서킷 블록 내부를 제외한 라인들
        text_without_subckts = re.sub(r"(?:\.SUBCKT[\s\S]*?\.ENDS(?:\s+\S+)?)", "", clean_text, flags=re.IGNORECASE)

        for line in text_without_subckts.splitlines():
            line = line.strip()
            if not line or line.startswith('*') or line.startswith('.'):
                continue

            parts = line.split()
            if len(parts) < 3:
                return False, f"유효하지 않은 소자 정의 라인입니다:\n'{line}'\n(소자명, 노드1, 노드2, 값 형식이 필요합니다)"

            comp_name = parts[0].upper()
            ctype = comp_name[0]
            if ctype not in ('R', 'L', 'C', 'X', 'V', 'I', 'K', 'M', 'Q', 'D', 'Z'):
                return False, f"알 수 없는 SPICE 소자 유형입니다: '{comp_name}' (line: {line})"

            if len(parts) >= 4:
                n1 = parts[1].lower()
                n2 = parts[2].lower()
                val_str = parts[3]

                nodes_found.add(n1)
                nodes_found.add(n2)

                # 소자값 파싱
                if comp_name.startswith('R_ESR_'):
                    base_comp = comp_name.replace('R_ESR_', '')
                    try:
                        r_val = float(val_str) if val_str.replace('.', '', 1).isdigit() else rlc.parse_value_with_unit(val_str, 'R')
                        parsed_esr[base_comp] = r_val
                    except Exception:
                        pass
                elif ctype in ('L', 'C', 'R'):
                    clean_name = comp_name
                    # 표준 소자 이름(L1~L7, C1~C3, R1 등) 매핑
                    parsed_val = rlc.parse_value_with_unit(val_str, ctype)
                    if parsed_val > 0:
                        parsed_components[clean_name] = parsed_val
                        parsed_nodes[clean_name] = (n1, n2)
                        parsed_types[clean_name] = ctype
            elif ctype == 'X' and len(parts) >= 3:
                n1 = parts[1].lower()
                n2 = parts[2].lower()
                nodes_found.add(n1)
                nodes_found.add(n2)
                parsed_nodes[comp_name] = (n1, n2)
                parsed_types[comp_name] = 'X'

        # 2. Port 1('in')과 Port 2('out') 연결 여부 검증
        if 'in' not in nodes_found:
            return False, "Port 1 노드('in')가 넷리스트에 존재하지 않습니다.\n신호 입력 포트는 'in' 노드에 연결되어야 합니다."
        if 'out' not in nodes_found:
            return False, "Port 2 노드('out')가 넷리스트에 존재하지 않습니다.\n신호 출력 포트는 'out' 노드에 연결되어야 합니다."

        # 3. NGSpice 테스트벤치 구동 검증 (로직 및 수렴 확인)
        temp_dir = tempfile.gettempdir()
        t_id = f"{os.getpid()}_{time.time_ns()}"
        cir_name = f"netlist_validate_{t_id}.cir"
        out_name = f"netlist_validate_out_{t_id}.txt"
        cir_path = os.path.join(temp_dir, cir_name)
        out_txt_path = os.path.join(temp_dir, out_name)

        z0 = sanitize_resistance(float(self.sys_params.get('Z0', 50.0)))
        test_netlist_lines = [
            "* Netlist Logic Validation Test",
            f".param Rbase={z0} Vbias_in=0 Vbias_out=0",
            clean_text,
            "",
            "* S-Parameter Driver",
            "X_SP in out S_2_2 S_1_2 S_PARAM",
            "",
            ".SUBCKT S_PARAM 22 66 5 7",
            "RS1 22 2 0.001",
            "RS2 66 6 0.001",
            "RS3 22 6 1e12",
            "RS4 66 2 1e12",
            "Vacdc 1 0 DC 0 AC 1",
            "R1 1 2 'Rbase'",
            "E1 3 0 2 0 2",
            "Vac 3 4 DC 0 AC 1",
            "R_loop 4 5 0.001",
            "R3 5 0 1",
            "E2 7 0 6 0 2",
            "R4 6 8 'Rbase'",
            "Vdc 8 0 DC 0 AC 0",
            ".ends",
            "",
            ".control",
            "set noaskquit",
            "set filetype=ascii",
            "op",
            "let Vdcnew=V(X_SP.1)",
            "let Vacdcnew=v(X_SP.8)",
            "ac lin 10 100k 500meg",
            "alter R.X_SP.RS1=1e12",
            "alter R.X_SP.RS2=1e12",
            "alter R.X_SP.RS3=0.001",
            "alter R.X_SP.RS4=0.001",
            "alter V.X_SP.Vacdc DC=op1.Vacdcnew",
            "alter V.X_SP.Vdc DC=op1.Vdcnew",
            "op",
            "ac lin 10 100k 500meg",
            "let s_1_1=ac1.s_2_2",
            "let s_2_1=ac1.s_1_2",
            "let S11db = db(s_1_1)",
            "let S12db = db(s_1_2)",
            "let S21db = db(s_2_1)",
            "let S22db = db(s_2_2)",
            f'wrdata {out_name} S11db S12db S21db S22db',
            "quit",
            ".endc",
            ".end"
        ]

        # ngspice 실행 파일 유효성 검증
        if not self.is_ngspice_available():
            return False, "ngspice 실행 파일을 찾을 수 없어 SPICE 넷리스트 검증을 실행할 수 없습니다.\n상단 [설정] 버튼에서 ngspice.exe 경로를 지정해주세요."

        with open(cir_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(test_netlist_lines))


        try:
            cmd = [self.ngspice_path, '-b', cir_name]
            res = subprocess.run(cmd, cwd=temp_dir, capture_output=True, text=True, timeout=10)

            full_output = (res.stdout or "") + "\n" + (res.stderr or "")
            if "Error:" in full_output or "fatal error" in full_output.lower():
                err_lines = [l.strip() for l in full_output.splitlines() if "error" in l.lower()]
                err_msg = "\n".join(err_lines[:4]) if err_lines else full_output[:300]
                return False, f"NGSpice 해석 중 에러가 발생했습니다:\n{err_msg}"

            if not os.path.exists(out_txt_path):
                err = res.stderr or res.stdout or "출력 파일 생성 실패"
                return False, f"NGSpice 해석 실패 (회로 연결 오류 또는 수렴 불가):\n{err[:300]}"

            # 성공 시 데이터 로드 테스트
            data = np.loadtxt(out_txt_path)
            if data.shape[0] < 5:
                return False, "NGSpice 해석 결과 데이터 포인트가 부족합니다."

        except Exception as e:
            return False, f"NGSpice 검증 중 예외 발생: {e}"
        finally:
            for p in [cir_path, out_txt_path]:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

        # 4. 검증 통과 -> 커스텀 회로 넷리스트 저장 및 파싱된 값 적용
        self.custom_circuit_netlist = clean_text
        self.sys_params['use_ngspice'] = True

        # 넷리스트에 명시된 소자들로 self.components, self.component_nodes, self.comp_types 완전 동기화
        self.components = dict(parsed_components)
        self.component_nodes = dict(parsed_nodes)
        self.comp_types = dict(parsed_types)

        # 소자별 개별 ESR 갱신
        for name, esr_val in parsed_esr.items():
            self.esr_values[name] = esr_val

        # 누락된 소자의 기본 SPICE 모델 초기화
        for cname in self.components:
            if cname not in self.spice_models:
                self.spice_models[cname] = {'mode': 'value', 'text': '', 'model_name': ''}

        # 서브서킷 파싱 적용
        for sb in subckts:
            m = re.search(r"^\s*\.SUBCKT\s+(\S+)", sb, re.IGNORECASE | re.MULTILINE)
            if m:
                mname = m.group(1)
                for cname in self.components:
                    # 넷리스트에서 X_<cname> 으로 인스턴스화되었는지 확인
                    if re.search(rf"\bX_{cname}\b|\bX{cname}\b", clean_text, re.IGNORECASE):
                        self.set_spice_model(cname, 'subckt', sb)

        return True, "성공"

    def reset_to_defaults(self):
        """기본 BPF 회로 설계 상태로 초기화 복원"""
        self.custom_circuit_netlist = None
        self.components = dict(DEFAULT_COMPONENTS)
        self.esr_values = dict(DEFAULT_ESR)
        self.component_nodes = dict(COMPONENT_NODES)
        self.comp_types = {name: ('L' if name.startswith('L') else ('C' if name.startswith('C') else 'R')) for name in self.components}
        self.spice_models = {name: {'mode': 'value', 'text': '', 'model_name': ''} for name in self.components}
        self.sys_params['use_ngspice'] = False

