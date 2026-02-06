"""
Cut and Remove 模块
结合视频片段删除和字幕去除功能

主要组件:
- main: 主入口
- producer: 视频片段删除生产者
- consumer: 字幕去除消费者
- task_queue: 任务数据结构
- config_loader: 配置加载器

使用示例:
    from cut_and_remove import main
    main.main()
"""
from .task_queue import VideoTask, TaskStatus, STOP_SIGNAL
from .config_loader import CutAndRemoveConfig, load_config
from .producer import VideoProducer, run_producer
from .consumer import VideoConsumer, run_consumer

__version__ = '1.0.0'
__all__ = [
    'VideoTask',
    'TaskStatus',
    'STOP_SIGNAL',
    'CutAndRemoveConfig',
    'load_config',
    'VideoProducer',
    'run_producer',
    'VideoConsumer',
    'run_consumer',
]
