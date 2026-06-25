bl_info = {
    "name": "发型生成插件",
    "author": "Hanyue",
    "version": (0, 1, 0),
    "blender": (4, 1, 0),
    "location": "3D View > Sidebar > 发型生成",
    "description": "提交照片到 DiffLocks 服务并把生成毛发导入 Blender",
    "category": "3D View",
}

import json
import mimetypes
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import bpy
from bpy.props import BoolProperty, FloatProperty, PointerProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup


DEFAULT_PARAMS = {
    "seed": "5",
    "steps": "180",
    "cfg": "1.6",
    "crop": "3.4",
    "upsample": "4",
    "decode_chunks": "10",
    "vertex_subsample": "0.5",
    "radius": "0.0001",
    "preview_resolution": "900",
}


def clean_base_url(value: str) -> str:
    value = (value or "").strip()
    return value.rstrip("/")


def join_url(base_url: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return clean_base_url(base_url) + "/" + path.lstrip("/")


def http_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def http_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"Accept": "application/octet-stream"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def submit_job(base_url: str, image_path: str, strand_subsample: float) -> dict:
    boundary = "----hairgen-" + uuid.uuid4().hex
    image_file = Path(bpy.path.abspath(image_path))
    image_name = image_file.name
    content_type = mimetypes.guess_type(str(image_file))[0] or "application/octet-stream"

    fields = dict(DEFAULT_PARAMS)
    fields["strand_subsample"] = f"{strand_subsample:.4f}"

    body = bytearray()
    for key, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")

    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(
        (
            f'Content-Disposition: form-data; name="image"; filename="{image_name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
    )
    body.extend(image_file.read_bytes())
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    request = urllib.request.Request(
        join_url(base_url, "/api/jobs"),
        data=bytes(body),
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def append_blend(blend_path: Path, context) -> int:
    linked_count = 0
    with bpy.data.libraries.load(str(blend_path), link=False) as (data_from, data_to):
        if data_from.collections:
            data_to.collections = list(data_from.collections)
        else:
            data_to.objects = list(data_from.objects)

    for collection in getattr(data_to, "collections", []) or []:
        if collection is None:
            continue
        try:
            context.scene.collection.children.link(collection)
        except RuntimeError:
            pass
        linked_count += len(collection.objects)

    for obj in getattr(data_to, "objects", []) or []:
        if obj is None:
            continue
        try:
            context.collection.objects.link(obj)
        except RuntimeError:
            pass
        linked_count += 1

    return linked_count


def error_text(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = ""
        return f"HTTP {exc.code}: {detail[:300]}"
    if isinstance(exc, urllib.error.URLError):
        return f"连接失败: {exc.reason}"
    return str(exc)


class HairGenProperties(PropertyGroup):
    server_url: StringProperty(
        name="服务地址",
        default="http://127.0.0.1:7860",
        description="本地或远程发型生成服务地址",
    )
    image_path: StringProperty(
        name="输入照片",
        subtype="FILE_PATH",
        description="用于生成发型的正面或接近正面的照片",
    )
    strand_subsample: FloatProperty(
        name="毛发数量",
        default=1.0,
        min=0.05,
        max=1.0,
        precision=2,
        description="1.0 为完整毛发数量，降低会减少毛发数量并加快导入",
    )
    progress: FloatProperty(name="进度", default=0.0, min=0.0, max=100.0, subtype="PERCENTAGE")
    status_text: StringProperty(name="状态", default="未开始")
    stage_text: StringProperty(name="阶段", default="")
    job_id: StringProperty(name="任务 ID", default="")
    status_url: StringProperty(name="状态地址", default="")
    downloaded_blend: StringProperty(name="下载文件", default="")
    is_running: BoolProperty(name="正在生成", default=False)
    imported: BoolProperty(name="已导入", default=False)


class HAIRGEN_OT_toggle_job(Operator):
    bl_idname = "hairgen.toggle_job"
    bl_label = "开始生成"
    bl_options = {"REGISTER"}

    _timer = None
    _last_poll = 0.0

    def execute(self, context):
        props = context.scene.hairgen_props
        if props.is_running:
            props.is_running = False
            props.status_text = "已停止等待"
            props.stage_text = ""
            return {"FINISHED"}

        image_path = Path(bpy.path.abspath(props.image_path))
        if not image_path.exists() or not image_path.is_file():
            self.report({"ERROR"}, "请选择有效的输入照片")
            return {"CANCELLED"}

        base_url = clean_base_url(props.server_url)
        if not base_url:
            self.report({"ERROR"}, "请填写服务地址")
            return {"CANCELLED"}

        try:
            result = submit_job(base_url, str(image_path), props.strand_subsample)
        except Exception as exc:
            props.status_text = error_text(exc)
            self.report({"ERROR"}, props.status_text)
            return {"CANCELLED"}

        props.job_id = str(result.get("id") or "")
        props.status_url = str(result.get("status_url") or f"/api/jobs/{props.job_id}")
        props.progress = 0.0
        props.stage_text = "排队中"
        props.status_text = "任务已提交"
        props.downloaded_blend = ""
        props.imported = False
        props.is_running = True

        self._timer = context.window_manager.event_timer_add(1.0, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        props = context.scene.hairgen_props
        if not props.is_running:
            self._finish_timer(context)
            return {"CANCELLED"}

        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        now = time.monotonic()
        if now - self._last_poll < 1.0:
            return {"PASS_THROUGH"}
        self._last_poll = now

        try:
            data = http_json(join_url(props.server_url, props.status_url))
        except Exception as exc:
            props.status_text = error_text(exc)
            self.report({"WARNING"}, props.status_text)
            return {"PASS_THROUGH"}

        props.progress = float(data.get("progress") or 0)
        props.stage_text = str(data.get("stage_label") or data.get("stage") or "")
        status = str(data.get("status") or "")
        if data.get("jobs_ahead") is not None and status == "queued":
            props.status_text = f"排队中，前面还有 {data.get('jobs_ahead')} 个任务"
        else:
            props.status_text = props.stage_text or status

        if status == "failed":
            props.is_running = False
            props.status_text = str(data.get("error") or "生成失败")
            self.report({"ERROR"}, props.status_text)
            self._finish_timer(context)
            return {"CANCELLED"}

        if status == "done" and not props.imported:
            try:
                count = self._download_and_import(context, data)
            except Exception as exc:
                props.is_running = False
                props.status_text = error_text(exc)
                self.report({"ERROR"}, props.status_text)
                self._finish_timer(context)
                return {"CANCELLED"}
            props.imported = True
            props.is_running = False
            props.progress = 100.0
            props.status_text = f"完成，已导入 {count} 个对象"
            self.report({"INFO"}, props.status_text)
            self._finish_timer(context)
            return {"FINISHED"}

        return {"PASS_THROUGH"}

    def _download_and_import(self, context, data: dict) -> int:
        props = context.scene.hairgen_props
        outputs = data.get("outputs") or {}
        hair_url = outputs.get("hair_blend") or f"/api/jobs/{props.job_id}/files/hair.blend"
        content = http_bytes(join_url(props.server_url, str(hair_url)))
        blend_path = Path(tempfile.gettempdir()) / f"hairgen_{props.job_id}_hair.blend"
        blend_path.write_bytes(content)
        props.downloaded_blend = str(blend_path)
        return append_blend(blend_path, context)

    def _finish_timer(self, context):
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None


class HAIRGEN_OT_add_default_head(Operator):
    bl_idname = "hairgen.add_default_head"
    bl_label = "添加默认头模"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        mat = bpy.data.materials.get("HairGen_Default_Skin")
        if mat is None:
            mat = bpy.data.materials.new("HairGen_Default_Skin")
            mat.diffuse_color = (0.74, 0.56, 0.46, 1.0)

        bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=1.0, location=(0, 0, 1.62))
        head = context.object
        head.name = "HairGen_Default_Head"
        head.scale = (0.34, 0.27, 0.46)
        head.data.materials.append(mat)
        bpy.ops.object.shade_smooth()

        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.18, depth=0.42, location=(0, 0, 1.08))
        neck = context.object
        neck.name = "HairGen_Default_Neck"
        neck.scale = (0.8, 0.7, 1.0)
        neck.data.materials.append(mat)
        bpy.ops.object.shade_smooth()

        self.report({"INFO"}, "已添加默认头模")
        return {"FINISHED"}


class HAIRGEN_PT_panel(Panel):
    bl_label = "发型生成"
    bl_idname = "HAIRGEN_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "发型生成"

    def draw(self, context):
        layout = self.layout
        props = context.scene.hairgen_props

        layout.prop(props, "server_url")
        layout.prop(props, "image_path")
        layout.prop(props, "strand_subsample", slider=True)

        button_text = "停止等待" if props.is_running else "开始生成"
        layout.operator("hairgen.toggle_job", text=button_text, icon="CANCEL" if props.is_running else "PLAY")
        layout.operator("hairgen.add_default_head", text="添加默认头模", icon="OUTLINER_OB_ARMATURE")

        layout.separator()
        layout.prop(props, "progress", slider=True)
        layout.label(text=f"状态: {props.status_text}")
        if props.stage_text:
            layout.label(text=f"阶段: {props.stage_text}")
        if props.job_id:
            layout.label(text=f"任务: {props.job_id}")


classes = (
    HairGenProperties,
    HAIRGEN_OT_toggle_job,
    HAIRGEN_OT_add_default_head,
    HAIRGEN_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.hairgen_props = PointerProperty(type=HairGenProperties)


def unregister():
    if hasattr(bpy.types.Scene, "hairgen_props"):
        del bpy.types.Scene.hairgen_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
