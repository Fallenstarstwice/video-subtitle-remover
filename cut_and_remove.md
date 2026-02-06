# Cut and Remove 模块使用文档

结合视频片段删除和字幕去除功能的完整视频处理流水线

---

## 📋 目录

- [功能概述](#功能概述)
- [文件结构](#文件结构)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [命令行参数](#命令行参数)
- [处理流程](#处理流程)
- [输出结果](#输出结果)
- [注意事项](#注意事项)
- [常见问题](#常见问题)

---

## 功能概述

`cut_and_remove` 模块将两个视频处理功能结合在一起：

1. **视频片段删除**：使用FFmpeg删除视频中的指定片段（基于Excel中的时间戳）
2. **字幕去除**：使用AI模型自动检测并去除视频中的字幕

### 核心特性

✅ 统一使用项目内FFmpeg（无需额外安装）
✅ YAML配置文件，灵活可配置
✅ 默认输出路径为 `output` 目录
✅ 生产者-消费者模式，解耦处理流程
✅ 完善的错误处理和日志记录
✅ 命令行参数覆盖配置
✅ 自动清理中间文件（可选）
✅ 进度条显示（tqdm）

---

## 文件结构

```
cut_and_remove/
├── __init__.py              # 模块初始化文件
├── main.py                  # 主入口（命令行接口）
├── config.yaml              # 配置文件
├── config_loader.py         # YAML配置加载器
├── producer.py              # 生产者（视频片段删除）
├── consumer.py              # 消费者（字幕去除）
└── task_queue.py            # 任务数据结构定义
```

### 相关文件修改

- `cutoff_specified_video_part/video_processor.py`：统一使用项目内FFmpeg

---

## 快速开始

### 基本用法

```bash
# 进入项目根目录
cd ~/video-subtitle-remover

# 运行处理（Excel文件包含视频路径和时间戳）
python cut_and_remove/main.py your_videos.xlsx
```

### 使用示例

```bash
# 基本使用
python cut_and_remove/main.py videos.xlsx

# 自定义输出目录
python cut_and_remove/main.py videos.xlsx --output D:/my_output

# 保留中间文件并显示详细日志
python cut_and_remove/main.py videos.xlsx --keep-temp --verbose

# 使用自定义配置文件
python cut_and_remove/main.py videos.xlsx --config my_config.yaml
```

---

## 配置说明

配置文件位于 `cut_and_remove/config.yaml`

```yaml
# ============================================
# 输出路径配置
# ============================================
output:
  # 中间视频输出目录（阶段1：cutoff删除片段后的视频）
  intermediate_dir: "output/intermediate"

  # 最终输出目录（阶段2：去除字幕后的视频）
  final_dir: "output/final"

  # 是否保留中间文件
  keep_intermediate: false


# ============================================
# 处理配置
# ============================================
processing:
  # 队列最大长度（控制内存中最多缓存多少个待处理的视频任务）
  max_queue_size: 10

  # 是否显示详细日志
  verbose: true

  # 字幕区域配置文件路径（复用 backend/subtitle_area.yaml）
  subtitle_area_config: "./backend/subtitle_area.yaml"


# ============================================
# FFmpeg 配置
# ============================================
ffmpeg:
  # 是否使用项目内ffmpeg
  use_builtin: true

  # 自定义 ffmpeg 路径（仅在 use_builtin = false 时生效）
  custom_path: ""
```

### 配置项说明

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `output.intermediate_dir` | string | "output/intermediate" | cutoff后的中间视频目录 |
| `output.final_dir` | string | "output/final" | 去字幕后最终输出目录 |
| `output.keep_intermediate` | boolean | false | 是否保留中间文件 |
| `processing.max_queue_size` | int | 10 | 队列最大长度（5-20建议） |
| `processing.verbose` | boolean | true | 是否显示详细日志 |
| `processing.subtitle_area_config` | string | "./backend/subtitle_area.yaml" | 字幕区域配置文件路径 |
| `ffmpeg.use_builtin` | boolean | true | 使用项目内FFmpeg |
| `ffmpeg.custom_path` | string | "" | 自定义FFmpeg路径 |

---

## 命令行参数

```bash
python cut_and_remove/main.py excel_file.xlsx [选项]
```

### 参数列表

| 参数 | 简写 | 说明 |
|------|------|------|
| `excel_file` | - | Excel文件路径（必填，包含视频路径和时间戳信息） |
| `--config` | `-c` | 配置文件路径（默认: ./cut_and_remove/config.yaml） |
| `--output` | `-o` | 最终输出目录（会覆盖配置文件中的设置） |
| `--intermediate-dir` | - | 中间视频输出目录（会覆盖配置文件中的设置） |
| `--keep-temp` | - | 保留中间文件（会覆盖配置文件中的设置） |
| `--verbose` | `-v` | 显示详细日志 |

### 使用示例

```bash
# 基本使用
python cut_and_remove/main.py videos.xlsx

# 自定义输出目录
python cut_and_remove/main.py videos.xlsx --output custom_output

# 保留中间文件
python cut_and_remove/main.py videos.xlsx --keep-temp

# 显示详细日志
python cut_and_remove/main.py videos.xlsx --verbose

# 组合使用
python cut_and_remove/main.py videos.xlsx --output D:/output --keep-temp -v
```

---

## 处理流程

```
Excel文件 → [阶段1: cutoff删除片段] → output/intermediate/
                                              ↓
                                         队列传递
                                              ↓
output/final/ ← [阶段2: 去除字幕] ← 从队列获取视频
```

### 阶段1：视频片段删除

1. 从Excel读取视频路径和时间戳信息
2. 使用FFmpeg删除指定时间段的视频片段
3. 生成中间视频文件（`video_name_cut.mp4`）
4. 将处理完成的视频任务放入队列

### 队列传递

- 使用 `queue.Queue` 在两个阶段之间传递视频任务
- 队列大小可通过配置文件控制
- 避免内存占用过大

### 阶段2：字幕去除

1. 从队列获取待处理的视频任务
2. 读取字幕区域配置（`subtitle_area.yaml`）
3. 使用AI模型检测并去除字幕
   - 支持多种算法：STTN、LAMA、ProPainter
   - 根据 `backend/config.py` 中的 `MODE` 配置选择
4. 生成最终视频文件（`video_name_no_sub.mp4`）
5. 可选：删除中间文件以节省磁盘空间

---

## 输出结果

### 文件结构

```
output/
├── intermediate/              # 中间视频目录（可选保留）
│   ├── video1_cut.mp4
│   └── video2_cut.mp4
├── final/                     # 最终输出目录
│   ├── video1_no_sub.mp4
│   └── video2_no_sub.mp4
└── failed_tasks.txt           # 失败任务日志（如果有）
```

### 文件命名规则

| 阶段 | 文件名格式 | 示例 |
|------|-----------|------|
| 原始视频 | `{name}.{ext}` | `video.mp4` |
| 中间视频 | `{name}_cut.{ext}` | `video_cut.mp4` |
| 最终视频 | `{name}_no_sub.{ext}` | `video_no_sub.mp4` |

### 处理统计

程序运行完成后会显示详细的统计信息：

```
============================================================
总体统计
============================================================
总处理时间: 125.32秒 (2.09分钟)

阶段1 - 视频片段删除:
  总任务数: 10 个
  成功: 8 个
  失败: 2 个

阶段2 - 字幕去除:
  总任务数: 8 个
  成功: 7 个
  失败: 1 个
  平均每个视频: 15.67秒

失败列表:
  [行3] video3.mp4
    原因: 处理失败
  [行7] video7_cut.mp4
    原因: 去字幕处理失败

最终输出目录: output/final
============================================================
```

---

## 注意事项

### Excel文件格式

需要与 `cutoff_specified_video_part` 模块兼容的格式：

| 列 | 说明 | 示例 |
|----|------|------|
| 视频路径 | 视频文件路径（相对或绝对） | `videos/sample.mp4` |
| 时间戳 | 要删除的时间段（格式灵活） | `00:01:00-00:02:00` 或 `60-120` |

### 字幕区域配置

字幕检测区域配置文件：`backend/subtitle_area.yaml`

```yaml
# 左上角为坐标原点,坐标轴垂直向下为y正方向,水平朝右为x正方向
Y : 0.0  # Y轴起始位置（比例）
H : 1.0  # 高度（比例）
X : 0.0  # X轴起始位置（比例）
W : 1.0  # 宽度（比例）
```

- 使用比例值（0.0-1.0）自动适配不同分辨率的视频
- 全屏检测：`Y:0.0, H:1.0, X:0.0, W:1.0`
- 底部字幕：`Y:0.85, H:0.15, X:0.0, W:1.0`

### GPU资源

- 由于深度学习模型使用GPU，当前采用**顺序执行模式**（避免资源竞争）
- 如需并行处理，请修改 `main.py` 使用多进程/线程
- 确保GPU显存足够（参考 `backend/config.py` 中的显存配置）

### FFmpeg

- 已统一使用项目内置的FFmpeg（无需额外安装）
- FFmpeg路径：`backend/ffmpeg/{platform}/ffmpeg`
- 支持平台：Windows、Linux、macOS

---

## 常见问题

### Q1: 如何修改字幕检测算法？

编辑 `backend/config.py`：

```python
# 选择算法类型
MODE = config.InpaintMode.STTN  # STTN / LAMA / PROPAINTER
```

### Q2: 处理速度太慢怎么办？

1. **调整队列大小**：增大 `processing.max_queue_size`（需要更多内存）
2. **选择快速算法**：使用 STTN 算法并启用跳过检测
   ```python
   # backend/config.py
   STTN_SKIP_DETECTION = True
   ```
3. **降低视频质量**：临时降低视频分辨率测试

### Q3: 中间文件保存在哪里？

- 默认路径：`output/intermediate/`
- 处理完成后自动删除（`keep_intermediate: false`）
- 如需保留，在配置文件中设置 `keep_intermediate: true` 或使用 `--keep-temp` 参数

### Q4: 如何批量处理多个Excel文件？

编写批处理脚本：

**Windows (batch)**:
```batch
@echo off
for %%f in (videos_*.xlsx) do (
    echo Processing %%f
    python cut_and_remove/main.py "%%f"
)
```

**Linux/Mac (bash)**:
```bash
for file in videos_*.xlsx; do
    echo "Processing $file"
    python cut_and_remove/main.py "$file"
done
```

### Q5: 内存不足怎么办？

减小队列大小：

```yaml
# config.yaml
processing:
  max_queue_size: 3  # 降低到3-5
```

或分批处理Excel文件。

### Q6: FFmpeg相关错误

**问题**：提示找不到FFmpeg

**解决方案**：
1. 检查 `backend/config.py` 中的 `FFMPEG_PATH`
2. 确保FFmpeg可执行文件存在
3. Windows系统检查文件权限

```python
# backend/config.py:53
FFMPEG_PATH = os.path.join(BASE_DIR, '', 'ffmpeg', ffmpeg_bin)
```

---

## 技术支持

如遇到问题，请检查：

1. ✅ Python版本（建议 3.8+）
2. ✅ 依赖包是否安装完整（`requirements.txt`）
3. ✅ GPU驱动和CUDA/ROCm/DirectML是否正确安装
4. ✅ 磁盘空间是否充足
5. ✅ Excel文件格式是否正确

---

## 版本信息

- **版本**：1.0.0
- **最后更新**：2025-02-06
- **兼容性**：Windows、Linux、macOS
