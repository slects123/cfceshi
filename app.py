# -*- coding: utf-8 -*-
"""TikTok 免拔卡电脑助手：登录后检测 USB，并一键启动 / ADB 安装。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import tkinter as tk
import urllib.error
import urllib.request
from pathlib import Path

API = "https://ios.slects.top/tiktok-shop/api/query"
CREATE_NO_WINDOW = 0x08000000

BG = "#101218"
CARD = "#1a1e2a"
LINE = "#2c3348"
TEXT = "#f5f7fb"
MUTED = "#9aa3b8"
GOLD = "#e8b15a"
INK = "#1a1408"
TEAL = "#5eead4"
ROSE = "#fb7185"
VIOLET = "#c4b5fd"
WARN = "#fbbf24"
BAD = "#fb7185"
INPUT = "#0d1018"

START_SCRIPTS = (
    "sh /sdcard/Android/data/moe.shizuku.privileged.api/start.sh",
    "sh /storage/emulated/0/Android/data/moe.shizuku.privileged.api/start.sh",
)


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


def adb_path() -> Path:
    name = "adb.exe" if os.name == "nt" else "adb"
    return app_dir() / "adb" / name


def apk_path(name: str) -> Path:
    return app_dir() / "apks" / name


class Pill(tk.Canvas):
    def __init__(self, master, text, command, fill, fg=INK, height=46, font=None):
        super().__init__(master, height=height, bg=master["bg"], highlightthickness=0, bd=0)
        self.command = command
        self.fill = fill
        self.fg = fg
        self.label = text
        self.enabled = True
        self._font = font or ("Microsoft YaHei UI", 12, "bold")
        self.bind("<Button-1>", self._click)
        self.bind("<Configure>", lambda _e: self._draw())

    def _draw(self) -> None:
        self.delete("all")
        w = max(self.winfo_width(), 40)
        h = max(self.winfo_height(), int(self["height"]))
        fill = self.fill if self.enabled else "#2a3144"
        fg = self.fg if self.enabled else "#7d869b"
        r = min(14, h // 2)
        self.create_polygon(self._points(2, 2, w - 2, h - 2, r), smooth=True, fill=fill, outline=fill)
        self.create_text(w / 2, h / 2, text=self.label, fill=fg, font=self._font)

    @staticmethod
    def _points(x1, y1, x2, y2, r):
        return [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]

    def set_text(self, text: str) -> None:
        self.label = text
        self._draw()

    def set_enabled(self, on: bool) -> None:
        self.enabled = on
        self._draw()

    def _click(self, _event) -> None:
        if self.enabled and self.command:
            self.command()


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("TikTok 免拔卡助手")
        self.geometry("460x780")
        self.minsize(420, 700)
        self.configure(bg=BG)
        self.serial = ""
        self.usb_state = "none"
        self.busy = False
        self._stop = False
        self._build()
        self.after(400, self._poll_usb)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _card(self, parent) -> tk.Frame:
        return tk.Frame(parent, bg=CARD, highlightbackground=LINE, highlightthickness=1, padx=16, pady=16)

    def _entry(self, parent) -> tk.Entry:
        return tk.Entry(
            parent, font=("Microsoft YaHei UI", 12), bg=INPUT, fg=TEXT,
            insertbackground=GOLD, relief="flat", highlightthickness=1,
            highlightbackground=LINE, highlightcolor=GOLD,
        )

    def _build(self) -> None:
        self.login = tk.Frame(self, bg=BG, padx=28, pady=28)
        self.main = tk.Frame(self, bg=BG, padx=20, pady=16)
        self.login.pack(fill="both", expand=True)

        tk.Label(self.login, text="免拔卡", bg=BG, fg=GOLD, font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w", pady=(24, 6))
        tk.Label(self.login, text="TikTok 助手", bg=BG, fg=TEXT, font=("Microsoft YaHei UI", 26, "bold")).pack(anchor="w")
        tk.Label(self.login, text="用购买时的邮箱和查询密码进入", bg=BG, fg=MUTED, font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(6, 22))

        card = self._card(self.login)
        card.pack(fill="x")
        tk.Label(card, text="邮箱", bg=CARD, fg=MUTED, font=("Microsoft YaHei UI", 10)).pack(anchor="w")
        self.email = self._entry(card)
        self.email.pack(fill="x", ipady=8, pady=(6, 14))
        tk.Label(card, text="查询密码", bg=CARD, fg=MUTED, font=("Microsoft YaHei UI", 10)).pack(anchor="w")
        self.password = self._entry(card)
        self.password.config(show="•")
        self.password.pack(fill="x", ipady=8, pady=(6, 16))
        self.password.bind("<Return>", lambda _e: self._login())
        self.login_btn = Pill(card, "进入", self._login, GOLD, INK, height=48)
        self.login_btn.pack(fill="x")
        self.login_err = tk.Label(card, text="", bg=CARD, fg=ROSE, font=("Microsoft YaHei UI", 10), wraplength=360, justify="left")
        self.login_err.pack(anchor="w", pady=(10, 0))

        head = tk.Frame(self.main, bg=BG)
        head.pack(fill="x")
        tk.Label(head, text="TikTok 助手", bg=BG, fg=TEXT, font=("Microsoft YaHei UI", 18, "bold")).pack(side="left")
        tk.Button(
            head, text="退出", command=self._logout, bg=BG, fg=MUTED, activebackground=BG,
            activeforeground=TEXT, relief="flat", bd=0, font=("Microsoft YaHei UI", 10), cursor="hand2",
        ).pack(side="right")

        usb = self._card(self.main)
        usb.pack(fill="x", pady=(14, 10))
        tk.Label(usb, text="USB", bg=CARD, fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(anchor="w")
        self.usb_var = tk.StringVar(value="正在检测…")
        self.usb_label = tk.Label(usb, textvariable=self.usb_var, bg=CARD, fg=TEXT, font=("Microsoft YaHei UI", 13, "bold"), wraplength=380, justify="left")
        self.usb_label.pack(anchor="w", pady=(4, 0))

        shizuku = self._card(self.main)
        shizuku.pack(fill="x", pady=(0, 10))
        tk.Label(shizuku, text="Shizuku", bg=CARD, fg=TEAL, font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w")
        box = tk.Frame(shizuku, bg=CARD)
        box.pack(fill="x", pady=(12, 0))
        self.start_btn = Pill(box, "启动", self._start_shizuku, "#134e4a", TEAL, height=52, font=("Microsoft YaHei UI", 14, "bold"))
        self.start_btn.pack(fill="x")
        self.one_btn = Pill(box, "一键", self._start_shizuku, GOLD, INK, height=36, font=("Microsoft YaHei UI", 11, "bold"))
        self.one_btn.pack(anchor="w", pady=(8, 0), fill="x", ipadx=0)
        self.one_btn.pack_configure(anchor="w")
        # 限制一键宽度，贴在启动键左下角
        self.one_btn.pack_forget()
        self.one_btn.configure(width=120)
        self.one_btn.pack(anchor="w", pady=(8, 0))
        tk.Label(shizuku, text="一键在启动键左下角，通过 USB 启动手机里的 Shizuku", bg=CARD, fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(10, 0))

        inst = self._card(self.main)
        inst.pack(fill="x")
        tk.Label(inst, text="安装到手机", bg=CARD, fg=TEXT, font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w", pady=(0, 10))
        self.btn_shizuku = Pill(inst, "ADB 安装 Shizuku", lambda: self._install("Shizuku-13.6.apk", "ADB 安装 Shizuku"), "#134e4a", TEAL)
        self.btn_nrfr = Pill(inst, "ADB 安装 Nrfr", lambda: self._install("Nrfr-v1.5.4.apk", "ADB 安装 Nrfr"), "#4c1d2a", ROSE)
        self.btn_aurora = Pill(inst, "ADB 安装 Aurora", lambda: self._install("Aurora-Store-4.4.4.apk", "ADB 安装 Aurora"), "#2e2460", VIOLET)
        for btn in (self.btn_shizuku, self.btn_nrfr, self.btn_aurora):
            btn.pack(fill="x", pady=4)

        tk.Label(self.main, text="日志", bg=BG, fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(12, 6))
        self.log = tk.Text(self.main, height=8, font=("Consolas", 9), bg="#0b0d12", fg="#d6dbe8", relief="flat", highlightthickness=0, padx=10, pady=8)
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

    def _login(self) -> None:
        email = self.email.get().strip()
        password = self.password.get()
        self.login_err.config(text="")
        if not email or not password:
            self.login_err.config(text="请填写邮箱和查询密码")
            return
        self.login_btn.set_enabled(False)
        self.login_btn.set_text("正在验证…")

        def work() -> None:
            try:
                body = json.dumps({"email": email, "query_password": password}).encode("utf-8")
                req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json", "User-Agent": "TikTokUsbHelper/1.0"})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                raw = e.read().decode("utf-8", "replace")
                try:
                    msg = json.loads(raw).get("error") or "登录失败"
                except Exception:
                    msg = "登录失败（%s）" % e.code
                self.after(0, lambda: self._login_fail(msg))
                return
            except Exception as e:
                self.after(0, lambda: self._login_fail("无法连接服务器：%s" % e))
                return
            if not data.get("ok"):
                self.after(0, lambda: self._login_fail(data.get("error") or "邮箱或查询密码不正确"))
                return
            order = data.get("order") or {}
            if order.get("status") != "paid":
                self.after(0, lambda: self._login_fail("订单尚未支付，请先完成支付宝付款"))
                return
            self.after(0, lambda: self._login_ok(order))

        threading.Thread(target=work, daemon=True).start()

    def _login_fail(self, msg: str) -> None:
        self.login_btn.set_enabled(True)
        self.login_btn.set_text("进入")
        self.login_err.config(text=msg)

    def _login_ok(self, order: dict) -> None:
        self.login_btn.set_enabled(True)
        self.login_btn.set_text("进入")
        self.login.pack_forget()
        self.main.pack(fill="both", expand=True)
        self._write("已登录 %s · 订单 %s" % (order.get("email") or "", order.get("trade_no") or ""))

    def _logout(self) -> None:
        self.main.pack_forget()
        self.login.pack(fill="both", expand=True)
        self.password.delete(0, "end")

    def _write(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _run_adb(self, args: list[str], timeout: int = 40) -> subprocess.CompletedProcess:
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = CREATE_NO_WINDOW
        return subprocess.run(
            [str(adb_path()), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(adb_path().parent), **kwargs,
        )

    def _device_args(self) -> list[str]:
        return ["-s", self.serial] if self.serial else []

    def _poll_usb(self) -> None:
        if self._stop:
            return

        def work() -> None:
            if not adb_path().is_file():
                self.after(0, lambda: self._set_usb("未找到 ADB", BAD, "", "missing"))
                return
            try:
                proc = self._run_adb(["devices"], timeout=8)
            except Exception as e:
                self.after(0, lambda: self._set_usb("ADB 检测失败", BAD, "", "error"))
                self.after(0, lambda: self._write(str(e)))
                return
            lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip() and "List of devices" not in ln]
            chosen, state, label, color = "", "none", "未检测到 USB 连接", WARN
            for ln in lines:
                parts = ln.split()
                if len(parts) < 2:
                    continue
                serial, st = parts[0], parts[1]
                if st == "device":
                    chosen, state, label, color = serial, "device", "USB 已连接   %s" % serial, TEAL
                    break
                if st == "unauthorized" and state != "device":
                    chosen, state, label, color = serial, "unauthorized", "已插上，请在手机上允许 USB 调试", WARN
                elif st == "offline" and state == "none":
                    chosen, state, label, color = serial, "offline", "设备离线，请重新插拔数据线", BAD
            self.after(0, lambda: self._set_usb(label, color, chosen, state))

        threading.Thread(target=work, daemon=True).start()
        self.after(2000, self._poll_usb)

    def _set_usb(self, label: str, color: str, serial: str, state: str) -> None:
        self.usb_var.set(label)
        self.usb_label.config(fg=color)
        self.serial = serial if state == "device" else ""
        self.usb_state = state

    def _need_device(self) -> bool:
        if self.usb_state != "device" or not self.serial:
            self._write("请先用数据线连接手机，并允许 USB 调试")
            return False
        return True

    def _lock(self, locked: bool) -> None:
        self.busy = locked
        for btn in (self.start_btn, self.one_btn, self.btn_shizuku, self.btn_nrfr, self.btn_aurora):
            btn.set_enabled(not locked)

    def _start_shizuku(self) -> None:
        if self.busy or not self._need_device():
            return
        self._lock(True)
        self._write("正在启动 Shizuku…")

        def work() -> None:
            last, ok = "", False
            for script in START_SCRIPTS:
                try:
                    proc = self._run_adb([*self._device_args(), "shell", script], timeout=40)
                except Exception as e:
                    last = str(e)
                    continue
                out = ((proc.stdout or "") + (proc.stderr or "")).strip()
                last = out or ("退出码 %s" % proc.returncode)
                if proc.returncode == 0 and "No such file" not in out and "not found" not in out.lower():
                    ok = True
                    break
            msg = "Shizuku 已执行启动" if ok else ("启动失败：%s\n请先安装并打开过一次 Shizuku" % last)
            self.after(0, lambda: self._write(msg))
            self.after(0, lambda: self._lock(False))

        threading.Thread(target=work, daemon=True).start()

    def _install(self, filename: str, title: str) -> None:
        if self.busy or not self._need_device():
            return
        apk = apk_path(filename)
        if not apk.is_file():
            self._write("缺少安装包：%s" % filename)
            return
        self._lock(True)
        self._write("%s …" % title)

        def work() -> None:
            try:
                proc = self._run_adb([*self._device_args(), "install", "-r", str(apk)], timeout=180)
                out = ((proc.stdout or "") + (proc.stderr or "")).strip()
                msg = ("%s 成功" % title) if proc.returncode == 0 and "Success" in out else ("%s 失败\n%s" % (title, out or ("退出码 %s" % proc.returncode)))
            except Exception as e:
                msg = "%s 失败：%s" % (title, e)
            self.after(0, lambda: self._write(msg))
            self.after(0, lambda: self._lock(False))

        threading.Thread(target=work, daemon=True).start()

    def _on_close(self) -> None:
        self._stop = True
        self.destroy()


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
