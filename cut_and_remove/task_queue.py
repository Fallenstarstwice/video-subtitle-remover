"""
视频任务数据结构
用于在生产者和消费者之间传递任务信息
"""
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from enum import Enum


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"           # 等待处理
    PROCESSING = "processing"     # 正在处理
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败


@dataclass
class VideoTask:
    """
    视频处理任务数据类

    Attributes:
        original_video_path: 原始视频路径（从Excel读取）
        cut_video_path: cutoff后的视频路径（阶段1输出）
        final_output_path: 最终输出路径（阶段2输出）
        row_index: Excel行号（用于日志追踪）
        segments_to_remove: 要删除的时间段列表 [(start_sec, end_sec), ...]
        status: 任务状态
        error: 错误信息（如果失败）
        processing_stage: 当前处理阶段 (1=cutoff, 2=subtitle_remove)
    """
    original_video_path: str
    cut_video_path: str
    final_output_path: str
    row_index: int
    segments_to_remove: List[Tuple[float, float]]
    status: TaskStatus = field(default=TaskStatus.PENDING)
    error: Optional[str] = None
    processing_stage: int = 0  # 0=未开始, 1=cutoff完成, 2=去字幕完成

    def mark_processing(self, stage: int = 1):
        """标记任务为处理中"""
        self.status = TaskStatus.PROCESSING
        self.processing_stage = stage

    def mark_completed(self, stage: int = 2):
        """标记任务为完成"""
        self.status = TaskStatus.COMPLETED
        self.processing_stage = stage

    def mark_failed(self, error_msg: str):
        """标记任务为失败"""
        self.status = TaskStatus.FAILED
        self.error = error_msg

    def __str__(self):
        """字符串表示"""
        return (f"VideoTask[row={self.row_index}, "
                f"video={self.original_video_path}, "
                f"status={self.status.value}, "
                f"stage={self.processing_stage}]")


# 用于标记队列结束的哨兵对象
STOP_SIGNAL = object()
