import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import re
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

# ========================================================
# 🔧 DarkButton (保持不变)
# ========================================================
class DarkButton(tk.Label):
    def __init__(self, parent, text, command, bg="#444444", fg="white", font=None, height=1):
        super().__init__(parent, text=text, bg=bg, fg=fg, font=font, 
                         padx=15, pady=6, cursor="hand2")
        self.command = command
        self.normal_bg = bg
        self.hover_bg = self._adjust_color(bg, 20)
        self.disabled_bg = "#333333"
        self.disabled_fg = "#666666"
        self.is_disabled = False
        
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_hover)
        self.bind("<Leave>", self._on_leave)

    def _on_click(self, event):
        if not self.is_disabled and self.command:
            self.command()

    def _on_hover(self, event):
        if not self.is_disabled:
            self.config(bg=self.hover_bg)

    def _on_leave(self, event):
        if not self.is_disabled:
            self.config(bg=self.normal_bg)

    def set_enabled(self, enabled):
        if enabled:
            self.is_disabled = False
            self.config(bg=self.normal_bg, fg="white", cursor="hand2")
        else:
            self.is_disabled = True
            self.config(bg=self.disabled_bg, fg=self.disabled_fg, cursor="arrow")

    def _adjust_color(self, hex_color, step):
        try:
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            r = min(255, r + step)
            g = min(255, g + step)
            b = min(255, b + step)
            return f"#{r:02x}{g:02x}{b:02x}"
        except:
            return hex_color

# ========================================================
# 主程序逻辑
# ========================================================
class SmartBookExporter:
    def __init__(self, root):
        self.root = root
        self.root.title("Kindle 笔记导出 (v9.7 目录修复版)")
        self.root.geometry("750x850")
        
        self.colors = {
            "window_bg": "#1C1C1E",
            "card_bg":   "#2C2C2E",
            "text_pri":  "#FFFFFF",
            "text_sec":  "#98989D",
            "accent":    "#0A84FF",
            "divider":   "#38383A",
            "input_bg":  "#1C1C1E",
            "success":   "#30D158",
            "warning":   "#FF9F0A"
        }
        
        self.root.configure(bg=self.colors["window_bg"])
        self.font_main = (".AppleSystemUIFont", 13)
        self.font_small = (".AppleSystemUIFont", 11)

        self.clippings_path = tk.StringVar()
        self.target_epub_path = tk.StringVar()
        self.parsed_notes = {}
        self.book_list = []
        self.selected_book = None
        self.epub_chapters = []
        self.is_epub_ready = False
        self.row_widgets = {}

        default_path = os.path.join(os.path.expanduser("~/Documents"), "My Clippings.txt")
        if os.path.exists(default_path):
            self.clippings_path.set(default_path)

        self._init_ui()
        if self.clippings_path.get():
            self.load_clippings()

    def _init_ui(self):
        tk.Label(self.root, text="Kindle 笔记 + 章节聚合", font=(".AppleSystemUIFont", 20, "bold"),
                 bg=self.colors["window_bg"], fg=self.colors["text_pri"], pady=15).pack()

        # Step 1
        self._create_section_label("第一步：加载 My Clippings.txt")
        card1 = self._create_card(self.root)
        row1 = tk.Frame(card1, bg=self.colors["card_bg"])
        row1.pack(fill="x", pady=12, padx=15)
        ent = tk.Entry(row1, textvariable=self.clippings_path, bg=self.colors["input_bg"], fg=self.colors["text_sec"], bd=0, highlightthickness=0, insertbackground="white")
        ent.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 10))
        DarkButton(row1, text="📂 导入笔记", command=self.browse_clippings, bg="#444444", font=self.font_small).pack(side="right")

        # Step 2
        self._create_section_label("第二步：在列表中选择一本书")
        list_container = tk.Frame(self.root, bg=self.colors["card_bg"])
        list_container.pack(fill="both", expand=True, padx=20, pady=5)
        scrollbar = ttk.Scrollbar(list_container, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        self.canvas = tk.Canvas(list_container, bg=self.colors["card_bg"], bd=0, highlightthickness=0, yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.canvas.yview)
        self.inner_list = tk.Frame(self.canvas, bg=self.colors["card_bg"])
        self.canvas_window = self.canvas.create_window((0, 0), window=self.inner_list, anchor="nw")
        self.inner_list.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Step 3
        self._create_section_label("第三步：选择对应的 ePub (用于匹配章节)")
        card3 = self._create_card(self.root)
        self.lbl_epub_status = tk.Label(card3, text="等待选择 ePub 文件...", bg=self.colors["card_bg"], fg=self.colors["text_sec"], font=self.font_main, anchor="w")
        self.lbl_epub_status.pack(fill="x", padx=15, pady=(15, 5))
        row3 = tk.Frame(card3, bg=self.colors["card_bg"])
        row3.pack(fill="x", pady=(0, 15), padx=15)
        self.ent_epub = tk.Entry(row3, textvariable=self.target_epub_path, bg=self.colors["input_bg"], fg=self.colors["text_pri"], bd=0, highlightthickness=0, insertbackground="white")
        self.ent_epub.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 10))
        DarkButton(row3, text="🔗 解析 ePub", command=self.browse_epub, bg="#444444", font=self.font_small).pack(side="right")

        # Step 4
        btn_frame = tk.Frame(self.root, bg=self.colors["window_bg"], pady=20)
        btn_frame.pack(fill="x", padx=20)
        self.btn_export = DarkButton(btn_frame, text="🚀 导出聚合笔记", command=self.run_export, bg=self.colors["accent"], font=(".AppleSystemUIFont", 14, "bold"))
        self.btn_export.pack(fill="x")
        self.btn_export.set_enabled(False)

    def _create_section_label(self, text):
        tk.Label(self.root, text=text, bg=self.colors["window_bg"], fg=self.colors["text_sec"], font=self.font_small, anchor="w").pack(fill="x", padx=25, pady=(15, 5))

    def _create_card(self, parent):
        f = tk.Frame(parent, bg=self.colors["card_bg"])
        f.pack(fill="x", padx=20)
        return f

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta)), "units")

    def clean_text_for_match(self, text):
        if not text: return ""
        return re.sub(r'\s+', '', str(text))

    def check_export_status(self):
        if self.selected_book and self.is_epub_ready:
            self.btn_export.set_enabled(True)
            self.btn_export.config(bg=self.colors["accent"])
        else:
            self.btn_export.set_enabled(False)

    def browse_clippings(self):
        f = filedialog.askopenfilename(filetypes=[("Text", "*.txt")])
        if f:
            self.clippings_path.set(f)
            self.load_clippings()

    def browse_epub(self):
        f = filedialog.askopenfilename(filetypes=[("Epub", "*.epub")])
        if f:
            self.target_epub_path.set(f)
            self.parse_epub(f)

    def load_clippings(self):
        path = self.clippings_path.get()
        if not os.path.exists(path): return
        self.parsed_notes = {}
        try:
            with open(path, 'r', encoding='utf-8-sig', errors='ignore') as f:
                content = f.read()
            for clip in content.split('=========='):
                lines = clip.strip().split('\n')
                if len(lines) >= 2:
                    title = lines[0].strip()
                    note_content = "\n".join(lines[2:]).strip()
                    if title and note_content:
                        if title not in self.parsed_notes: self.parsed_notes[title] = []
                        self.parsed_notes[title].append(note_content)
            self.book_list = sorted(list(self.parsed_notes.keys()))
            self.render_book_list()
        except Exception as e:
            messagebox.showerror("Error", f"无法读取 Clippings: {e}")

    def render_book_list(self):
        for w in self.inner_list.winfo_children(): w.destroy()
        self.row_widgets = {}
        self.selected_book = None
        self.check_export_status()
        if not self.book_list:
            tk.Label(self.inner_list, text="未找到笔记", bg=self.colors["card_bg"], fg="white").pack(pady=20)
            return
        for title in self.book_list:
            row = tk.Frame(self.inner_list, bg=self.colors["card_bg"], pady=10, padx=10)
            row.pack(fill="x")
            tk.Frame(self.inner_list, bg=self.colors["divider"], height=1).pack(fill="x", padx=10)
            lbl = tk.Label(row, text=title, bg=self.colors["card_bg"], fg=self.colors["text_pri"], font=self.font_main, anchor="w")
            lbl.pack(fill="x", expand=True)
            cmd = lambda e, t=title: self.on_select_book(t)
            row.bind("<Button-1>", cmd)
            lbl.bind("<Button-1>", cmd)
            self.row_widgets[title] = {"frame": row, "label": lbl}

    def on_select_book(self, title):
        if self.selected_book and self.selected_book in self.row_widgets:
            prev = self.row_widgets[self.selected_book]
            prev["frame"].config(bg=self.colors["card_bg"])
            prev["label"].config(bg=self.colors["card_bg"], fg=self.colors["text_pri"])
        self.selected_book = title
        curr = self.row_widgets[title]
        curr["frame"].config(bg=self.colors["accent"])
        curr["label"].config(bg=self.colors["accent"], fg="white")
        self.check_export_status()

    # ========================================================
    # 核心修改：新增解析目录(TOC)的辅助函数
    # ========================================================
    def parse_toc(self, toc, toc_map):
        """递归解析 TOC，建立 文件名 -> 标题 的映射"""
        for item in toc:
            if isinstance(item, epub.Link):
                # epub.Link 的 href 可能包含 #锚点 (如 chapter01.html#section1)，需要去掉
                clean_href = item.href.split('#')[0]
                toc_map[clean_href] = item.title
            elif isinstance(item, (list, tuple)):
                self.parse_toc(item, toc_map) # 递归处理子章节

    def parse_epub(self, epub_path):
        self.is_epub_ready = False
        self.check_export_status()
        self.lbl_epub_status.config(text="正在解析 ePub 内容...", fg=self.colors["warning"])
        self.root.update()
        
        try:
            book = epub.read_epub(epub_path)
            self.epub_chapters = []
            
            # 1. 优先读取官方目录 (TOC)
            toc_map = {}
            self.parse_toc(book.toc, toc_map)
            
            # 2. 遍历实际文档
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    # 获取文件名 (例如 Text/chapter04.xhtml)
                    file_name = item.get_name()
                    
                    soup = BeautifulSoup(item.get_content(), 'html.parser')
                    title = ""
                    
                    # 策略 A: 先查目录表 (最准确)
                    if file_name in toc_map:
                        title = toc_map[file_name]
                    
                    # 策略 B: 目录里没有，再去 HTML 里硬抓 (后备)
                    if not title:
                        for tag in ['h1', 'h2', 'h3', 'h4']:
                            found = soup.find(tag)
                            if found:
                                title = found.get_text().strip()
                                break 
                    
                    # 策略 C: 还是没有，尝试 title 标签
                    if not title and soup.title: 
                        title = soup.title.get_text().strip()
                    
                    # 策略 D: 实在没办法了，才用文件名 (但前面几步通常能拦截住)
                    if not title: 
                        title = file_name

                    raw_text = soup.get_text()
                    clean_text = self.clean_text_for_match(raw_text)
                    
                    self.epub_chapters.append({'title': title, 'clean_text': clean_text})
            
            self.is_epub_ready = True
            self.lbl_epub_status.config(text=f"✅ 解析成功: 识别到 {len(self.epub_chapters)} 个章节", fg=self.colors["success"])
            self.check_export_status()
        except Exception as e:
            self.lbl_epub_status.config(text="❌ 解析失败", fg="red")
            messagebox.showerror("Epub Error", f"无法解析文件: {e}")

    def find_chapter_for_note(self, note_content):
        note_fingerprint = self.clean_text_for_match(note_content)
        if len(note_fingerprint) > 50: search_key = note_fingerprint[:50]
        else: search_key = note_fingerprint
        if not search_key: return "未知位置"
        
        for chapter in self.epub_chapters:
            if search_key in chapter['clean_text']:
                return chapter['title']
        return "未知位置"

    def run_export(self):
        if not self.selected_book or not self.is_epub_ready: return
        title = self.selected_book
        notes = self.parsed_notes[title]
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        output_folder = os.path.join(desktop_path, "Matched_Notes")
        if not os.path.exists(output_folder): os.makedirs(output_folder)
        safe_name = "".join([c for c in title if c.isalnum() or c in " -_"]).strip()
        file_path = os.path.join(output_folder, f"{safe_name}.md")
        
        # 提取作者
        output_header = title 
        match = re.search(r'(.*)\((.*)\)$', title)
        if match:
            output_header = match.group(2).strip()
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# {output_header}\n\n") # 只写作者
                
                match_count = 0
                last_chapter = None 
                
                for i, note in enumerate(notes):
                    current_title = self.find_chapter_for_note(note)
                    
                    if current_title != "未知位置":
                        match_count += 1
                    
                    if current_title != last_chapter:
                        f.write(f"### {current_title}\n\n")
                        last_chapter = current_title 
                    
                    f.write(f"> {note}\n\n")
                    f.write("\n")
            
            messagebox.showinfo("完成", f"导出成功！\n匹配了 {match_count}/{len(notes)} 条笔记。\n\n文件位于桌面：Matched_Notes")
            os.system(f"open '{output_folder}'")
            
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = SmartBookExporter(root)
    root.mainloop()