# 本地部署说明

本地部署包负责启动 Web 服务和连接 Blender/DiffLocks，不包含 DiffLocks checkpoint。

## 前置条件

- Python 3.10+。
- NVIDIA GPU 和可用 CUDA 环境，CPU 只适合启动 Web，不适合实际推理。
- Blender 4.1.1。DiffLocks 官方说明里 Blender 导出路径对应 4.1.1，其他版本可能不兼容。
- DiffLocks checkpoints。按官方授权下载后放入 `third_party/difflocks` 中官方代码要求的位置。
- NATTEN 和 FlashAttention-2。请按本机 CUDA/PyTorch 版本安装。

## Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\local_deploy\install_windows.ps1 -CloneDiffLocks
powershell -ExecutionPolicy Bypass -File .\local_deploy\start_windows.ps1
```

可选安装 DiffLocks Python 依赖：

```powershell
powershell -ExecutionPolicy Bypass -File .\local_deploy\install_windows.ps1 -CloneDiffLocks -InstallDiffLocksDeps
```

## Linux

```bash
bash ./local_deploy/install_linux.sh --clone-difflocks
bash ./local_deploy/start_linux.sh
```

可选安装 DiffLocks Python 依赖：

```bash
bash ./local_deploy/install_linux.sh --clone-difflocks --install-difflocks-deps
```

## 配置文件

首次安装会在仓库根目录生成 `.env`。常用字段：

- `DIFFLOCKS_WEB_DATA` - 任务输出目录。
- `DIFFLOCKS_REPO` - DiffLocks 官方仓库目录。
- `DIFFLOCKS_PYTHON` - 用于执行 DiffLocks 推理的 Python。
- `BLENDER_PATH` - Blender 可执行文件路径。
- `DIFFLOCKS_PUBLIC=1` - 本地默认免登录。

