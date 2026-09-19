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
        self.root.title(f"Kindle 笔记自动匹配版 (v16.0 - {self.system})")
        self.root.geometry("750x850")
        
        # === 字体适配 ===
        if self.system == "Darwin":
            self.font_main = (".AppleSystemUIFont", 13)
            self.font_bold = (".AppleSystemUIFont", 14, "bold")
            self.font_large = (".AppleSystemUIFont", 20, "bold")
        elif self.system == "Windows":
            self.font_main = ("Microsoft YaHei UI", 10)
            self.font_bold = ("Microsoft YaHei UI", 11, "bold")
            self.font_large = ("Microsoft YaHei UI", 16, "bold")
        else:
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
        self.row_widgets = {} # 存储 UI 行引用以便自动选择

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
        tk.Label(self.root, text="Kindle 笔记智能导出", font=self.font_large, bg=self.colors["window_bg"], fg=self.colors["text_pri"], pady=15).pack()
        
        # Step 1: Clippings
        card1 = tk.Frame(self.root, bg=self.colors["card_bg"]); card1.pack(fill="x", padx=20, pady=5)
        tk.Label(card1, text="1. 加载 My Clippings.txt", font=self.font_main, bg=self.colors["card_bg"], fg=self.colors["text_sec"]).pack(anchor="w", padx=10, pady=5)
        row1 = tk.Frame(card1, bg=self.colors["card_bg"]); row1.pack(fill="x", padx=10, pady=5)
        tk.Entry(row1, textvariable=self.clippings_path, font=self.font_main, bg=self.colors["input_bg"], fg="white", bd=0).pack(side="left", fill="x", expand=True, ipady=6)
        self.DarkButton(row1, "📂 浏览", self.browse_clippings, font_cfg=self.font_main).pack(side="right", padx=5)

        # Step 2: ePub (提前到第二步)
        card3 = tk.Frame(self.root, bg=self.colors["card_bg"]); card3.pack(fill="x", padx=20, pady=5)
        self.lbl_epub_status = tk.Label(card3, text="2. 解析 ePub (将自动匹配书籍)", font=self.font_main, bg=self.colors["card_bg"], fg=self.colors["text_sec"])
        self.lbl_epub_status.pack(anchor="w", padx=10, pady=5)
        row3 = tk.Frame(card3, bg=self.colors["card_bg"]); row3.pack(fill="x", padx=10, pady=5)
        tk.Entry(row3, textvariable=self.target_epub_path, font=self.font_main, bg=self.colors["input_bg"], fg="white", bd=0).pack(side="left", fill="x", expand=True, ipady=6)
        self.DarkButton(row3, "🔗 选择并解析", self.browse_epub, font_cfg=self.font_main).pack(side="right", padx=5)

        # Step 3: 列表预览
        tk.Label(self.root, text="匹配结果预览:", font=self.font_main, bg=self.colors["window_bg"], fg=self.colors["text_sec"]).pack(anchor="w", padx=25, pady=(10,0))
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
        self._setup_mouse_wheel()

        # Step 4: Export
        self.btn_export = self.DarkButton(self.root, "🚀 导出笔记", self.run_export, font_cfg=self.font_bold, bg=self.colors["accent"])
        self.btn_export.pack(fill="x", padx=20, pady=20)
        self.btn_export.set_enabled(False)

    # ================= 逻辑核心 =================
    def browse_clippings(self):
        f = filedialog.askopenfilename(filetypes=[("Text", "*.txt")])
        if f: 
            self.clippings_path.set(f)
            self.load_clippings()

    def browse_epub(self):
        if not self.parsed_notes:
            messagebox.showwarning("提示", "请先加载 My Clippings.txt")
            return
        f = filedialog.askopenfilename(filetypes=[("Epub", "*.epub")])
        if f: 
            self.target_epub_path.set(f)
            self.parse_epub(f)

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
                    title = lines[0].strip().replace('\ufeff', '')
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
            messagebox.showerror("错误", f"解析失败: {str(e)}")

    def parse_epub(self, epub_path):
        self.lbl_epub_status.config(text="正在解析并匹配...", fg=self.colors["warning"])
        self.root.update()
        try:
            book = epub.read_epub(epub_path)
            
            # --- 核心改进：自动匹配书籍 ---
            epub_title = ""
            meta_titles = book.get_metadata('DC', 'title')
            if meta_titles:
                epub_title = meta_titles[0][0] # 提取 ePub 标题文本
            
            # 模糊匹配 Kindle 列表
            matched_title = self.find_best_match(epub_title)
            
            # 解析章节逻辑 (增强版：支持任意层级嵌套、epub.Section、多 anchor 及文件名归一化)
            self.epub_chapters = []
            toc_map = {}
            toc_anchors = defaultdict(list)

            def extract_toc(toc_list, parent_title=None, current_depth=2):
                for item in toc_list:
                    if isinstance(item, epub.Link):
                        href_full = item.href
                        file_part, _, anchor_part = href_full.partition('#')
                        entry = (item.title.strip(), current_depth, parent_title)
                        if file_part not in toc_map:
                            toc_map[file_part] = entry
                        base_name = os.path.basename(file_part)
                        if base_name not in toc_map:
                            toc_map[base_name] = entry
                        if anchor_part:
                            toc_anchors[file_part].append((anchor_part, *entry))
                            toc_anchors[base_name].append((anchor_part, *entry))
                    elif isinstance(item, epub.Section):
                        title = item.title.strip() if item.title else ""
                        href = getattr(item, 'href', '') or ''
                        if href:
                            file_part, _, anchor_part = href.partition('#')
                            entry = (title, current_depth, parent_title)
                            if file_part not in toc_map:
                                toc_map[file_part] = entry
                            base_name = os.path.basename(file_part)
                            if base_name not in toc_map:
                                toc_map[base_name] = entry
                            if anchor_part:
                                toc_anchors[file_part].append((anchor_part, *entry))
                                toc_anchors[base_name].append((anchor_part, *entry))
                    elif isinstance(item, (list, tuple)):
                        if len(item) == 0:
                            continue
                        first = item[0]
                        first_title = getattr(first, 'title', '')
                        if not first_title and isinstance(first, str):
                            first_title = first
                        first_title = first_title.strip() if first_title else None
                        first_href = getattr(first, 'href', '') or ''
                        if first_href:
                            file_part, _, anchor_part = first_href.partition('#')
                            entry = (first_title, current_depth, parent_title)
                            if file_part not in toc_map:
                                toc_map[file_part] = entry
                            base_name = os.path.basename(file_part)
                            if base_name not in toc_map:
                                toc_map[base_name] = entry
                            if anchor_part:
                                toc_anchors[file_part].append((anchor_part, *entry))
                                toc_anchors[base_name].append((anchor_part, *entry))
                        
                        next_parent = first_title or parent_title
                        if len(item) > 1 and isinstance(item[1], (list, tuple)):
                            extract_toc(item[1], parent_title=next_parent, current_depth=current_depth+1)
                        else:
                            for sub in item[1:]:
                                extract_toc([sub], parent_title=next_parent, current_depth=current_depth+1)

            if hasattr(book, 'toc') and book.toc:
                extract_toc(book.toc)

            # 按 Spine 线性阅读顺序获取文档，若无则使用 get_items
            spine_items = []
            if hasattr(book, 'spine') and book.spine:
                for s in book.spine:
                    item_id = s[0] if isinstance(s, (list, tuple)) else s
                    doc_item = book.get_item_with_id(item_id)
                    if doc_item and doc_item.get_type() == ebooklib.ITEM_DOCUMENT:
                        spine_items.append(doc_item)
            docs_to_process = spine_items if spine_items else [it for it in book.get_items() if it.get_type() == ebooklib.ITEM_DOCUMENT]

            idx = 0
            last = {"title": "前言", "depth": 2, "parent": None}
            running_chapter = None
            for item in docs_to_process:
                name = item.get_name()
                base_name = os.path.basename(name)
                soup = BeautifulSoup(item.get_content(), 'html.parser')

                # 匹配章节名：优先完整路径，其次文件名
                title, depth, parent = "", 2, None
                if name in toc_map:
                    title, depth, parent = toc_map[name]
                elif base_name in toc_map:
                    title, depth, parent = toc_map[base_name]
                else:
                    # 尝试从 h1-h4 标签中读取
                    for t, d in {'h1':2, 'h2':3, 'h3':4}.items():
                        found = soup.find(t)
                        if found and 0 < len(found.text.strip()) < 60:
                            title, depth = found.text.strip(), d
                            if d == 2: parent = None
                            else: parent = last["parent"]
                            break
                    if not title:
                        # 尝试从 class 带 title / chapter / heading 的元素中读取
                        candidate = soup.find(class_=re.compile(r"title|chapter|heading", re.I))
                        if candidate and 0 < len(candidate.text.strip()) < 60:
                            title, depth, parent = candidate.text.strip(), 3, last["parent"]
                    if not title:
                        # 尝试匹配常见章节标题正则
                        chap_regex = re.compile(r'^(第[0-9一二三四五六七八九十百千]+[章卷节回部]|Chapter\s+\d+|[•·]\s*\d+\s*[•·])\s*(.*)', re.I)
                        for p in soup.find_all(['p', 'div'])[:5]:
                            p_text = p.get_text().strip()
                            if 0 < len(p_text) < 60 and chap_regex.match(p_text):
                                title, depth, parent = p_text, 3, last["parent"]
                                break

                if not title:
                    title, depth, parent = last["title"], last["depth"], last["parent"]
                else:
                    last = {"title": title, "depth": depth, "parent": parent}

                if depth == 2:
                    running_chapter = title
                if depth > 2 and parent is None and running_chapter:
                    parent = running_chapter

                self.epub_chapters.append({
                    "index": idx,
                    "title": title,
                    "clean_text": self.clean_text_for_match(soup.get_text()),
                    "depth": depth,
                    "parent": parent
                })
                idx += 1

            self.is_epub_ready = True
            
            # 如果找到了匹配的书籍，自动选择它
            if matched_title:
                self.on_select_book(matched_title)
                self.lbl_epub_status.config(text=f"✅ 已自动匹配: {matched_title[:30]}...", fg=self.colors["success"])
                self.btn_export.set_enabled(True)
            else:
                self.lbl_epub_status.config(text="⚠ 解析成功但未找到匹配书籍，请手动点击列表", fg=self.colors["warning"])
                
        except Exception as e:
            self.lbl_epub_status.config(text="❌ 解析失败", fg="red")
            traceback.print_exc()

    def find_best_match(self, epub_title):
        """简单的模糊匹配：检查 ePub 标题是否包含在 Kindle 书名中，反之亦然"""
        if not epub_title: return None
        
        target = self.clean_text_for_match(epub_title).lower()
        
        # 1. 精确包含匹配
        for book in self.book_list:
            clean_book = self.clean_text_for_match(book).lower()
            if target in clean_book or clean_book in target:
                return book
        
        # 2. 如果没找到，尝试匹配前 5 个字符 (应对长书名差异)
        if len(target) > 5:
            short_target = target[:8]
            for book in self.book_list:
                if short_target in self.clean_text_for_match(book).lower():
                    return book
        return None

    def render_book_list(self):
        for w in self.inner_list.winfo_children(): w.destroy()
        self.row_widgets = {}
        for title in self.book_list:
            display_title = title.strip()
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

    def on_select_book(self, title):
        # 取消之前的选择
        if self.selected_book and self.selected_book in self.row_widgets:
            w = self.row_widgets[self.selected_book]
            w["frame"].config(bg=self.colors["card_bg"])
            w["label"].config(bg=self.colors["card_bg"])
        
        # 设置新选择
        self.selected_book = title
        if title in self.row_widgets:
            w = self.row_widgets[title]
            w["frame"].config(bg=self.colors["accent"])
            w["label"].config(bg=self.colors["accent"])
            # 自动滚动到该位置
            self.cvs.yview_moveto(w["frame"].winfo_y() / self.inner_list.winfo_height() if self.inner_list.winfo_height() > 0 else 0)
            
        if self.is_epub_ready: 
            self.btn_export.set_enabled(True)

    # ================= 其他辅助函数 (保持不变) =================
    def clean_text_for_match(self, text):
        return "".join(re.findall(r'\w+', str(text)))

    def clean_note_content(self, text):
        text = text.strip()
        text = re.sub(r'[\(（]\d{4}-?$', '', text) 
        text = re.sub(r'[\(（]$', '', text)       
        return text.strip()

    def _setup_mouse_wheel(self):
        def _on_mousewheel(event):
            if self.system == "Windows": self.cvs.yview_scroll(int(-1 * (event.delta / 120)), "units")
            else: self.cvs.yview_scroll(int(-1 * event.delta), "units")
        self.cvs.bind_all("<MouseWheel>", _on_mousewheel)

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
        if not self.selected_book: return
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
                    for n in buckets[idx]: f.write(f"> {n}\n\n")
            if unmatched:
                f.write("---\n## 未归类笔记\n\n")
                for n in unmatched: f.write(f"> {n}\n\n")

        messagebox.showinfo("完成", f"导出成功！包含笔记: {len(optimized_notes)} 条\n文件已保存至桌面 Matched_Notes 文件夹")
        try:
            if self.system == "Windows": os.startfile(desktop)
            elif self.system == "Darwin": subprocess.call(["open", desktop])
            else: subprocess.call(["xdg-open", desktop])
        except: pass

if __name__ == "__main__":
    root = tk.Tk()
    app = SmartBookExporter(root)
    root.mainloop()