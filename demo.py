import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageOps
import os
import math


# ---------- 工具函数 ----------
def pil_image_to_tk(img):
    return ImageTk.PhotoImage(img)


def load_font(font_size):
    # 尝试加载常见系统字体，失败则退回默认
    possible = ["SimHei.ttf"]
    for f in possible:
        try:
            return ImageFont.truetype(f, font_size)
        except Exception:
            continue
    return ImageFont.load_default()


# ---------- 主应用 ----------
class WatermarkProApp:
    CANVAS_W = 900
    CANVAS_H = 600

    def __init__(self, root):
        self.root = root
        root.title("Watermark Pro — 文字/图片水印（可拖拽/缩放/旋转）")
        self.setup_ui()

        # 状态
        self.base_img = None  # 原始高分辨率图（PIL）
        self.display_img = None  # 缩放后显示图（PIL）
        self.display_tk = None  # 展示用 PhotoImage
        self.display_scale = 1.0  # display_img 与 base_img 的缩放比例
        self.display_offset = (0, 0)  # display_img 在 canvas 上的左上角坐标

        # 水印基础图（PIL），不包含用户 scale/rotate/alpha
        self.wm_base = None  # watermark base image (RGBA) - 原始 logo 或文字渲染图
        self.wm_base_size = (0, 0)
        # 可视参数（用户控制）
        self.wm_x = 50
        self.wm_y = 50
        self.wm_user_scale = 1.0
        self.wm_rotation = 0.0  # degrees
        self.wm_opacity = 0.6  # 0.0 - 1.0

        # Canvas 元素 id
        self.canvas_img_id = None
        self.canvas_wm_id = None

        # 拖拽相关
        self.dragging = False
        self.drag_start = (0, 0)

    # ---------- UI 创建 ----------
    def setup_ui(self):
        # 顶部控制栏
        top = tk.Frame(self.root)
        top.pack(side="top", fill="x", padx=6, pady=6)

        tk.Button(top, text="打开图片", command=self.open_base_image).pack(
            side="left", padx=4
        )
        tk.Button(
            top, text="保存最终图片", command=self.save_result, bg="#b3e6b3"
        ).pack(side="left", padx=4)

        tk.Button(top, text="居中水印", command=self.center_watermark).pack(
            side="left", padx=6
        )
        tk.Button(top, text="重置水印参数", command=self.reset_wm_params).pack(
            side="left", padx=6
        )

        # 左侧控制面板
        left = tk.Frame(self.root)
        left.pack(side="left", fill="y", padx=6, pady=6)

        # 水印类型选择
        tk.Label(left, text="水印类型").pack(anchor="w")
        self.wm_type = tk.StringVar(value="text")
        tk.Radiobutton(
            left,
            text="文字水印",
            variable=self.wm_type,
            value="text",
            command=self.on_wm_type_change,
        ).pack(anchor="w")
        tk.Radiobutton(
            left,
            text="图片水印",
            variable=self.wm_type,
            value="image",
            command=self.on_wm_type_change,
        ).pack(anchor="w")

        # 文字输入
        tk.Label(left, text="文字内容").pack(anchor="w", pady=(8, 0))
        self.text_entry = tk.Entry(left, width=24)
        self.text_entry.insert(0, "© YourName")
        self.text_entry.pack(anchor="w")

        tk.Label(left, text="字体大小（基准）").pack(anchor="w", pady=(6, 0))
        self.font_size_var = tk.IntVar(value=72)
        tk.Spinbox(
            left, from_=8, to=400, increment=2, textvariable=self.font_size_var, width=8
        ).pack(anchor="w")

        tk.Button(left, text="生成文字水印", command=self.create_text_watermark).pack(
            anchor="w", pady=6
        )

        # 图片水印选择
        tk.Label(left, text="（图片水印）选择文件").pack(anchor="w", pady=(10, 0))
        tk.Button(
            left, text="选择水印图片（PNG 推荐）", command=self.select_watermark_image
        ).pack(anchor="w", pady=4)
        self.wm_image_label = tk.Label(left, text="未选择", fg="gray")
        self.wm_image_label.pack(anchor="w")

        # 分隔
        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=8)

        # 参数滑块：缩放、透明度、旋转
        tk.Label(left, text="缩放（鼠标滚轮也可）").pack(anchor="w")
        self.scale_slider = tk.Scale(
            left,
            from_=0.1,
            to=5.0,
            resolution=0.05,
            orient="horizontal",
            length=180,
            command=self.on_scale_change,
        )
        self.scale_slider.set(1.0)
        self.scale_slider.pack(anchor="w")

        tk.Label(left, text="透明度").pack(anchor="w", pady=(6, 0))
        self.opacity_slider = tk.Scale(
            left,
            from_=0,
            to=100,
            orient="horizontal",
            length=180,
            command=self.on_opacity_change,
        )
        self.opacity_slider.set(60)
        self.opacity_slider.pack(anchor="w")

        tk.Label(left, text="旋转（度）").pack(anchor="w", pady=(6, 0))
        self.rotate_slider = tk.Scale(
            left,
            from_=-180,
            to=180,
            orient="horizontal",
            length=180,
            command=self.on_rotate_change,
        )
        self.rotate_slider.set(0)
        self.rotate_slider.pack(anchor="w")

        # 说明
        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=8)
        tk.Label(left, text="操作提示：", fg="blue").pack(anchor="w")
        tips = [
            "左键在水印上按住并拖动移动",
            "鼠标滚轮在水印上可放大/缩小",
            "可用缩放/旋转/透明度滑块精调",
            "生成/选择文字或图片水印后再拖动",
        ]
        for t in tips:
            tk.Label(left, text="• " + t, anchor="w").pack(fill="x")

        # 主画布（显示区）
        right = tk.Frame(self.root)
        right.pack(side="left", expand=True, fill="both", padx=6, pady=6)
        self.canvas = tk.Canvas(
            right, width=self.CANVAS_W, height=self.CANVAS_H, bg="#333333"
        )
        self.canvas.pack(expand=True, fill="both")

        # 绑定交互事件
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)  # Windows
        self.canvas.bind("<Button-4>", self.on_mouse_wheel)  # Linux scroll up
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)  # Linux scroll down

        # 最下方状态栏
        self.status_var = tk.StringVar(value="准备")
        status = tk.Label(
            self.root, textvariable=self.status_var, bd=1, relief="sunken", anchor="w"
        )
        status.pack(side="bottom", fill="x")

    # ---------- 打开与显示基础图片 ----------
    def open_base_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.bmp;*.tif")]
        )
        if not path:
            return
        try:
            img = Image.open(path).convert("RGBA")
        except Exception as e:
            messagebox.showerror("错误", f"打开图片失败：{e}")
            return
        self.base_img = img
        self.status_var.set(
            f"已打开：{os.path.basename(path)}  尺寸：{img.width}×{img.height}"
        )
        # 生成 display image（等比缩放以适应 canvas）
        self.update_display_image()
        # reset watermark default
        self.reset_wm_params()

    def update_display_image(self):
        if self.base_img is None:
            return
        cw, ch = self.CANVAS_W, self.CANVAS_H
        bw, bh = self.base_img.size
        # 计算缩放以适应画布（保留完整）
        scale = min(cw / bw, ch / bh, 1.0)
        dw = int(bw * scale)
        dh = int(bh * scale)
        self.display_img = self.base_img.resize((dw, dh), Image.LANCZOS)
        self.display_tk = pil_image_to_tk(self.display_img)
        self.display_scale = scale
        # 放置在画布中居中
        x = (cw - dw) // 2
        y = (ch - dh) // 2
        self.display_offset = (x, y)
        # draw
        self.canvas.delete("all")
        self.canvas_img_id = self.canvas.create_image(
            x, y, anchor="nw", image=self.display_tk
        )
        # 若已有水印基础，重绘
        self.redraw_watermark_on_canvas()

    # ---------- 创建/选择水印 ----------
    def create_text_watermark(self):
        text = self.text_entry.get().strip()
        if not text:
            messagebox.showwarning("提示", "请输入水印文字")
            return
        # 创建一张带透明背景的文字图片（基准大小：字体大小直接使用用户输入）
        font_size = max(8, int(self.font_size_var.get()))
        font = load_font(font_size)
        # 先测量文字尺寸
        dummy = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        draw = ImageDraw.Draw(dummy)
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError:
            text_w, text_h = draw.textsize(text, font=font)

        # 为了更好的旋转不被裁切，创建稍大画布
        pad = int(max(10, font_size * 0.4))
        wm_img = Image.new(
            "RGBA", (text_w + pad * 2, text_h + pad * 2), (255, 255, 255, 0)
        )
        draw = ImageDraw.Draw(wm_img)
        # 白色半透明默认颜色，可扩展为颜色选择
        alpha = int(255 * self.wm_opacity)
        draw.text((pad, pad), text, font=font, fill=(255, 255, 255, alpha))
        self.set_wm_base(wm_img)
        self.status_var.set("已生成文字水印（可拖动/缩放/旋转）")

    def select_watermark_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.bmp")]
        )
        if not path:
            return
        try:
            wm = Image.open(path).convert("RGBA")
        except Exception as e:
            messagebox.showerror("错误", f"打开水印图片失败：{e}")
            return
        # 将 alpha channel 强制存在（确保有透明通道）
        if wm.mode != "RGBA":
            wm = wm.convert("RGBA")
        self.set_wm_base(wm)
        self.wm_image_label.config(text=os.path.basename(path))
        self.wm_type.set("image")
        self.status_var.set(f"已选择水印图片：{os.path.basename(path)}")

    def set_wm_base(self, wm_img):
        self.wm_base = wm_img.copy()
        self.wm_base_size = self.wm_base.size
        # 初始化位置：图像左上 50,50（显示坐标）
        # 若已经有 display img，放在中心
        if self.display_img:
            dx, dy = self.display_offset
            dw, dh = self.display_img.size
            self.wm_x = (
                dx + dw // 2 - int((self.wm_base_size[0] * self.display_scale) / 2)
            )
            self.wm_y = (
                dy + dh // 2 - int((self.wm_base_size[1] * self.display_scale) / 2)
            )
        else:
            self.wm_x, self.wm_y = 50, 50
        self.wm_user_scale = 1.0
        self.scale_slider.set(1.0)
        self.rotate_slider.set(0)
        # 重绘
        self.redraw_watermark_on_canvas()

    # ---------- 重绘水印到 Canvas（仅预览） ----------
    def get_wm_render_for_canvas(self):
        """基于 wm_base 与用户参数，生成展示用 watermark (PIL)"""
        if self.wm_base is None:
            return None
        # 先按用户 scale 调整到 base size * user_scale
        base_w, base_h = self.wm_base_size
        scaled_w = max(1, int(base_w * self.wm_user_scale * self.display_scale))
        scaled_h = max(1, int(base_h * self.wm_user_scale * self.display_scale))
        # 为了得到较好质量，先对 wm_base 做 user_scale，然后在绘制到 canvas 已乘 display_scale
        # 但我们直接做 combined scale = user_scale * display_scale 来避免多次插值：
        combined_w = max(1, int(base_w * self.wm_user_scale * self.display_scale))
        combined_h = max(1, int(base_h * self.wm_user_scale * self.display_scale))
        wm = self.wm_base.resize((combined_w, combined_h), Image.LANCZOS)
        # 旋转
        if abs(self.wm_rotation) > 0.001:
            wm = wm.rotate(-self.wm_rotation, expand=True, resample=Image.BICUBIC)
        # 应用透明度（乘到 alpha 通道）
        if self.wm_opacity < 1.0:
            alpha = wm.split()[3].point(lambda p: int(p * self.wm_opacity))
            wm.putalpha(alpha)
        return wm

    def redraw_watermark_on_canvas(self):
        # 先清除旧的 wm
        if self.canvas_wm_id:
            try:
                self.canvas.delete(self.canvas_wm_id)
            except Exception:
                pass
            self.canvas_wm_id = None
        if not self.wm_base or not self.display_img:
            return
        wm_disp = self.get_wm_render_for_canvas()
        if wm_disp is None:
            return
        self.wm_disp_tk = pil_image_to_tk(wm_disp)
        # 直接在 canvas 的 wm_x, wm_y 位置绘制（wm_x/wm_y 为 display 坐标）
        self.canvas_wm_id = self.canvas.create_image(
            self.wm_x, self.wm_y, anchor="nw", image=self.wm_disp_tk
        )
        # 把水印放到图片之上
        self.canvas.tag_raise(self.canvas_wm_id, self.canvas_img_id)

    # ---------- 交互事件（拖动、缩放） ----------
    def on_canvas_press(self, event):
        # 点击判断是否在水印范围内（使用当前 wm_render 大小）
        if self.wm_base is None or self.display_img is None:
            return
        x, y = event.x, event.y
        wm_render = self.get_wm_render_for_canvas()
        if wm_render is None:
            return
        w, h = wm_render.size
        if self.wm_x <= x <= self.wm_x + w and self.wm_y <= y <= self.wm_y + h:
            self.dragging = True
            self.drag_start = (x, y)
            self.status_var.set("拖动水印中...")
        else:
            self.dragging = False

    def on_canvas_move(self, event):
        if not self.dragging:
            return
        x, y = event.x, event.y
        dx = x - self.drag_start[0]
        dy = y - self.drag_start[1]
        self.wm_x += dx
        self.wm_y += dy
        self.drag_start = (x, y)
        self.redraw_watermark_on_canvas()

    def on_canvas_release(self, event):
        if self.dragging:
            self.dragging = False
            self.status_var.set("移动完成")

    def on_mouse_wheel(self, event):
        # 鼠标滚轮在水印上时缩放水印（检测光标是否在水印范围）
        if self.wm_base is None or self.display_img is None:
            return
        x, y = event.x, event.y if hasattr(event, "y") else (event.x, None)
        # Determine scroll direction cross-platform
        delta = 0
        if hasattr(event, "delta"):
            delta = event.delta
        elif event.num == 4:
            delta = 120
        elif event.num == 5:
            delta = -120
        # 检查是否在水印范围
        wm_render = self.get_wm_render_for_canvas()
        if wm_render is None:
            return
        w, h = wm_render.size
        if not (
            self.wm_x <= event.x <= self.wm_x + w
            and self.wm_y <= event.y <= self.wm_y + h
        ):
            return
        # 缩放比例变化
        factor = 1.0 + (0.12 if delta > 0 else -0.12)
        new_scale = max(0.05, min(10.0, self.wm_user_scale * factor))
        self.wm_user_scale = new_scale
        self.scale_slider.set(self.wm_user_scale)
        self.redraw_watermark_on_canvas()
        self.status_var.set(f"缩放：{self.wm_user_scale:.2f}x")

    # ---------- 滑块回调 ----------
    def on_scale_change(self, val):
        try:
            self.wm_user_scale = float(val)
        except:
            return
        self.redraw_watermark_on_canvas()

    def on_opacity_change(self, val):
        try:
            v = int(val)
            self.wm_opacity = max(0.0, min(1.0, v / 100.0))
        except:
            return
        self.redraw_watermark_on_canvas()

    def on_rotate_change(self, val):
        try:
            self.wm_rotation = float(val)
        except:
            return
        self.redraw_watermark_on_canvas()

    # ---------- 操作按钮 ----------
    def center_watermark(self):
        if not self.display_img or not self.wm_base:
            return
        dx, dy = self.display_offset
        dw, dh = self.display_img.size
        wm_render = self.get_wm_render_for_canvas()
        if not wm_render:
            return
        ww, wh = wm_render.size
        self.wm_x = dx + (dw - ww) // 2
        self.wm_y = dy + (dh - wh) // 2
        self.redraw_watermark_on_canvas()

    def reset_wm_params(self):
        self.wm_user_scale = 1.0
        self.wm_rotation = 0.0
        self.wm_opacity = 0.6
        self.scale_slider.set(1.0)
        self.rotate_slider.set(0)
        self.opacity_slider.set(int(self.wm_opacity * 100))
        self.status_var.set("水印参数已重置")
        self.redraw_watermark_on_canvas()

    def on_wm_type_change(self):
        # 切换到文字时可以自动生成文字水印（保持上次文字）
        if self.wm_type.get() == "text":
            self.create_text_watermark()
        # 如果切到图片没有选择，则提示
        else:
            if self.wm_base is None:
                self.status_var.set("请选择水印图片或生成文字水印")

    # ---------- 保存最终结果（高分辨率） ----------
    def save_result(self):
        if self.base_img is None:
            messagebox.showwarning("提示", "请先打开原始图片")
            return
        if self.wm_base is None:
            # 允许用户保存无水印的原图
            if not messagebox.askyesno("确认", "当前没有水印，是否直接保存原图？"):
                return
            save_path = filedialog.asksaveasfilename(
                defaultextension=".png", filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")]
            )
            if not save_path:
                return
            if save_path.lower().endswith(".jpg") or save_path.lower().endswith(
                ".jpeg"
            ):
                self.base_img.convert("RGB").save(save_path, quality=95)
            else:
                self.base_img.save(save_path)
            messagebox.showinfo("已保存", f"文件已保存：\n{save_path}")
            return

        # 计算水印在原始图上的位置与大小
        # display_offset = (dx, dy), display_scale = s
        dx, dy = self.display_offset
        s = self.display_scale
        # wm_x/wm_y are display coords of wm top-left. Convert to original coords:
        orig_x = int(round((self.wm_x - dx) / s))
        orig_y = int(round((self.wm_y - dy) / s))
        # wm_base size in px. The final wm on original should be scaled by wm_user_scale
        base_w, base_h = self.wm_base_size
        final_w = max(1, int(round(base_w * self.wm_user_scale)))
        final_h = max(1, int(round(base_h * self.wm_user_scale)))
        # Resize watermark to final size (in original image pixel space)
        wm_for_paste = self.wm_base.resize((final_w, final_h), Image.LANCZOS)
        # Rotate if needed (note rotate expands image, so position adjust required)
        if abs(self.wm_rotation) > 0.001:
            wm_for_paste = wm_for_paste.rotate(
                -self.wm_rotation, expand=True, resample=Image.BICUBIC
            )
        # Apply opacity to alpha channel
        if self.wm_opacity < 1.0:
            alpha = wm_for_paste.split()[3].point(lambda p: int(p * self.wm_opacity))
            wm_for_paste.putalpha(alpha)

        # 因为 rotate 后图片可能变大，新的 top-left 需要从中心偏移
        # 我们在 display 时是基于 rotated-render 的尺寸来定位的（在 redraw 时使用 combined scale and rotation）
        # 为简化：我们在保存时计算水印中心在原图坐标，然后将 rotated wm 的左上定位到 center - new_size/2
        # 计算水印中心在显示图坐标：
        wm_render_disp = self.get_wm_render_for_canvas()
        if wm_render_disp is None:
            messagebox.showerror("错误", "无法获取水印渲染信息")
            return
        # center on display coords:
        center_disp_x = self.wm_x + wm_render_disp.size[0] // 2
        center_disp_y = self.wm_y + wm_render_disp.size[1] // 2
        # convert to original coords:
        center_orig_x = int(round((center_disp_x - dx) / s))
        center_orig_y = int(round((center_disp_y - dy) / s))
        # Now compute paste top-left:
        new_w, new_h = wm_for_paste.size
        paste_x = center_orig_x - new_w // 2
        paste_y = center_orig_y - new_h // 2

        # 创建拷贝并粘贴
        result = self.base_img.convert("RGBA").copy()
        # clip paste coordinates to image — PIL paste handles negative coords
        result.paste(wm_for_paste, (paste_x, paste_y), wm_for_paste)

        save_path = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")]
        )
        if not save_path:
            return
        try:
            if save_path.lower().endswith(".jpg") or save_path.lower().endswith(
                ".jpeg"
            ):
                # JPG 不支持 alpha，先合并到白色背景
                bg = Image.new("RGB", result.size, (255, 255, 255))
                bg.paste(result, mask=result.split()[3])
                bg.save(save_path, quality=95)
            else:
                result.save(save_path)
            messagebox.showinfo("已保存", f"文件已保存：\n{save_path}")
            self.status_var.set(f"已保存：{os.path.basename(save_path)}")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))


# ---------- 运行 ----------
if __name__ == "__main__":
    root = tk.Tk()
    app = WatermarkProApp(root)
    # 固定窗口大小以保持画布布局稳定（可根据需要移除）
    root.resizable(False, False)
    root.mainloop()
