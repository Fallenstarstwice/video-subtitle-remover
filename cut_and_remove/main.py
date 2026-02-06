"""
Cut and Remove - 主入口模块
结合视频片段删除和字幕去除功能，实现完整的视频处理流水线

使用方法:
    python cut_and_remove/main.py excel_file.xlsx [选项]

示例:
    python cut_and_remove/main.py videos.xlsx
    python cut_and_remove/main.py videos.xlsx --output custom_output
    python cut_and_remove/main.py videos.xlsx --keep-temp --verbose
"""
import sys
import argparse
import time
import threading
from pathlib import Path
from queue import Queue
from typing import Optional

# 添加项目根目录到路径
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

# 导入backend配置（用于FFmpeg路径）
from backend.config import FFMPEG_PATH

# 导入cut_and_remove模块
import sys
from pathlib import Path

# 添加当前目录到路径以确保能导入模块
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from config_loader import load_config, CutAndRemoveConfig
from producer import run_producer
from consumer import run_consumer


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='视频片段删除和字幕去除流水线处理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s videos.xlsx
  %(prog)s videos.xlsx --output custom_output
  %(prog)s videos.xlsx --keep-temp --verbose
  %(prog)s videos.xlsx --config custom_config.yaml
        """
    )

    parser.add_argument(
        'excel_file',
        help='Excel文件路径（包含视频路径和时间戳信息）'
    )

    parser.add_argument(
        '--config', '-c',
        help='配置文件路径（默认: ./cut_and_remove/config.yaml）',
        default=None
    )

    parser.add_argument(
        '--output', '-o',
        help='最终输出目录（会覆盖配置文件中的设置）',
        default=None
    )

    parser.add_argument(
        '--intermediate-dir',
        help='中间视频输出目录（会覆盖配置文件中的设置）',
        default=None
    )

    parser.add_argument(
        '--keep-temp',
        help='保留中间文件（会覆盖配置文件中的设置）',
        action='store_true'
    )

    parser.add_argument(
        '--verbose', '-v',
        help='显示详细日志',
        action='store_true'
    )

    return parser.parse_args()


def load_and_validate_config(args) -> CutAndRemoveConfig:
    """
    加载并验证配置

    Args:
        args: 命令行参数

    Returns:
        CutAndRemoveConfig: 配置对象
    """
    # 确定配置文件路径
    if args.config:
        config_path = args.config
    else:
        # 使用默认配置文件
        config_path = str(current_dir / 'config.yaml')

    # 加载配置
    config = load_config(config_path)

    # 命令行参数覆盖配置文件
    if args.output:
        config.final_dir = args.output
        # 确保输出目录存在
        Path(config.final_dir).mkdir(parents=True, exist_ok=True)

    if args.intermediate_dir:
        config.intermediate_dir = args.intermediate_dir
        Path(config.intermediate_dir).mkdir(parents=True, exist_ok=True)

    if args.keep_temp:
        config.keep_intermediate = True

    if args.verbose:
        config.verbose = True

    return config


def print_statistics(producer_stats: dict, consumer_stats: dict, total_time: float):
    """
    打印处理统计信息

    Args:
        producer_stats: 生产者统计信息
        consumer_stats: 消费者统计信息
        total_time: 总处理时间（秒）
    """
    print("\n" + "=" * 60)
    print("总体统计")
    print("=" * 60)
    print(f"总处理时间: {total_time:.2f}秒 ({total_time/60:.2f}分钟)")

    print("\n阶段1 - 视频片段删除:")
    print(f"  总任务数: {producer_stats['total']} 个")
    print(f"  成功: {producer_stats['success']} 个")
    print(f"  失败: {producer_stats['failed']} 个")

    print("\n阶段2 - 字幕去除:")
    print(f"  总任务数: {consumer_stats['total']} 个")
    print(f"  成功: {consumer_stats['success']} 个")
    print(f"  失败: {consumer_stats['failed']} 个")

    if consumer_stats['total'] > 0:
        avg_time = total_time / consumer_stats['total']
        print(f"  平均每个视频: {avg_time:.2f}秒")

    # 显示失败任务
    all_failed = (
        producer_stats.get('failed_tasks', []) +
        consumer_stats.get('failed_tasks', [])
    )

    if all_failed:
        print("\n失败列表:")
        for task in all_failed:
            print(f"  [行{task['row']}] {task['video']}")
            print(f"    原因: {task['error']}")

    print("\n最终输出目录: " + Path(producer_stats.get('output_dir', 'output/final')).as_posix())
    print("=" * 60)


def save_failed_tasks_log(
    producer_stats: dict,
    consumer_stats: dict,
    output_dir: str
):
    """
    保存失败任务日志到文件

    Args:
        producer_stats: 生产者统计信息
        consumer_stats: 消费者统计信息
        output_dir: 输出目录
    """
    all_failed = (
        producer_stats.get('failed_tasks', []) +
        consumer_stats.get('failed_tasks', [])
    )

    if not all_failed:
        return

    log_path = Path(output_dir) / 'failed_tasks.txt'

    with open(log_path, 'w', encoding='utf-8') as f:
        f.write("失败任务列表\n")
        f.write("=" * 60 + "\n\n")

        for task in all_failed:
            f.write(f"[行{task['row']}] {task['video']}\n")
            f.write(f"  失败原因: {task['error']}\n\n")

    print(f"\n失败任务日志已保存到: {log_path}")


def main():
    """主函数"""
    # 解析命令行参数
    args = parse_arguments()

    # 检查Excel文件是否存在
    excel_path = Path(args.excel_file)
    if not excel_path.exists():
        print(f"错误: Excel文件不存在: {args.excel_file}")
        sys.exit(1)

    # 加载配置
    try:
        config = load_and_validate_config(args)
    except Exception as e:
        print(f"错误: 加载配置失败: {e}")
        sys.exit(1)

    # 打印启动信息
    print("=" * 60)
    print("Cut and Remove - 视频片段删除和字幕去除")
    print("=" * 60)
    print(f"Excel文件: {excel_path}")
    print(f"中间目录: {config.intermediate_dir}")
    print(f"最终目录: {config.final_dir}")
    print(f"保留中间文件: {'是' if config.keep_intermediate else '否'}")
    print(f"FFmpeg路径: {FFMPEG_PATH}")
    print("=" * 60)

    # 创建任务队列
    task_queue = Queue(maxsize=config.max_queue_size)

    # 记录开始时间
    start_time = time.time()

    # 用于存储线程执行结果的容器
    producer_stats = {}
    consumer_stats = {}
    producer_error = None
    consumer_error = None

    try:
        # 创建并启动生产者线程和消费者线程（并发执行）
        print("\n启动并发处理...")
        print(f"- 阶段1 (Cutoff): 将视频片段删除后的视频放入队列")
        print(f"- 阶段2 (AI去字幕): 从队列取出视频并去除字幕")
        print(f"- 队列大小: {config.max_queue_size}\n")

        # 创建生产者线程
        producer_thread = threading.Thread(
            target=lambda: producer_stats.update(
                run_producer(str(excel_path), task_queue, config, FFMPEG_PATH)
            ),
            name="Producer-Thread"
        )

        # 创建消费者线程
        consumer_thread = threading.Thread(
            target=lambda: consumer_stats.update(
                run_consumer(task_queue, config)
            ),
            name="Consumer-Thread"
        )

        # 启动两个线程
        producer_thread.start()
        consumer_thread.start()

        # 等待两个线程完成
        producer_thread.join()
        consumer_thread.join()

        # 计算总耗时
        total_time = time.time() - start_time

        # 添加输出目录到统计信息
        producer_stats['output_dir'] = config.final_dir

        # 打印统计信息
        print_statistics(producer_stats, consumer_stats, total_time)

        # 保存失败任务日志
        save_failed_tasks_log(producer_stats, consumer_stats, config.final_dir)

        # 返回码
        failed_count = producer_stats.get('failed', 0) + consumer_stats.get('failed', 0)
        if failed_count > 0:
            sys.exit(1)
        else:
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n用户中断处理")
        sys.exit(130)
    except Exception as e:
        print(f"\n错误: 处理过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    multiprocessing = None
    try:
        import multiprocessing
        multiprocessing.set_start_method("spawn")
    except:
        pass

    main()
