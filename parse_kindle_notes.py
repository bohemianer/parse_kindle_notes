import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import re
import platform
import subprocess
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from collections import defaultdict
import traceback

class SmartBookExporter:
    def __init__(self, root):
        self.root = root
        self.system = platform.system()
        self.root.title(f"Kindle 笔记导出 (v15.8 最终稳定版 - {self.system})")
        self.root.geometry("750x850")
        
        # === 字体适配 ===
        if self.system == "Darwin": # MacOS
            self.font_main = (".AppleSystemUIFont", 13)
            self.font_bold = (".AppleSystemUIFont", 14, "bold")
            self.font_large = (".AppleSystemUIFont", 20, "bold")
        elif self.system == "Windows": # Windows
            self.font_main = ("Microsoft YaHei UI", 10)
            self.font_bold = ("Microsoft YaHei UI", 11, "bold")
            self.font_large = ("Microsoft YaHei UI", 16, "bold")
        else: # Linux
            self.font_main = ("Helvetica", 11)
            self.font_bold = ("Helvetica", 12, "bold")
            self.font_large = ("Helvetica", 18, "bold")

        self.colors = {
            "window_bg": "#1C1C1E",
            "card_bg":   "#2C2C2E",
            "text_pri":  "#FFFFFF",
            "text_sec":  "#98989D",
            "accent":    "#0A84FF",
            "input_bg":  "#1C1C1E",
            "success":   "#30D158",
            "warning":   "#FF9F0A"
        }
        
        self.root.configure(bg=self.colors["window_bg"])
        
        self.clippings_path = tk.StringVar()
        self.target_epub_path = tk.StringVar()
        self.parsed_notes = {}
        self.book_list = []
        self.selected_book = None
        self.epub_chapters = []
        self.is_epub_ready = False
        
        default_path = os.path.join(os.path.expanduser("~/Documents"), "My Clippings.txt")
        if os.path.exists(default_path):
            self.clippings_path.set(default_path)

        self._init_ui()

    # ================= UI 部分 =================
    class DarkButton(tk.Label):
        def __init__(self, parent, text, command, font_cfg, bg="#444444", fg="white"):
            super().__init__(parent, text=text, bg=bg, fg=fg, font=font_cfg, padx=15, pady=6, cursor="hand2")
            self.command = command
            self.normal_bg = bg
            self.hover_bg = self._adjust_color(bg, 20)
            self.is_disabled = False
            self.bind("<Button-1>", lambda e: self.command() if not self.is_disabled else None)
            self.bind("<Enter>", lambda e: self.config(bg=self.hover_bg) if not self.is_disabled else None)
            self.bind("<Leave>", lambda e: self.config(bg=self.normal_bg) if not self.is_disabled else None)

        def set_enabled(self, enabled):
            self.is_disabled = not enabled
            self.config(bg=self.normal_bg if enabled else "#333333", fg="white" if enabled else "#666666", cursor="hand2" if enabled else "arrow")

        def _adjust_color(self, hex_color, step):
            try: return f"#{min(255, int(hex_color[1:3], 16)+step):02x}{min(255, int(hex_color[3:5], 16)+step):02x}{min(255, int(hex_color[5:7], 16)+step):02x}"
            except: return hex_color

    def _init_ui(self):
        tk.Label(self.root, text="Kindle 笔记导出", font=self.font_large, bg=self.colors["window_bg"], fg=self.colors["text_pri"], pady=15).pack()
        
        # Step 1
        card1 = tk.Frame(self.root, bg=self.colors["card_bg"]); card1.pack(fill="x", padx=20, pady=5)
        tk.Label(card1, text="1. 加载 My Clippings.txt", font=self.font_main, bg=self.colors["card_bg"], fg=self.colors["text_sec"]).pack(anchor="w", padx=10, pady=5)
        row1 = tk.Frame(card1, bg=self.colors["card_bg"]); row1.pack(fill="x", padx=10, pady=5)
        tk.Entry(row1, textvariable=self.clippings_path, font=self.font_main, bg=self.colors["input_bg"], fg="white", bd=0).pack(side="left", fill="x", expand=True, ipady=6)
        self.DarkButton(row1, "📂 浏览", self.browse_clippings, font_cfg=self.font_main).pack(side="right", padx=5)

        # Step 2: 列表区域
        card2 = tk.Frame(self.root, bg=self.colors["card_bg"])
        card2.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.cvs = tk.Canvas(card2, bg=self.colors["card_bg"], bd=0, highlightthickness=0)
        self.cvs.pack(side="left", fill="both", expand=True)
        
        scr = ttk.Scrollbar(card2, orient="vertical", command=self.cvs.yview)
        scr.pack(side="right", fill="y")
        self.cvs.configure(yscrollcommand=scr.set)
        
        self.inner_list = tk.Frame(self.cvs, bg=self.colors["card_bg"])
        self.cvs_window = self.cvs.create_window((0,0), window=self.inner_list, anchor="nw", width=700)
        
        self.inner_list.bind("<Configure>", lambda e: self.cvs.configure(scrollregion=self.cvs.bbox("all")))
        self.cvs.bind("<Configure>", lambda e: self.cvs.itemconfig(self.cvs_window, width=e.width))

        # === 鼠标滚轮逻辑 ===
        self._setup_mouse_wheel()

        # Step 3
        card3 = tk.Frame(self.root, bg=self.colors["card_bg"]); card3.pack(fill="x", padx=20, pady=5)
        self.lbl_epub_status = tk.Label(card3, text="等待选择 ePub...", font=self.font_main, bg=self.colors["card_bg"], fg=self.colors["text_sec"])
        self.lbl_epub_status.pack(anchor="w", padx=10, pady=5)
        row3 = tk.Frame(card3, bg=self.colors["card_bg"]); row3.pack(fill="x", padx=10, pady=5)
        tk.Entry(row3, textvariable=self.target_epub_path, font=self.font_main, bg=self.colors["input_bg"], fg="white", bd=0).pack(side="left", fill="x", expand=True, ipady=6)
        self.DarkButton(row3, "🔗 解析 ePub", self.browse_epub, font_cfg=self.font_main).pack(side="right", padx=5)

        # Step 4
        self.btn_export = self.DarkButton(self.root, "🚀 导出笔记", self.run_export, font_cfg=self.font_bold, bg=self.colors["accent"])
        self.btn_export.pack(fill="x", padx=20, pady=20)
        self.btn_export.set_enabled(False)

    # ================= 鼠标滚轮逻辑 =================
    def _setup_mouse_wheel(self):
        def _on_mousewheel(event):
            if self.system == "Windows":
                self.cvs.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif self.system == "Darwin":
                self.cvs.yview_scroll(int(-1 * event.delta), "units")

        def _on_linux_scroll_up(event):
            self.cvs.yview_scroll(-1, "units")
            
        def _on_linux_scroll_down(event):
            self.cvs.yview_scroll(1, "units")

        def _bind_to_mouse(event):
            if self.system == "Linux":
                self.cvs.bind_all("<Button-4>", _on_linux_scroll_up)
                self.cvs.bind_all("<Button-5>", _on_linux_scroll_down)
            else:
                self.cvs.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_from_mouse(event):
            if self.system == "Linux":
                self.cvs.unbind_all("<Button-4>")
                self.cvs.unbind_all("<Button-5>")
            else:
                self.cvs.unbind_all("<MouseWheel>")

        self.cvs.bind('<Enter>', _bind_to_mouse)
        self.cvs.bind('<Leave>', _unbind_from_mouse)

    # ================= 辅助函数 =================
    def clean_text_for_match(self, text):
        return "".join(re.findall(r'\w+', str(text)))

    def clean_note_content(self, text):
        text = text.strip()
        text = re.sub(r'[\(（]\d{4}-?$', '', text) 
        text = re.sub(r'[\(（]$', '', text)       
        return text.strip()

    def browse_clippings(self):
        f = filedialog.askopenfilename(filetypes=[("Text", "*.txt")])
        if f: self.clippings_path.set(f); self.load_clippings()

    def browse_epub(self):
        f = filedialog.askopenfilename(filetypes=[("Epub", "*.epub")])
        if f: self.target_epub_path.set(f); self.parse_epub(f)

    def load_clippings(self):
        path = self.clippings_path.get()
        if not os.path.exists(path): return
        self.parsed_notes = {}
        try:
            with open(path, 'r', encoding='utf-8-sig', errors='ignore') as f: content = f.read()
            clips = content.split('==========')
            for clip in clips:
                lines = clip.strip().split('\n')
                if len(lines) >= 2:
                    title = lines[0].strip()
                    note_start_idx = 0
                    for idx, line in enumerate(lines):
                        if line.strip() == "" and idx > 0:
                            note_start_idx = idx + 1
                            break
                    if note_start_idx == 0: note_start_idx = 2
                    note = "\n".join(lines[note_start_idx:]).strip()
                    if title and note:
                        if title not in self.parsed_notes: self.parsed_notes[title] = []
                        cleaned = self.clean_note_content(note)
                        if cleaned: self.parsed_notes[title].append(cleaned)
            self.book_list = sorted(list(self.parsed_notes.keys()))
            self.render_book_list()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("错误", f"解析失败: {str(e)}")

    def render_book_list(self):
        for w in self.inner_list.winfo_children(): w.destroy()
        self.row_widgets = {}
        for title in self.book_list:
            display_title = title.replace('\ufeff', '').strip()
            row = tk.Frame(self.inner_list, bg=self.colors["card_bg"], pady=8, padx=5)
            row.pack(fill="x")
            lbl = tk.Label(row, text=display_title, font=self.font_main, bg=self.colors["card_bg"], fg="white", anchor="w")
            lbl.pack(fill="x", padx=5)
            tk.Frame(self.inner_list, bg="#38383A", height=1).pack(fill="x")
            
            cmd = lambda e, t=title: self.on_select_book(t)
            row.bind("<Button-1>", cmd)
            lbl.bind("<Button-1>", cmd)
            self.row_widgets[title] = {"frame": row, "label": lbl}
        self.inner_list.update_idletasks()
        try: self.cvs.configure(scrollregion=self.cvs.bbox("all"))
        except: pass

    def on_select_book(self, title):
        if self.selected_book and self.selected_book in self.row_widgets:
            w = self.row_widgets[self.selected_book]
            w["frame"].config(bg=self.colors["card_bg"])
            w["label"].config(bg=self.colors["card_bg"])
        self.selected_book = title
        if title in self.row_widgets:
            w = self.row_widgets[title]
            w["frame"].config(bg=self.colors["accent"])
            w["label"].config(bg=self.colors["accent"])
        if self.is_epub_ready: self.btn_export.set_enabled(True)

    def parse_epub(self, epub_path):
        self.lbl_epub_status.config(text="解析中...", fg=self.colors["warning"])
        self.root.update()
        try:
            book = epub.read_epub(epub_path)
            self.epub_chapters = []
            toc_map = {}
            def parse_toc_recursive(toc, parent=None, depth=2):
                for item in toc:
                    if isinstance(item, epub.Link):
                        toc_map[item.href.split('#')[0]] = (item.title, depth, parent)
                    elif isinstance(item, (list, tuple)):
                        parse_toc_recursive(item, parent=parent, depth=depth+1)
            for item in book.toc:
                if isinstance(item, epub.Link): toc_map[item.href.split('#')[0]] = (item.title, 2, None)
                elif isinstance(item, (list, tuple)) and len(item)>0:
                    if isinstance(item[0], epub.Link):
                        toc_map[item[0].href.split('#')[0]] = (item[0].title, 2, None)
                        if len(item) > 1: parse_toc_recursive(item[1], parent=item[0].title, depth=3)
            
            idx = 0
            last = {"title": "前言", "depth": 2, "parent": None}
            running_chapter = None

            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    name = item.get_name()
                    soup = BeautifulSoup(item.get_content(), 'html.parser')
                    title, depth, parent = "", 2, None
                    if name in toc_map: title, depth, parent = toc_map[name]
                    else:
                        for t, d in {'h1':2, 'h2':3, 'h3':4}.items():
                            found = soup.find(t)
                            if found and 0 < len(found.text.strip()) < 50:
                                title, depth = found.text.strip(), d
                                if d==2: parent = None
                                else: parent = last["parent"]
                                break
                    if not title: title, depth, parent = last["title"], last["depth"], last["parent"]
                    else: last = {"title": title, "depth": depth, "parent": parent}
                    if depth == 2: running_chapter = title
                    if depth > 2 and parent is None and running_chapter: parent = running_chapter
                    self.epub_chapters.append({"index": idx, "title": title, "clean_text": self.clean_text_for_match(soup.get_text()), "depth": depth, "parent": parent})
                    idx += 1
            self.is_epub_ready = True
            self.lbl_epub_status.config(text=f"✅ 成功解析 {len(self.epub_chapters)} 章节", fg=self.colors["success"])
            if self.selected_book: self.btn_export.set_enabled(True)
        except Exception as e:
            self.lbl_epub_status.config(text="❌ 解析失败", fg="red"); print(e)

    def smart_deduplicate(self, note_list):
        if not note_list: return []
        clean_data = []
        for note in note_list: clean_data.append({"raw": note, "fingerprint": self.clean_text_for_match(note)})
        final_notes = []
        for i, item_i in enumerate(clean_data):
            is_subset = False
            for j, item_j in enumerate(clean_data):
                if i == j: continue 
                if item_i["fingerprint"] in item_j["fingerprint"] and len(item_j["fingerprint"]) > len(item_i["fingerprint"]):
                    is_subset = True; break
            if not is_subset: final_notes.append(item_i["raw"])
        return final_notes

    def run_export(self):
        title = self.selected_book
        notes = self.parsed_notes[title]
        unique_notes_source = []
        global_seen = set()
        for n in notes:
            fp = self.clean_text_for_match(n)
            if fp not in global_seen: global_seen.add(fp); unique_notes_source.append(n)
        optimized_notes = self.smart_deduplicate(unique_notes_source)
        
        buckets = defaultdict(list); unmatched = []
        for note in optimized_notes:
            fp = self.clean_text_for_match(note)[:20]
            found = False
            for chap in self.epub_chapters:
                if fp in chap["clean_text"]: buckets[chap["index"]].append(note); found = True; break
            if not found: unmatched.append(note)

        desktop = os.path.join(os.path.expanduser("~"), "Desktop", "Matched_Notes")
        if not os.path.exists(desktop): os.makedirs(desktop)
        
        # === 修复: 将正则操作移出 f-string，兼容 Python < 3.12 ===
        safe_title = re.sub(r'[^\w\-_]', '', title)
        path = os.path.join(desktop, f"{safe_title}.md")

        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n"); last_parent = None
            for chap in self.epub_chapters:
                idx = chap["index"]
                if idx in buckets:
                    if chap["depth"] == 2:
                        if chap["title"] != last_parent: f.write(f"## {chap['title']}\n\n"); last_parent = chap["title"]
                    else:
                        if chap["parent"] and chap["parent"] != last_parent: f.write(f"## {chap['parent']}\n\n"); last_parent = chap["parent"]
                        prefix = "###" if chap["parent"] else ("##" if chap["depth"]==2 else "###")
                        f.write(f"{prefix} {chap['title']}\n\n")
                    for n in buckets[idx]: f.write(f"> {n}\n\n"); f.write("\n")
            if unmatched:
                f.write("---\n## 未归类笔记\n\n")
                for n in unmatched: f.write(f"> {n}\n\n")

        messagebox.showinfo("完成", f"导出成功！包含笔记: {len(optimized_notes)} 条")
        try:
            if self.system == "Windows": os.startfile(desktop)
            elif self.system == "Darwin": subprocess.call(["open", desktop])
            else: subprocess.call(["xdg-open", desktop])
        except: pass

if __name__ == "__main__":
    root = tk.Tk()
    app = SmartBookExporter(root)
    root.mainloop()