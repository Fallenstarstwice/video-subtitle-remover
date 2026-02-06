"""
装饰器模块
提供计时等通用装饰器功能
"""
import time
from functools import wraps


def timing_decorator(func):
    """
    计时装饰器，统计函数执行时间并添加到返回结果的字典中

    Usage:
        @timing_decorator
        def process_video(...) -> dict:
            ...
            return result

    如果返回值是字典，会自动添加 'processing_time' 键
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()

        # 将耗时添加到返回结果中
        if isinstance(result, dict):
            result['processing_time'] = end_time - start_time

        return result
    return wrapper


def print_timing_decorator(func):
    """
    计时并自动打印的装饰器

    在函数执行后自动打印耗时，同时将耗时添加到返回结果中
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()

        elapsed = end_time - start_time
        print(f"  ⏱ 处理耗时: {elapsed:.2f}秒")

        # 同时也将耗时添加到结果中
        if isinstance(result, dict):
            result['processing_time'] = elapsed

        return result
    return wrapper
