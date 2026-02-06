"""
路径解析模块
处理视频文件的路径解析逻辑
"""
import os
from pathlib import Path
from typing import Optional
import pandas as pd


def resolve_video_path(file_path: str, excel_dir: str) -> Optional[str]:
    """
    解析视频文件路径

    优先级:
    1. 尝试绝对路径
    2. 尝试相对于Excel文件的路径
    3. 尝试相对于当前工作目录的路径

    Args:
        file_path: Excel中的视频路径
        excel_dir: Excel文件所在目录

    Returns:
        成功返回绝对路径，失败返回None
    """
    if not file_path or pd.isna(file_path):
        return None

    file_path = str(file_path).strip()

    # 1. 尝试绝对路径
    if os.path.isabs(file_path):
        if os.path.exists(file_path):
            return file_path
    else:
        # 2. 尝试相对于Excel文件的路径
        relative_to_excel = os.path.join(excel_dir, file_path)
        if os.path.exists(relative_to_excel):
            return os.path.abspath(relative_to_excel)

        # 3. 尝试相对于当前工作目录的路径
        if os.path.exists(file_path):
            return os.path.abspath(file_path)

    return None
