#!/bin/bash
# LIBENV: "LD_LIBRARY_PATH=/tmp/nova_libs" (default) or "LD_PRELOAD=/opt/conda/lib/libstdc++.so.6"
cd /tmp
LIBENV=${LIBENV:-LD_LIBRARY_PATH=/tmp/nova_libs}
CUDA_VISIBLE_DEVICES=0 nohup env -u PYTHONNOUSERSITE $LIBENV PYTHONPATH=/tmp/nova_pylib HF_HOME=/tmp/hf_nova VLLM_CACHE_ROOT=/tmp/vllm_cache TORCHINDUCTOR_CACHE_DIR=/tmp/torchinductor TRITON_CACHE_DIR=/tmp/triton XDG_CACHE_HOME=/tmp/xdg_cache /home/jovyan/.local/bin/vllm serve openai/gpt-oss-20b --served-model-name openai/gpt-oss-20b --port 8010 --host 0.0.0.0 --gpu-memory-utilization ${GMU:-0.30} --max-model-len 32768 --max-num-seqs 32 --enable-prefix-caching --enforce-eager > /home/jovyan/Hyunsoo/projects/N.O.V.A/code/tools/gptoss_vllm.log 2>&1 &
echo $!
