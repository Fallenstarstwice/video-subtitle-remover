"""
视频片段删除工具
从Excel文件读取视频路径和时间戳，使用FFmpeg删除指定片段
"""
import sys
import argparse
from pathlib import Path
from excel_handler import read_excel_file, get_unique_output_path
from path_resolver import resolve_video_path
from video_processor import remove_video_segments, format_seconds_to_ffmpeg
from decorators import print_timing_decorator
import pandas as pd


@print_timing_decorator
def process_video(row_data: dict, excel_dir: str, output_dir: str = None) -> dict:
    """
    处理单个视频

    Args:
        row_data: 从Excel解析的数据
        excel_dir: Excel文件所在目录
        output_dir: 输出目录

    Returns:
        处理结果字典
    """
    video_path_str = row_data['video_path']
    segments = row_data['segments_to_remove']
    row_index = row_data['row_index']
    errors = row_data['errors']

    result = {
        'row': row_index,
        'video_path': video_path_str,
        'success': False,
        'error': None,
        'output_path': None
    }

    # 检查是否有解析错误
    if errors:
        result['error'] = f"时间戳解析错误: {'; '.join(errors)}"
        return result

    # 检查是否有时间戳
    if not segments:
        result['error'] = "没有时间戳数据"
        return result

    # 解析视频路径
    video_path = resolve_video_path(video_path_str, excel_dir)

    if video_path is None:
        result['error'] = f"找不到视频文件: {video_path_str}"
        return result

    # 生成输出路径
    output_path = get_unique_output_path(video_path, output_dir)

    # 删除片段
    print(f"\n[行{row_index}] 正在处理: {Path(video_path).name}")
    print(f"  要删除的片段: {len(segments)} 个")
    for start, end in segments:
        print(f"    - {format_seconds_to_ffmpeg(start)} ~ {format_seconds_to_ffmpeg(end)}")

    success = remove_video_segments(video_path, segments, output_path)

    result['success'] = success
    result['output_path'] = output_path

    if success:
        print(f"  ✓ 成功! 输出: {output_path}")
    else:
        result['error'] = "视频处理失败"

    return result


def main():
    parser = argparse.ArgumentParser(
        description='从Excel文件读取视频路径和时间戳，删除视频中的指定片段'
    )
    parser.add_argument(
        'excel_file',
        help='Excel文件路径'
    )
    parser.add_argument(
        '-o', '--output',
        help='输出目录（默认与原视频同目录）',
        default=None
    )

    args = parser.parse_args()

    excel_path = args.excel_file
    output_dir = args.output

    # 检查Excel文件是否存在
    if not Path(excel_path).exists():
        print(f"错误: 找不到Excel文件: {excel_path}")
        sys.exit(1)

    excel_dir = str(Path(excel_path).parent)

    print("=" * 60)
    print("视频片段删除工具")
    print("=" * 60)
    print(f"Excel文件: {excel_path}")
    if output_dir:
        print(f"输出目录: {output_dir}")
    print("=" * 60)

    # 读取Excel
    print("\n正在读取Excel文件...")
    try:
        _, results = read_excel_file(excel_path)
        print(f"✓ 成功读取 {len(results)} 行数据")
    except Exception as e:
        print(f"✗ 读取Excel失败: {e}")
        sys.exit(1)

    # 处理每个视频
    success_count = 0
    failed_count = 0
    failed_videos = []
    total_processing_time = 0
    video_times = []

    for row_data in results:
        # 跳过空行
        if pd.isna(row_data['video_path']) or not row_data['video_path']:
            continue

        result = process_video(row_data, excel_dir, output_dir)

        # 收集时间统计
        if result['success'] and 'processing_time' in result:
            total_processing_time += result['processing_time']
            video_times.append({
                'row': result['row'],
                'video': Path(result['video_path']).name,
                'time': result['processing_time']
            })

        if result['success']:
            success_count += 1
        else:
            failed_count += 1
            failed_videos.append(result)

    # 输出统计
    print("\n" + "=" * 60)
    print("处理完成!")
    print("=" * 60)
    print(f"成功: {success_count} 个")
    print(f"失败: {failed_count} 个")

    # 添加时间统计
    if success_count > 0:
        avg_time = total_processing_time / success_count
        print(f"\n⏱ 时间统计:")
        print(f"  总处理时间: {total_processing_time:.2f}秒")
        print(f"  平均每个视频: {avg_time:.2f}秒")

        # 显示最慢和最快的视频
        if video_times:
            fastest = min(video_times, key=lambda x: x['time'])
            slowest = max(video_times, key=lambda x: x['time'])
            print(f"  最快: {fastest['video']} (行{fastest['row']}, {fastest['time']:.2f}秒)")
            print(f"  最慢: {slowest['video']} (行{slowest['row']}, {slowest['time']:.2f}秒)")

    if failed_videos:
        print("\n失败列表:")
        for video in failed_videos:
            print(f"  [行{video['row']}] {video['video_path']}")
            print(f"    原因: {video['error']}")

    print("=" * 60)


if __name__ == "__main__":
    main()
