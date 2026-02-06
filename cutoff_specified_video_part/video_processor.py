"""
视频处理模块
使用FFmpeg删除视频中的指定片段
"""
import subprocess
import os
import sys
from typing import List, Tuple, Optional
from pathlib import Path

# 添加项目根目录到路径，以便导入backend模块
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

# 导入FFmpeg路径配置
from backend.config import FFMPEG_PATH


def get_video_duration(video_path: str) -> Optional[float]:
    """
    获取视频总时长（秒）

    Args:
        video_path: 视频文件路径

    Returns:
        视频时长（秒），失败返回None
    """
    try:
        # 使用 ffmpeg 获取视频时长（不依赖 ffprobe）
        cmd = [
            FFMPEG_PATH,
            '-i', video_path,
            '-f', 'null', '-'
        ]
        # 合并 stdout 和 stderr，从输出中解析时长
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        # 从 ffmpeg 输出中解析时长
        # 格式: Duration: HH:MM:SS.mm
        import re
        match = re.search(r'Duration:\s+(\d+):(\d+):(\d+\.\d+)', result.stdout)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            seconds = float(match.group(3))
            duration = hours * 3600 + minutes * 60 + seconds
            return duration
        else:
            print(f"无法从输出中解析视频时长")
            return None
    except Exception as e:
        print(f"获取视频时长失败: {e}")
        return None


def calculate_keep_segments(total_duration: float,
                           remove_segments: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """
    计算要保留的片段

    Args:
        total_duration: 视频总时长（秒）
        remove_segments: 要删除的片段列表 [(start, end), ...]

    Returns:
        要保留的片段列表 [(start, end), ...]
    """
    if not remove_segments:
        return [(0, total_duration)]

    # 按开始时间排序
    sorted_segments = sorted(remove_segments, key=lambda x: x[0])

    # 合并重叠的片段
    merged = []
    for start, end in sorted_segments:
        if not merged:
            merged.append([start, end])
        else:
            last_start, last_end = merged[-1]
            if start <= last_end:  # 有重叠
                merged[-1][1] = max(last_end, end)
            else:
                merged.append([start, end])

    # 计算要保留的片段
    keep_segments = []
    current_pos = 0

    for start, end in merged:
        if current_pos < start:
            keep_segments.append((current_pos, start))
        current_pos = max(current_pos, end)

    # 添加最后一个片段
    if current_pos < total_duration:
        keep_segments.append((current_pos, total_duration))

    return keep_segments


def format_seconds_to_ffmpeg(seconds: float) -> str:
    """
    将秒数转换为FFmpeg时间格式

    Args:
        seconds: 秒数

    Returns:
        格式化后的时间字符串，如 "00:01:13.500"
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def remove_video_segments(input_path: str,
                         segments_to_remove: List[Tuple[float, float]],
                         output_path: str) -> bool:
    """
    删除视频中的指定片段

    Args:
        input_path: 输入视频路径
        segments_to_remove: 要删除的片段列表 [(start_sec, end_sec), ...]
        output_path: 输出视频路径

    Returns:
        成功返回True，失败返回False
    """
    try:
        # 获取视频总时长
        total_duration = get_video_duration(input_path)
        if total_duration is None:
            return False

        # 计算要保留的片段
        keep_segments = calculate_keep_segments(total_duration, segments_to_remove)

        if not keep_segments:
            print("警告: 所有片段都被删除，将保留原始视频")
            import shutil
            shutil.copy(input_path, output_path)
            return True

        if len(keep_segments) == 1:
            # 只有一个片段，直接剪切（使用 stream copy，速度快）
            start, end = keep_segments[0]
            duration = end - start
            start_time = format_seconds_to_ffmpeg(start)

            cmd = [
                FFMPEG_PATH,
                '-ss', start_time,
                '-t', format_seconds_to_ffmpeg(duration),
                '-i', input_path,
                '-c', 'copy',
                output_path,
                '-y'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"FFmpeg 错误: {result.stderr}")
                return False
        else:
            # 多个片段，使用 concat filter 拼接
            # 构建 filter_complex 图
            filter_parts = []
            stream_inputs = []

            for i, (start, end) in enumerate(keep_segments):
                duration = end - start
                # 视频流：trim + setpts
                filter_parts.append(
                    f"[0:v]trim={start}:{end},setpts=PTS-STARTPTS[v{i}];"
                )
                # 音频流：atrim + asetpts
                filter_parts.append(
                    f"[0:a]atrim={start}:{end},asetpts=PTS-STARTPTS[a{i}];"
                )
                stream_inputs.extend([f"[v{i}]", f"[a{i}]"])

            # concat filter
            n = len(keep_segments)
            filter_complex = "".join(filter_parts) + f"{''.join(stream_inputs)}concat=n={n}:v=1:a=1[outv][outa]"

            # 使用 subprocess 直接调用 FFmpeg（更可靠）
            cmd = [
                FFMPEG_PATH,
                '-i', input_path,
                '-filter_complex', filter_complex,
                '-map', '[outv]',
                '-map', '[outa]',
                output_path,
                '-y'  # 覆盖输出文件
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"FFmpeg 错误: {result.stderr}")
                return False

        return True

    except Exception as e:
        print(f"处理视频时发生错误: {e}")
        return False
