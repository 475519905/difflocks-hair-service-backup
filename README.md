# DiffLocks 发型生成服务备份

这是从 GCP L4 服务端 `/home/c47551/difflocks_web` 拉取的发型生成 Web 服务源码备份，并补充了本地一键部署脚本和 Blender 插件。

## 目录

- `server/` - L4 上运行的 FastAPI 服务端源码。
- `local_deploy/` - 本地部署脚本，负责创建 Web 虚拟环境、生成本地 `.env`、启动服务。
- `blender_plugin/` - Blender 插件源码，能把图片提交到服务端并把生成的 `hair.blend` 导回当前场景。

## 不包含的内容

为了安全和体积控制，Git 仓库不包含：

- 服务器 `.env`、密码、Cookie、令牌。
- DiffLocks checkpoints、数据集、生成任务输出。
- `runtime_data/`、`third_party/`、`.venv*`、`.blend`、`.npz` 等运行时文件。

## 本地快速部署

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\local_deploy\install_windows.ps1 -CloneDiffLocks
powershell -ExecutionPolicy Bypass -File .\local_deploy\start_windows.ps1
```

Linux:

```bash
bash ./local_deploy/install_linux.sh --clone-difflocks
bash ./local_deploy/start_linux.sh
```

启动后访问：

```text
http://127.0.0.1:7860
```

DiffLocks 官方代码仓库为 `https://github.com/Meshcapade/difflocks`。权重需要按官方授权流程单独下载并放到 DiffLocks 代码要求的位置，本仓库不会分发 checkpoint。

如果要让安装脚本尝试安装 DiffLocks 的 `requirements.txt`，Windows 增加 `-InstallDiffLocksDeps`，Linux 增加 `--install-difflocks-deps`。NATTEN、FlashAttention-2、CUDA/PyTorch 版本仍需要按本机显卡环境确认。

## Blender 插件

Windows 安装到 Blender 5.1:

```powershell
powershell -ExecutionPolicy Bypass -File .\blender_plugin\install_blender_plugin_windows.ps1 -BlenderVersion 5.1
```

在 Blender 中启用插件 `发型生成插件`，打开 3D View 侧栏里的 `发型生成` 面板：

1. 服务地址填 `http://127.0.0.1:7860`。
2. 选择输入照片。
3. 只调整毛发数量比例。
4. 点击开始生成；再次点击同一按钮会停止等待。
5. 完成后插件自动导入服务端返回的 `hair.blend`。
