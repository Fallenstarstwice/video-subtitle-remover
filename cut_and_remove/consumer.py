"""
消费者模块
从队列获取视频任务，调用backend模块去除字幕，保存最终视频
"""
import os
import sys
import logging
import time
from pathlib import Path
from typing import Optional
from queue import Queue

# 添加backend模块路径
current_dir = Path(__file__).parent
project_root = current_dir.parent
backend_dir = project_root / 'backend'
sys.path.insert(0, str(backend_dir))

# 导入backend模块
from main import SubtitleRemover, read_subtitle_area_from_config
from tools.common_tools import is_video_or_image

# 导入任务队列模块
try:
    # 尝试相对导入（作为包使用时）
    from .task_queue import VideoTask, TaskStatus, STOP_SIGNAL
    from .config_loader import CutAndRemoveConfig
except ImportError:
    # 回退到绝对导入（直接运行时）
    from task_queue import VideoTask, TaskStatus, STOP_SIGNAL
    from config_loader import CutAndRemoveConfig


class VideoConsumer:
    """
    视频处理消费者

    功能:
    1. 从队列获取视频任务
    2. 调用backend模块去除字幕
    3. 保存最终视频
    4. 可选地删除中间文件
    """

    def __init__(
        self,
        task_queue: Queue,
        config: CutAndRemoveConfig
    ):
        """
        初始化消费者

        Args:
            task_queue: 任务队列
            config: 配置对象
        """
        self.task_queue = task_queue
        self.config = config
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger('VideoConsumer')
        logger.setLevel(logging.DEBUG if self.config.verbose else logging.INFO)

        # 避免重复添加handler
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '[Consumer] %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _get_subtitle_area(self, video_path: str):
        """
        从配置文件读取字幕区域

        Args:
            video_path: 视频文件路径（用于获取视频尺寸）

        Returns:
            tuple: (ymin, ymax, xmin, xmax) 或 None
        """
        try:
            # 传递 verbose=False 以禁用输出，避免干扰进度条
            sub_area = read_subtitle_area_from_config(video_path, verbose=False)
            return sub_area
        except Exception as e:
            self.logger.warning(f"读取字幕区域配置失败: {e}")
            self.logger.info("将使用全屏字幕检测")
            return None

    def _process_video(self, task: VideoTask) -> bool:
        """
        处理单个视频（去除字幕）

        Args:
            task: 视频任务对象

        Returns:
            bool: 处理成功返回True，失败返回False
        """
        try:
            # 读取字幕区域配置
            sub_area = self._get_subtitle_area(task.cut_video_path)

            # 创建字幕去除对象
            # 注意：不禁用进度条，让backend显示该视频的处理进度
            video_name = Path(task.cut_video_path).name
            remover = SubtitleRemover(
                vd_path=task.cut_video_path,
                sub_area=sub_area,
                gui_mode=False,
                disable_progress=False,  # 让backend显示进度条
                show_processing_info=False  # 不显示处理信息，避免干扰进度条
            )

            # 设置当前处理信息（视频名称），会在进度条postfix中显示
            remover.current_processing_info = f"video={video_name}"

            # 执行去字幕处理
            start_time = time.time()

            remover.run()
            elapsed_time = time.time() - start_time

            # remover.run() 会生成 _no_sub.mp4 文件
            # 需要移动到我们指定的最终输出路径
            generated_output = remover.video_out_name

            if Path(generated_output).exists():
                # 如果生成的文件路径与我们期望的不同，则移动
                if generated_output != task.final_output_path:
                    import shutil
                    shutil.move(generated_output, task.final_output_path)
            else:
                self.logger.error(f"生成的输出文件不存在: {generated_output}")
                return False

            print(f"\n[行{task.row_index}] ✓ 完成: {Path(task.final_output_path).name} (耗时: {elapsed_time:.1f}秒)")

            # 如果不保留中间文件，删除cutoff后的视频
            if not self.config.keep_intermediate:
                try:
                    os.remove(task.cut_video_path)
                except Exception as e:
                    self.logger.warning(f"删除中间文件失败: {e}")

            return True

        except Exception as e:
            print(f"[行{task.row_index}] ✗ 失败: {Path(task.cut_video_path).name} - {e}")
            return False

    def run(self) -> dict:
        """
        运行消费者主流程

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
        self.logger.info("字幕去除（阶段2）")
        self.logger.info("=" * 60)
        self.logger.info(f"输出目录: {self.config.final_dir}")
        self.logger.info(f"保留中间文件: {'是' if self.config.keep_intermediate else '否'}")
        self.logger.info("=" * 60)

        success_count = 0
        failed_count = 0
        failed_tasks = []
        processed_count = 0

        # 从队列获取任务并处理
        while True:
            task = self.task_queue.get()

            # 检查结束信号
            if task is STOP_SIGNAL:
                self.task_queue.task_done()
                break

            processed_count += 1

            # 处理视频（每个视频会显示自己的进度条）
            success = self._process_video(task)

            if success:
                success_count += 1
            else:
                failed_count += 1
                failed_tasks.append({
                    'row': task.row_index,
                    'video': Path(task.cut_video_path).name,
                    'error': '去字幕处理失败'
                })

            self.task_queue.task_done()

        # 输出统计
        self.logger.info("\n" + "=" * 60)
        self.logger.info("[Consumer] 处理完成!")
        self.logger.info("=" * 60)
        self.logger.info(f"成功: {success_count} 个")
        self.logger.info(f"失败: {failed_count} 个")
        self.logger.info("=" * 60)

        return {
            'total': processed_count,
            'success': success_count,
            'failed': failed_count,
            'failed_tasks': failed_tasks
        }


def run_consumer(
    task_queue: Queue,
    config: CutAndRemoveConfig
) -> dict:
    """
    运行消费者的便捷函数

    Args:
        task_queue: 任务队列
        config: 配置对象

    Returns:
        dict: 处理统计信息
    """
    consumer = VideoConsumer(task_queue, config)
    return consumer.run()
