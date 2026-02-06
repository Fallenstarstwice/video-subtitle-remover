"""
生产者模块
从Excel读取视频任务，调用cutoff模块删除指定片段，将处理后的视频放入队列
"""
import os
import sys
import pandas as pd
import logging
from pathlib import Path
from typing import Optional
from queue import Queue
from tqdm import tqdm

# 添加cutoff模块路径
current_dir = Path(__file__).parent
project_root = current_dir.parent
cutoff_dir = project_root / 'cutoff_specified_video_part'
sys.path.insert(0, str(cutoff_dir))

# 导入cutoff模块的函数
from excel_handler import read_excel_file, get_unique_output_path
from path_resolver import resolve_video_path
from video_processor import remove_video_segments, format_seconds_to_ffmpeg

# 导入任务队列模块
try:
    # 尝试相对导入（作为包使用时）
    from .task_queue import VideoTask, TaskStatus, STOP_SIGNAL
    from .config_loader import CutAndRemoveConfig
except ImportError:
    # 回退到绝对导入（直接运行时）
    from task_queue import VideoTask, TaskStatus, STOP_SIGNAL
    from config_loader import CutAndRemoveConfig


class VideoProducer:
    """
    视频处理生产者

    功能:
    1. 从Excel读取任务列表
    2. 调用cutoff模块删除视频片段
    3. 将处理成功的视频任务放入队列
    """

    def __init__(
        self,
        excel_path: str,
        task_queue: Queue,
        config: CutAndRemoveConfig,
        ffmpeg_path: str
    ):
        """
        初始化生产者

        Args:
            excel_path: Excel文件路径
            task_queue: 任务队列
            config: 配置对象
            ffmpeg_path: FFmpeg可执行文件路径
        """
        self.excel_path = Path(excel_path)
        self.task_queue = task_queue
        self.config = config
        self.ffmpeg_path = ffmpeg_path
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger('VideoProducer')
        logger.setLevel(logging.DEBUG if self.config.verbose else logging.INFO)

        # 避免重复添加handler
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '[Producer] %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _process_video(self, row_data: dict, excel_dir: str) -> Optional[VideoTask]:
        """
        处理单个视频（删除指定片段）

        Args:
            row_data: 从Excel解析的数据
            excel_dir: Excel文件所在目录

        Returns:
            VideoTask: 处理成功返回任务对象，失败返回None
        """
        video_path_str = row_data['video_path']
        segments = row_data['segments_to_remove']
        row_index = row_data['row_index']
        errors = row_data['errors']

        # 检查是否有解析错误
        if errors:
            self.logger.error(
                f"[行{row_index}] {video_path_str} - 时间戳解析错误: {'; '.join(errors)}"
            )
            return None

        # 检查是否有时间戳
        if not segments:
            self.logger.warning(f"[行{row_index}] {video_path_str} - 没有时间戳数据")
            return None

        # 解析视频路径
        video_path = resolve_video_path(video_path_str, excel_dir)
        if video_path is None:
            self.logger.error(f"[行{row_index}] 找不到视频文件: {video_path_str}")
            return None

        # 生成中间视频路径（cutoff后的输出）
        intermediate_name = f"{Path(video_path).stem}_cut{Path(video_path).suffix}"
        cut_video_path = str(Path(self.config.intermediate_dir) / intermediate_name)

        # 生成最终输出路径（去字幕后）
        final_name = f"{Path(video_path).stem}_no_sub{Path(video_path).suffix}"
        final_output_path = str(Path(self.config.final_dir) / final_name)

        # 调用cutoff模块删除片段
        self.logger.info(f"[行{row_index}] 正在处理: {Path(video_path).name}")
        if self.config.verbose:
            self.logger.debug(f"  要删除的片段: {len(segments)} 个")
            for start, end in segments:
                self.logger.debug(f"    - {format_seconds_to_ffmpeg(start)} ~ {format_seconds_to_ffmpeg(end)}")

        # 注意: 这里需要修改 video_processor.py 以支持自定义 ffmpeg 路径
        # 临时方案: 设置环境变量
        original_env = os.environ.get('FFMPEG_PATH')
        os.environ['FFMPEG_PATH'] = self.ffmpeg_path

        try:
            success = remove_video_segments(video_path, segments, cut_video_path)
        finally:
            # 恢复环境变量
            if original_env is not None:
                os.environ['FFMPEG_PATH'] = original_env
            elif 'FFMPEG_PATH' in os.environ:
                del os.environ['FFMPEG_PATH']

        if not success:
            self.logger.error(f"[行{row_index}] {Path(video_path).name} - 视频处理失败")
            return None

        self.logger.info(f"[行{row_index}] ✓ Cutoff完成: {cut_video_path}")

        # 创建任务对象
        task = VideoTask(
            original_video_path=video_path,
            cut_video_path=cut_video_path,
            final_output_path=final_output_path,
            row_index=row_index,
            segments_to_remove=segments,
            status=TaskStatus.COMPLETED,
            processing_stage=1  # 阶段1完成
        )

        return task

    def run(self) -> dict:
        """
        运行生产者主流程

        Returns:
            dict: 处理统计信息
                {
                    'total': int,          # 总任务数
                    'success': int,        # 成功数
                    'failed': int,         # 失败数
                    'failed_tasks': list   # 失败任务列表
                }
        """
        self.logger.info("=" * 60)
        self.logger.info("视频片段删除（阶段1）")
        self.logger.info("=" * 60)
        self.logger.info(f"Excel文件: {self.excel_path}")
        self.logger.info(f"输出目录: {self.config.intermediate_dir}")
        self.logger.info("=" * 60)

        # 检查Excel文件是否存在
        if not self.excel_path.exists():
            self.logger.error(f"Excel文件不存在: {self.excel_path}")
            raise FileNotFoundError(f"Excel文件不存在: {self.excel_path}")

        excel_dir = str(self.excel_path.parent)

        # 读取Excel
        self.logger.info("\n正在读取Excel文件...")
        try:
            _, results = read_excel_file(str(self.excel_path))
            self.logger.info(f"✓ 成功读取 {len(results)} 行数据")
        except Exception as e:
            self.logger.error(f"✗ 读取Excel失败: {e}")
            raise

        # 过滤空行
        valid_results = [
            r for r in results
            if not pd.isna(r['video_path']) and r['video_path']
        ]

        # 处理每个视频
        success_count = 0
        failed_count = 0
        failed_tasks = []

        with tqdm(total=len(valid_results), unit='video', desc='[Producer] Cutting',
                  position=0, file=sys.__stdout__) as pbar:
            for row_data in valid_results:
                task = self._process_video(row_data, excel_dir)

                if task:
                    # 将任务放入队列
                    self.task_queue.put(task)
                    success_count += 1
                    pbar.set_postfix({'queued': self.task_queue.qsize()})
                else:
                    failed_count += 1
                    failed_tasks.append({
                        'row': row_data['row_index'],
                        'video': row_data['video_path'],
                        'error': '处理失败'
                    })

                pbar.update(1)

        # 发送结束信号
        self.task_queue.put(STOP_SIGNAL)

        # 输出统计
        self.logger.info("\n" + "=" * 60)
        self.logger.info("[Producer] 处理完成!")
        self.logger.info("=" * 60)
        self.logger.info(f"成功: {success_count} 个")
        self.logger.info(f"失败: {failed_count} 个")
        self.logger.info(f"队列中待处理: {success_count} 个")
        self.logger.info("=" * 60)

        return {
            'total': len(valid_results),
            'success': success_count,
            'failed': failed_count,
            'failed_tasks': failed_tasks
        }


def run_producer(
    excel_path: str,
    task_queue: Queue,
    config: CutAndRemoveConfig,
    ffmpeg_path: str
) -> dict:
    """
    运行生产者的便捷函数

    Args:
        excel_path: Excel文件路径
        task_queue: 任务队列
        config: 配置对象
        ffmpeg_path: FFmpeg可执行文件路径

    Returns:
        dict: 处理统计信息
    """
    producer = VideoProducer(excel_path, task_queue, config, ffmpeg_path)
    return producer.run()
