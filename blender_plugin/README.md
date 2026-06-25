# 发型生成插件

这个 Blender 插件用于连接本地或远程 DiffLocks Web 服务：

- 上传用户选择的照片。
- 只暴露毛发数量比例，其他参数沿用服务端默认值。
- 显示服务端队列和推理进度。
- 完成后自动下载 `hair.blend` 并追加到当前场景。

## Windows 安装

```powershell
powershell -ExecutionPolicy Bypass -File .\blender_plugin\install_blender_plugin_windows.ps1 -BlenderVersion 5.1
```

也可以手动把 `hair_generation_plugin` 文件夹复制到 Blender 的 `scripts/addons` 目录，然后在偏好设置里启用 `发型生成插件`。

## 打包

```powershell
powershell -ExecutionPolicy Bypass -File .\blender_plugin\package.ps1
```

生成文件位于 `blender_plugin/dist/hair_generation_plugin.zip`。

