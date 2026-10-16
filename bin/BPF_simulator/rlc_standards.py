# -*- coding: utf-8 -*-
"""
RLC 소자 표준 판매 규격 (E-Series: IEC 60063) 모듈
저항, 커패시터, 인덕터의 시중 판매 단위 및 허용오차별 공칭값을 정의합니다.
"""

import numpy as np
import os
import sys
import json
import re

def get_rlc_json_path() -> str:
    """rlc_values.json 파일의 우선 탐색 경로 반환 (현재 작업 폴더 -> MEIPASS -> 모듈 폴더)"""
    cwd_path = os.path.join(os.getcwd(), 'rlc_values.json')
    if os.path.exists(cwd_path):
        return cwd_path
    if hasattr(sys, '_MEIPASS'):
        mei_path = os.path.join(sys._MEIPASS, 'rlc_values.json')
        if os.path.exists(mei_path):
            return mei_path
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rlc_values.json')

# 기본 RLC 공칭값 JSON 파일 경로 정의
RLC_JSON_PATH = get_rlc_json_path()

# =============================================================================
# IEC 60063 표준 E-시리즈 공칭값 (1.0 ~ 10.0 범위)
# =============================================================================

# E6 시리즈: 20% 허용오차 (6 steps per decade)
E6_BASE = [1.0, 1.5, 2.2, 3.3, 4.7, 6.8]

# E12 시리즈: 10% 허용오차 (12 steps per decade)
E12_BASE = [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2]

# E24 시리즈: 5% 허용오차 (24 steps per decade)
E24_BASE = [
    1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0,
    3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1
]

# E96 시리즈: 1% 허용오차 (96 steps per decade)
E96_BASE = [
    1.00, 1.02, 1.05, 1.07, 1.10, 1.13, 1.15, 1.18, 1.21, 1.24, 1.27, 1.30,
    1.33, 1.37, 1.40, 1.43, 1.47, 1.50, 1.54, 1.58, 1.62, 1.65, 1.69, 1.74,
    1.78, 1.82, 1.87, 1.91, 1.96, 2.00, 2.05, 2.10, 2.15, 2.21, 2.26, 2.32,
    2.37, 2.43, 2.49, 2.55, 2.61, 2.67, 2.74, 2.80, 2.87, 2.94, 3.01, 3.09,
    3.16, 3.24, 3.32, 3.40, 3.48, 3.57, 3.65, 3.74, 3.83, 3.92, 4.02, 4.12,
    4.22, 4.32, 4.42, 4.53, 4.64, 4.75, 4.87, 4.99, 5.11, 5.23, 5.36, 5.49,
    5.62, 5.76, 5.90, 6.04, 6.19, 6.34, 6.49, 6.65, 6.81, 6.98, 7.15, 7.32,
    7.50, 7.68, 7.87, 8.06, 8.25, 8.45, 8.66, 8.87, 9.09, 9.31, 9.53, 9.76
]

# =============================================================================
# 소자 유형별 허용오차 및 E-시리즈 매핑
# 저항: 1% (E96), 5% (E24), 10% (E12), 20% (E6)
# 커패시터: 5% (E24), 10% (E12), 20% (E6)
# 인덕터: 10% (E12), 20% (E6)
# =============================================================================
TOLERANCE_MAP = {
    'R': {
        '1% (E96)': E96_BASE,
        '5% (E24)': E24_BASE,
        '10% (E12)': E12_BASE,
        '20% (E6)': E6_BASE,
    },
    'C': {
        '5% (E24)': E24_BASE,
        '10% (E12)': E12_BASE,
        '20% (E6)': E6_BASE,
    },
    'L': {
        '10% (E12)': E12_BASE,
        '20% (E6)': E6_BASE,
    }
}

# 기본 허용오차 선택값
DEFAULT_TOLERANCE = {
    'R': '5% (E24)',
    'C': '5% (E24)',
    'L': '10% (E12)',
}

# 각 소자별 단위 정의 (기호, 1 기본단위 대비 크기)
UNITS = {
    'R': [('mΩ', 1e-3), ('Ω', 1.0), ('kΩ', 1e3), ('MΩ', 1e6)],
    'L': [('pH', 1e-12), ('nH', 1e-9), ('uH', 1e-6), ('mH', 1e-3)],
    'C': [('fF', 1e-15), ('pF', 1e-12), ('nF', 1e-9), ('uF', 1e-6)]
}


def get_e_series_base(component_type: str, tolerance_str: str) -> list[float]:
    """소자 타입과 오차율 문자열에 따른 기본 E-시리즈 값 목록을 반환합니다."""
    type_map = TOLERANCE_MAP.get(component_type.upper(), TOLERANCE_MAP['R'])
    return type_map.get(tolerance_str, list(type_map.values())[0])


def generate_available_values(base_list: list[float], min_val: float, max_val: float) -> list[float]:
    """
    주어진 기본 E-시리즈 값(1.0~9.76)과 최소/최대 범위 사이의
    모든 판매 공칭값(부동소수점 실제 단위) 목록을 오름차순으로 생성합니다.
    """
    min_exp = int(np.floor(np.log10(max(min_val, 1e-18))))
    max_exp = int(np.ceil(np.log10(max(max_val, 1e-18))))
    
    values = []
    for exp in range(min_exp - 1, max_exp + 2):
        scale = 10.0 ** exp
        for b in base_list:
            v = b * scale
            # 유효 범위 내의 값만 포함 (약간의 여유 마진 제공)
            if (min_val * 0.999) <= v <= (max_val * 1.001):
                # 부동소수점 오차 정밀도 보정
                values.append(float(f"{v:.6e}"))
                
    values = sorted(list(set(values)))
    return values


def snap_to_e_series(value: float, base_list: list[float]) -> float:
    """
    임의의 실수 값을 가장 가까운 표준 E-시리즈 공칭값으로 스냅(변환)합니다.
    """
    if value <= 0:
        return base_list[0]
    
    exp = np.floor(np.log10(value))
    mantissa = value / (10.0 ** exp)
    
    # 10.0 경계 처리를 위해 10.0 추가
    extended = list(base_list) + [10.0]
    
    # 로그 스케일 비율 기준 가장 가까운 인덱스 탐색
    log_mantissa = np.log10(mantissa)
    diffs = [abs(np.log10(x) - log_mantissa) for x in extended]
    idx = int(np.argmin(diffs))
    
    chosen = extended[idx]
    if abs(chosen - 10.0) < 1e-6:
        result = 1.0 * (10.0 ** (exp + 1))
    else:
        result = chosen * (10.0 ** exp)
        
    return float(f"{result:.6e}")


def format_engineering(value: float, component_type: str) -> str:
    """
    값을 사람이 읽기 좋은 공학 단위 문자열(예: 18 nH, 6.8 pF, 50 Ω)로 변환합니다.
    """
    if value == 0:
        return f"0 {UNITS[component_type][1][0]}"
    
    units = UNITS[component_type]
    # 적합한 단위 선택
    chosen_unit = units[0][0]
    chosen_scale = units[0][1]
    
    for u_name, u_scale in units:
        if value >= (u_scale * 0.999):
            chosen_unit = u_name
            chosen_scale = u_scale
            
    scaled_val = value / chosen_scale
    
    # 소수점 표시 처리 (정수 형태면 소수점 제거, 아니면 최대 3자리)
    if abs(scaled_val - round(scaled_val)) < 1e-4:
        return f"{int(round(scaled_val))} {chosen_unit}"
    else:
        # 끝자리 불필요한 0 제거
        val_str = f"{scaled_val:.3f}".rstrip('0').rstrip('.')
        return f"{val_str} {chosen_unit}"


import re

def parse_value_with_unit(text: str, component_type: str) -> float:
    """
    문자열(예: '18nh', '27 nH', '6.8pF', '100', '1.2u', '50 ohm', '10k')을 파싱하여
    실제 부동소수점 값(SI 기본 단위)으로 변환합니다.
    """
    clean_text = text.strip().replace(' ', '').replace('Ω', '').replace('ohm', '').replace('OHM', '').replace('µ', 'u')
    if not clean_text:
        return 0.0
    
    # 정규식으로 숫자 부분과 단위 접미사 분리
    match = re.match(r"^([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*([a-zA-Z가-힣]*)$", clean_text)
    if not match:
        return 0.0
        
    num_str, suffix = match.groups()
    try:
        base_num = float(num_str)
    except ValueError:
        return 0.0
        
    suffix = suffix.lower()
    
    # 기본 소자 단위 제거 (h, f 등)
    if component_type == 'L' and suffix.endswith('h'):
        suffix = suffix[:-1]
    elif component_type == 'C' and suffix.endswith('f'):
        suffix = suffix[:-1]
        
    # 배수 단위 매핑
    scale_dict = {
        'f': 1e-15,  # 펨토
        'p': 1e-12,  # 피코
        'n': 1e-9,   # 나노
        'u': 1e-6,   # 마이크로
        'm': 1e-3,   # 밀리
        '': 1.0,     # 기본
        'k': 1e3,    # 킬로
        'meg': 1e6,  # 메가
        'm': 1e-3 if component_type != 'R' else 1e-3,  # 저항에서 m은 밀리, M은 메가
        'g': 1e9     # 기가
    }
    
    # 저항에서 대문자 M은 메가 처리
    if component_type == 'R' and match.group(2).startswith('M'):
        scale = 1e6
    else:
        scale = scale_dict.get(suffix, 1.0)
        
    return base_num * scale


def get_default_rlc_dict() -> dict[str, list[str]]:
    """
    RLC 기본 콤보박스에 사용될 R, L, C 분류별 기본 공칭값 목록을 반환합니다.
    BPF 필터 설계 및 일반 RF/아날로그 회로에서 널리 쓰이는 표준 규격값입니다.
    """
    return {
        "R": [
            "0.1 Ω", "0.22 Ω", "0.47 Ω", "1 Ω", "1.5 Ω", "2.2 Ω", "3.3 Ω", "4.7 Ω", "6.8 Ω",
            "10 Ω", "15 Ω", "22 Ω", "27 Ω", "33 Ω", "39 Ω", "47 Ω", "50 Ω", "51 Ω", "56 Ω", "68 Ω", "75 Ω", "82 Ω",
            "100 Ω", "120 Ω", "150 Ω", "180 Ω", "220 Ω", "270 Ω", "330 Ω", "390 Ω", "470 Ω", "560 Ω", "680 Ω", "820 Ω",
            "1 kΩ", "1.5 kΩ", "2.2 kΩ", "3.3 kΩ", "4.7 kΩ", "6.8 kΩ",
            "10 kΩ", "22 kΩ", "47 kΩ", "100 kΩ", "1 MΩ"
        ],
        "L": [
            "1 nH", "1.2 nH", "1.5 nH", "1.8 nH", "2.2 nH", "2.7 nH", "3.3 nH", "3.9 nH", "4.7 nH", "5.6 nH", "6.8 nH", "8.2 nH",
            "10 nH", "12 nH", "15 nH", "18 nH", "22 nH", "27 nH", "33 nH", "39 nH", "47 nH", "56 nH", "68 nH", "82 nH",
            "100 nH", "120 nH", "150 nH", "180 nH", "220 nH", "270 nH", "330 nH", "390 nH", "470 nH", "560 nH", "680 nH", "820 nH",
            "1 uH", "1.5 uH", "2.2 uH", "3.3 uH", "4.7 uH", "6.8 uH", "10 uH", "22 uH", "47 uH", "100 uH"
        ],
        "C": [
            "0.5 pF", "0.68 pF", "0.82 pF", "1 pF", "1.2 pF", "1.5 pF", "1.8 pF", "2 pF", "2.2 pF", "2.7 pF", "3 pF", "3.3 pF", "3.9 pF", "4.7 pF", "5.6 pF", "6.8 pF", "7.5 pF", "8.2 pF", "9.1 pF",
            "10 pF", "12 pF", "15 pF", "18 pF", "20 pF", "22 pF", "27 pF", "30 pF", "33 pF", "39 pF", "47 pF", "56 pF", "68 pF", "82 pF",
            "100 pF", "120 pF", "150 pF", "180 pF", "220 pF", "270 pF", "330 pF", "390 pF", "470 pF", "560 pF", "680 pF", "820 pF",
            "1 nF", "1.5 nF", "2.2 nF", "3.3 nF", "4.7 nF", "6.8 nF", "10 nF", "22 nF", "47 nF", "100 nF", "1 uF"
        ]
    }


def save_rlc_values_json(data: dict[str, list[str]], path: str = RLC_JSON_PATH):
    """RLC 공칭값 분류 사전을 JSON 파일로 UTF-8 포맷으로 저장합니다."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[RLC] JSON 저장 오류 ({path}): {e}")


def load_rlc_values_json(path: str = RLC_JSON_PATH) -> dict[str, list[tuple[float, str]]]:
    """
    JSON 파일에서 R, L, C 목록을 로드하여 (실제값_float, 표시텍스트_str) 리스트의 딕셔너리로 반환합니다.
    파일이 존재하지 않으면 기본 규격으로 JSON 파일을 자동 생성(저장)한 후 반환합니다.
    사용자가 직접 수정한 문자열이나 숫자 모두 자동으로 파싱됩니다.
    """
    raw_dict = None
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                raw_dict = json.load(f)
        except Exception as e:
            print(f"[RLC] JSON 로드 오류 ({path}): {e}")

    # 파일이 없거나 읽기 실패한 경우 기본값 사용 및 파일 생성
    if not raw_dict or not isinstance(raw_dict, dict):
        raw_dict = get_default_rlc_dict()
        save_rlc_values_json(raw_dict, path)

    parsed_result = {'R': [], 'L': [], 'C': []}
    for comp_type in ['R', 'L', 'C']:
        items = raw_dict.get(comp_type, [])
        item_list = []
        for it in items:
            if isinstance(it, (int, float)):
                val = float(it)
                txt = format_engineering(val, comp_type)
            elif isinstance(it, str):
                txt = it.strip()
                val = parse_value_with_unit(txt, comp_type)
            else:
                continue

            if val > 0:
                item_list.append((val, txt))

        # 공칭값 크기순(오름차순) 정렬 및 중복 제거
        item_list.sort(key=lambda x: x[0])
        unique_list = []
        seen_vals = set()
        for v, t in item_list:
            v_key = round(v, 18)
            if v_key not in seen_vals:
                seen_vals.add(v_key)
                unique_list.append((v, t))

        parsed_result[comp_type] = unique_list

    return parsed_result


