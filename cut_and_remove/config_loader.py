"""
配置加载器
从YAML文件加载 cut_and_remove 模块的配置
"""
import os
import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class CutAndRemoveConfig:
    """
    Cut and Remove 模块配置

    Attributes:
        intermediate_dir: 中间视频输出目录（阶段1：cutoff后的视频）
        final_dir: 最终输出目录（阶段2：去字幕后的视频）
        keep_intermediate: 是否保留中间文件
        max_queue_size: 队列最大长度
        verbose: 是否显示详细日志
        subtitle_area_config: 字幕区域配置文件路径
        use_builtin_ffmpeg: 是否使用项目内ffmpeg
        custom_ffmpeg_path: 自定义ffmpeg路径
    """
    intermediate_dir: str
    final_dir: str
    keep_intermediate: bool
    max_queue_size: int
    verbose: bool
    subtitle_area_config: str
    use_builtin_ffmpeg: bool
    custom_ffmpeg_path: str

    @classmethod
    def from_yaml(cls, yaml_path: str) -> 'CutAndRemoveConfig':
        """
        从YAML文件加载配置

        Args:
            yaml_path: YAML配置文件路径

        Returns:
            CutAndRemoveConfig 配置对象

        Raises:
            FileNotFoundError: 配置文件不存在
            KeyError: 配置项缺失
        """
        yaml_path = Path(yaml_path)

        if not yaml_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {yaml_path}")

        with open(yaml_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        # 解析配置
        output_config = config_data.get('output', {})
        processing_config = config_data.get('processing', {})
        ffmpeg_config = config_data.get('ffmpeg', {})

        # 获取项目根目录（假设配置文件在 cut_and_remove/ 目录下）
        project_root = yaml_path.parent.parent

        # 构建绝对路径
        intermediate_dir = output_config.get('intermediate_dir', 'output/intermediate')
        final_dir = output_config.get('final_dir', 'output/final')

        # 如果是相对路径，转换为绝对路径
        if not Path(intermediate_dir).is_absolute():
            intermediate_dir = str(project_root / intermediate_dir)
        if not Path(final_dir).is_absolute():
            final_dir = str(project_root / final_dir)

        # 创建输出目录
        os.makedirs(intermediate_dir, exist_ok=True)
        os.makedirs(final_dir, exist_ok=True)

        return cls(
            intermediate_dir=intermediate_dir,
            final_dir=final_dir,
            keep_intermediate=output_config.get('keep_intermediate', False),
            max_queue_size=processing_config.get('max_queue_size', 10),
            verbose=processing_config.get('verbose', True),
            subtitle_area_config=processing_config.get(
                'subtitle_area_config',
                str(project_root / 'backend' / 'subtitle_area.yaml')
            ),
            use_builtin_ffmpeg=ffmpeg_config.get('use_builtin', True),
            custom_ffmpeg_path=ffmpeg_config.get('custom_path', '')
        )

    def validate(self) -> bool:
        """
        验证配置的有效性

        Returns:
            bool: 配置是否有效
        """
        # 检查字幕区域配置文件是否存在
        if not Path(self.subtitle_area_config).exists():
            print(f"警告: 字幕区域配置文件不存在: {self.subtitle_area_config}")
            return False

        # 如果不使用内置ffmpeg，检查自定义路径是否存在
        if not self.use_builtin_ffmpeg:
            if not self.custom_ffmpeg_path or not Path(self.custom_ffmpeg_path).exists():
                print(f"警告: 自定义FFmpeg路径无效: {self.custom_ffmpeg_path}")
                return False

        return True

    def get_ffmpeg_path(self, builtin_ffmpeg_path: Optional[str] = None) -> str:
        """
        获取FFmpeg可执行文件路径

        Args:
            builtin_ffmpeg_path: 项目内ffmpeg路径（从backend.config导入）

        Returns:
            str: FFmpeg可执行文件的完整路径
        """
        if self.use_builtin_ffmpeg:
            if builtin_ffmpeg_path and Path(builtin_ffmpeg_path).exists():
                return builtin_ffmpeg_path
            else:
                raise FileNotFoundError(
                    f"项目内FFmpeg不存在: {builtin_ffmpeg_path}\n"
                    f"请检查 backend/config.py 中的 FFMPEG_PATH 配置"
                )
        else:
            return self.custom_ffmpeg_path


def load_config(config_path: Optional[str] = None) -> CutAndRemoveConfig:
    """
    加载配置文件的便捷函数

    Args:
        config_path: 配置文件路径，如果为None则使用默认路径

    Returns:
        CutAndRemoveConfig 配置对象
    """
    if config_path is None:
        # 默认配置文件路径
        current_dir = Path(__file__).parent
        config_path = str(current_dir / 'config.yaml')

    config = CutAndRemoveConfig.from_yaml(config_path)

    # 验证配置
    if not config.validate():
        raise ValueError("配置验证失败，请检查配置文件")

    return config
