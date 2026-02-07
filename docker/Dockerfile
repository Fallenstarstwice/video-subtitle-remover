FROM python:3.12

RUN --mount=type=cache,target=/root/.cache,sharing=private \
    apt update && \
    apt install -y libgl1-mesa-glx && \
    true

ADD . /vsr
ARG CUDA_VERSION=12.8
ARG USE_DIRECTML=0

# 如果是 CUDA 版本，执行 CUDA 特定设置
RUN --mount=type=cache,target=/root/.cache,sharing=private \
    if [ "${USE_DIRECTML:-0}" != "1" ]; then \
        pip install paddlepaddle-gpu==3.3.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/ && \
        pip install torch==2.7.1 torchvision==0.22.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu$(echo ${CUDA_VERSION} | tr -d '.') && \
        pip install -r /vsr/requirements.txt; \
    fi

# 如果是 DirectML 版本，执行 DirectML 特定设置
RUN --mount=type=cache,target=/root/.cache,sharing=private \
    if [ "${USE_DIRECTML:-0}" = "1" ]; then \
        pip install paddlepaddle==3.3.0 && \
        pip install torch_directml==0.2.5.dev240914 && \
        pip install -r /vsr/requirements.txt; \
    fi

ENV LD_LIBRARY_PATH=/usr/local/lib/python3.12/site-packages/nvidia/cudnn/lib/
WORKDIR /vsr
CMD ["python", "/vsr/backend/main.py"]