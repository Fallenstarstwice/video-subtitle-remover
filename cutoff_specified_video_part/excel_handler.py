"""
Excel处理模块
读取和解析Excel文件中的视频路径和时间戳
"""
import pandas as pd
import json
import re
from typing import List, Dict, Tuple, Optional
from pathlib import Path


def parse_timestamp(ts_str: str) -> Optional[List[Tuple[float, float]]]:
    """
    解析时间戳格式

    支持两种格式:
    1. 单个对象: {"timestamp_start": "000:5", "timestamp_end": "000:8"}
    2. 数组格式: [{"timestamp_start": "000:5", "timestamp_end": "000:8"}, ...]

    Args:
        ts_str: 时间戳字符串

    Returns:
        [(start_seconds, end_seconds), ...] 或 None
    """
    if not ts_str or pd.isna(ts_str):
        return None

    try:
        # 尝试解析JSON格式
        data = json.loads(ts_str)

        def parse_time_str(time_str: str) -> float:
            """将 "000:5" 或 "001:13" 转换为秒数"""
            match = re.match(r'(\d+):(\d+)', time_str)
            if match:
                minutes = int(match.group(1))
                seconds = int(match.group(2))
                return minutes * 60 + seconds
            return 0

        segments = []

        # 判断是数组还是单个对象
        if isinstance(data, list):
            # 数组格式: [{"timestamp_start": "000:5", "timestamp_end": "000:8"}, ...]
            for item in data:
                start_str = item.get("timestamp_start", "")
                end_str = item.get("timestamp_end", "")
                start_seconds = parse_time_str(start_str)
                end_seconds = parse_time_str(end_str)
                segments.append((start_seconds, end_seconds))
        elif isinstance(data, dict):
            # 单个对象格式: {"timestamp_start": "000:5", "timestamp_end": "000:8"}
            start_str = data.get("timestamp_start", "")
            end_str = data.get("timestamp_end", "")
            start_seconds = parse_time_str(start_str)
            end_seconds = parse_time_str(end_str)
            segments.append((start_seconds, end_seconds))
        else:
            return None

        return segments if segments else None

    except (json.JSONDecodeError, KeyError, AttributeError):
        return None


def read_excel_file(excel_path: str) -> Tuple[pd.DataFrame, List[Dict]]:
    """
    读取Excel文件并解析视频路径和时间戳

    Args:
        excel_path: Excel文件路径

    Returns:
        (原始DataFrame, 解析后的数据列表)
        解析后的数据格式: [
            {
                'row_index': 行号,
                'video_path': 视频路径,
                'segments_to_remove': [(start_sec, end_sec), ...],
                'errors': [错误信息列表]
            }
        ]
    """
    df = pd.read_excel(excel_path)
    excel_dir = str(Path(excel_path).parent)

    results = []

    for idx, row in df.iterrows():
        # 第一列是视频路径
        video_path = row.iloc[0] if len(row) > 0 else None

        # 后续列是时间戳
        segments_to_remove = []
        errors = []

        # 解析所有时间戳列
        for col_idx in range(1, len(row)):
            timestamp_cell = row.iloc[col_idx]

            if pd.isna(timestamp_cell):
                continue

            parsed = parse_timestamp(timestamp_cell)
            if parsed:
                segments_to_remove.extend(parsed)
            else:
                errors.append(f"列{col_idx+1}: 无法解析时间戳 '{timestamp_cell}'")

        results.append({
            'row_index': idx + 2,  # Excel行号从1开始，加上表头
            'video_path': video_path,
            'segments_to_remove': segments_to_remove,
            'errors': errors
        })

    return df, results


def get_unique_output_path(input_path: str, output_dir: str = None) -> str:
    """
    生成唯一的输出文件路径

    Args:
        input_path: 输入视频路径
        output_dir: 输出目录，默认为输入文件所在目录

    Returns:
        输出文件路径
    """
    input_path = Path(input_path)

    if output_dir:
        output_dir = Path(output_dir)
    else:
        output_dir = input_path.parent

    # 生成输出文件名: original_name_edited.ext
    output_name = f"{input_path.stem}_edited{input_path.suffix}"
    output_path = output_dir / output_name

    # 如果文件已存在，添加数字后缀
    counter = 1
    while output_path.exists():
        output_name = f"{input_path.stem}_edited_{counter}{input_path.suffix}"
        output_path = output_dir / output_name
        counter += 1

    return str(output_path)
