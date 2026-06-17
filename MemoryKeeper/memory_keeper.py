import flet as ft
import json
import os
from datetime import datetime
import threading
import time
import plyer
from PIL import Image, ImageDraw, ImageFont
import sys

try:
    import pystray
except ImportError:
    pystray = None

DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "memory_keeper_data.json")
os.makedirs(DATA_DIR, exist_ok=True)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"reminders": [], "tasks": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class MemoryKeeper:
    def __init__(self, page: ft.Page):
        self.page = page
        self.data = load_data()
        self.tray_icon = None
        self.current_color = "blue"
        
        self.setup_page()
        self.setup_tray()
        self.start_scheduler()
        self.update_reminder_list()
        self.update_task_list()

    def setup_page(self):
        self.page.title = "Memory Keeper"
        self.page.window.width = 820
        self.page.window.height = 650
        self.page.window.resizable = False
        self.page.theme_mode = ft.ThemeMode.LIGHT
        
        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(text="Напоминания", content=self.create_reminders_tab()),
                ft.Tab(text="Важные дела", content=self.create_tasks_tab()),
                ft.Tab(text="Настройки", content=self.create_settings_tab()),
            ],
            expand=1
        )
        
        self.page.add(self.tabs)
        self.page.on_close = self.minimize_to_tray
        self.page.update()

    def apply_theme(self, color_name, e=None):   # <-- Добавил e=None
        self.current_color = color_name
        colors = {
            "blue": "#0D47A1", "green": "#1B5E20", "purple": "#4A148C",
            "orange": "#E65100", "red": "#B71C1C", "teal": "#004D40",
            "indigo": "#1A237E", "pink": "#880E4F", "brown": "#3E2723",
            "black": "#121212",
        }
        seed = colors.get(color_name, "#0D47A1")
        self.page.theme = ft.Theme(color_scheme_seed=seed)
        self.page.update()

    def create_reminders_tab(self):
        self.reminder_list = ft.ListView(expand=1, spacing=6)

        self.new_reminder_text = ft.TextField(
            label="Текст напоминания", multiline=True, min_lines=3,
            width=580, hint_text="Что нужно не забыть..."
        )
        
        self.date_picker = ft.DatePicker(on_change=self.pick_date)
        self.time_picker = ft.TimePicker(on_change=self.pick_time)
        
        self.selected_date = ft.Text("Дата не выбрана")
        self.selected_time = ft.Text("Время не выбрано")
        
        pick_date_btn = ft.ElevatedButton("Выбрать дату", icon=ft.icons.CALENDAR_MONTH,
                                          on_click=lambda _: self.page.show_dialog(self.date_picker))
        pick_time_btn = ft.ElevatedButton("Выбрать время", icon=ft.icons.ACCESS_TIME,
                                          on_click=lambda _: self.page.show_dialog(self.time_picker))
        
        add_btn = ft.ElevatedButton("Добавить напоминание", icon=ft.icons.ADD_ALARM,
                                    on_click=self.add_reminder, width=320)

        return ft.Column([
            ft.Container(
                content=ft.Column([
                    self.new_reminder_text,
                    ft.Row([pick_date_btn, self.selected_date], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Row([pick_time_btn, self.selected_time], alignment=ft.MainAxisAlignment.CENTER),
                    add_btn
                ], spacing=15, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=30
            ),
            self.reminder_list
        ], expand=True, scroll=ft.ScrollMode.AUTO)

    def pick_date(self, e):
        if self.date_picker.value:
            self.selected_date.value = str(self.date_picker.value.date())
        self.page.update()

    def pick_time(self, e):
        if self.time_picker.value:
            self.selected_time.value = str(self.time_picker.value)
        self.page.update()

    def add_reminder(self, e):
        if not self.new_reminder_text.value or not self.date_picker.value or not self.time_picker.value:
            self.page.show_snack_bar(ft.SnackBar(ft.Text("Заполните все поля!"), bgcolor=ft.colors.RED))
            return
        
        dt = datetime.combine(self.date_picker.value.date(), self.time_picker.value)
        self.data["reminders"].append({
            "text": self.new_reminder_text.value.strip(),
            "datetime": dt.isoformat(),
            "done": False
        })
        save_data(self.data)
        self.update_reminder_list()
        
        self.new_reminder_text.value = ""
        self.selected_date.value = "Дата не выбрана"
        self.selected_time.value = "Время не выбрано"
        self.page.show_snack_bar(ft.SnackBar(ft.Text("Напоминание добавлено ✓"), bgcolor=ft.colors.GREEN))
        self.page.update()

    def update_reminder_list(self):
        self.reminder_list.controls.clear()
        for i, r in enumerate(self.data["reminders"]):
            try:
                dt = datetime.fromisoformat(r["datetime"].replace("Z", "+00:00"))
                status = "✅ Выполнено" if r.get("done") else f"⏰ {dt.strftime('%d.%m.%Y %H:%M')}"
                color = ft.colors.GREEN if r.get("done") else ft.colors.BLUE_700
            except:
                status, color = "⏰", ft.colors.BLUE_700

            delete_btn = ft.IconButton(
                icon=ft.icons.DELETE,
                icon_color=ft.colors.RED_400,
                on_click=lambda e, idx=i: self.delete_reminder(idx)
            )

            self.reminder_list.controls.append(
                ft.ListTile(
                    title=ft.Text(r["text"], size=16),
                    subtitle=ft.Text(status, color=color),
                    leading=ft.Icon(ft.icons.NOTIFICATIONS_ACTIVE if not r.get("done") else ft.icons.CHECK_CIRCLE),
                    trailing=delete_btn,
                    bgcolor=ft.colors.BLUE_50 if not r.get("done") else ft.colors.GREY_100
                )
            )
        self.page.update()

    def delete_reminder(self, index):
        if 0 <= index < len(self.data["reminders"]):
            del self.data["reminders"][index]
            save_data(self.data)
            self.update_reminder_list()

    def create_tasks_tab(self):
        self.task_list = ft.ListView(expand=1, spacing=8)
        self.new_task = ft.TextField(
            label="Новый пункт важных дел",
            width=550,
            hint_text="Например: Подготовить отчет...",
            on_submit=self.add_task
        )
        add_btn = ft.ElevatedButton("Добавить", icon=ft.icons.ADD, on_click=self.add_task)

        self.update_task_list()

        return ft.Column([
            ft.Container(
                content=ft.Row([self.new_task, add_btn], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                padding=20
            ),
            ft.Divider(),
            self.task_list
        ], expand=True, scroll=ft.ScrollMode.AUTO)

    def add_task(self, e):
        if self.new_task.value and self.new_task.value.strip():
            self.data["tasks"].append({"text": self.new_task.value.strip(), "done": False})
            save_data(self.data)
            self.update_task_list()
            self.new_task.value = ""
            self.page.update()

    def update_task_list(self):
        self.task_list.controls.clear()
        for i, t in enumerate(self.data["tasks"]):
            delete_btn = ft.IconButton(
                icon=ft.icons.DELETE,
                icon_color=ft.colors.RED_400,
                on_click=lambda e, idx=i: self.delete_task(idx)
            )
            self.task_list.controls.append(
                ft.Row([
                    ft.Checkbox(
                        label=t["text"],
                        value=t["done"],
                        on_change=lambda e, idx=i: self.toggle_task(idx, e),
                        expand=True,
                        label_style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH if t["done"] else None)
                    ),
                    delete_btn
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            )
        self.page.update()

    def toggle_task(self, index, e):
        self.data["tasks"][index]["done"] = e.control.value
        save_data(self.data)
        self.update_task_list()

    def delete_task(self, index):
        if 0 <= index < len(self.data["tasks"]):
            del self.data["tasks"][index]
            save_data(self.data)
            self.update_task_list()

    def create_settings_tab(self):
        colors = ["blue", "green", "purple", "orange", "red", "teal", "indigo", "pink", "brown", "black"]
        buttons = []
        for c in colors:
            btn_color = getattr(ft.colors, c.upper(), ft.colors.BLUE)
            buttons.append(
                ft.ElevatedButton(
                    text=c.capitalize(),
                    bgcolor=btn_color,
                    color=ft.colors.WHITE,
                    on_click=lambda e, col=c: self.apply_theme(col)
                )
            )
        return ft.Column([
            ft.Text("Выберите цвет темы:", size=22, weight=ft.FontWeight.BOLD),
            ft.Row(buttons, wrap=True, spacing=12, run_spacing=12, alignment=ft.MainAxisAlignment.CENTER)
        ], spacing=40, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def minimize_to_tray(self, e):
        self.page.window.visible = False
        self.page.update()

    def setup_tray(self):
        if not pystray: return
        try:
            icon_image = Image.new('RGB', (64, 64), color=(0, 120, 215))
            draw = ImageDraw.Draw(icon_image)
            font = ImageFont.load_default()
            draw.text((18, 18), "MK", fill=(255, 255, 255), font=font)
            menu = pystray.Menu(
                pystray.MenuItem("Открыть", self.show_window),
                pystray.MenuItem("Быстрое напоминание", self.quick_reminder),
                pystray.MenuItem("Выход", self.quit_app)
            )
            self.tray_icon = pystray.Icon("Memory Keeper", icon_image, "Memory Keeper", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except:
            pass

    def show_window(self, icon=None):
        self.page.window.visible = True
        self.page.update()

    def quick_reminder(self, icon=None):
        self.show_notification("Проверьте важные дела!")

    def quit_app(self, icon=None):
        if self.tray_icon:
            self.tray_icon.stop()
        sys.exit(0)

    def start_scheduler(self):
        def check_reminders():
            while True:
                now = datetime.now()
                updated = False
                for r in self.data.get("reminders", []):
                    if not r.get("done"):
                        try:
                            dt = datetime.fromisoformat(r["datetime"].replace("Z", "+00:00"))
                            if dt <= now:
                                self.show_notification(r["text"])
                                r["done"] = True
                                updated = True
                        except:
                            pass
                if updated:
                    save_data(self.data)
                    self.update_reminder_list()
                time.sleep(15)
        threading.Thread(target=check_reminders, daemon=True).start()

    def show_notification(self, text):
        try:
            plyer.notification.notify(
                title="🔔 Memory Keeper",
                message=text,
                app_name="Memory Keeper",
                timeout=12
            )
        except:
            pass

if __name__ == "__main__":
    def main(page: ft.Page):
        MemoryKeeper(page)
    ft.app(target=main, view=ft.AppView.FLET_APP)