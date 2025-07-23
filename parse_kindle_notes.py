import re
import os
from collections import defaultdict

def sanitize_filename(filename):
    """
    清理文件名，移除或替换Windows和macOS/Linux中不允许的字符。
    """
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', filename)
    sanitized = sanitized.strip('. ')
    return sanitized

def merge_consecutive_notes(sorted_notes):
    """
    合并内容上连续的笔记。
    例如，将位置 #1008-1009 和 #1009-1009 的笔记合并。
    """
    if not sorted_notes:
        return []

    merged_notes = []
    # 从第一条笔记开始
    current_note = sorted_notes[0].copy()

    for next_note in sorted_notes[1:]:
        # 提取位置信息以判断是否连续
        # current_match = re.search(r'#(\d+)(?:-(\d+))?', current_note['metadata'])
        # next_match = re.search(r'#(\d+)(?:-(\d+))?', next_note['metadata'])
        # A simple heuristic: if the content seems to follow, merge it.
        # For Kindle, consecutive highlights on the same passage often lack punctuation at the end of the first part.
        
        # 一个更简单有效的判断方法：如果前一条笔记的结尾不是标点，很可能是一个长段落被截断了。
        if not current_note['content'].strip()[-1] in '。！？】”)]':
             # 合并内容
            current_note['content'] += ' ' + next_note['content']
            # 更新元数据为最后一条笔记的元数据
            current_note['metadata'] = next_note['metadata']
        else:
            # 如果不连续，则将当前笔记存入结果列表，并开始处理下一条
            merged_notes.append(current_note)
            current_note = next_note.copy()

    # 不要忘记添加最后一条处理中的笔记
    merged_notes.append(current_note)
    
    return merged_notes


def parse_kindle_notes(input_file='My Clippings.txt', output_dir='Kindle_Notes'):
    """
    解析Kindle笔记文件并按书名生成美观的Markdown文件。
    （已更新以处理书名前的乱码/BOM字符）
    """
    try:
        with open(input_file, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"错误：找不到文件 '{input_file}'。请确保文件名正确。")
        return
    except Exception as e:
        print(f"读取文件时发生错误: {e}")
        return

    notes_by_book = defaultdict(list)
    clippings = content.split('==========')

    for clip in clippings:
        clip = clip.strip()
        if not clip: continue
        lines = [line.strip() for line in clip.split('\n') if line.strip()]
        if len(lines) < 3: continue
        
        # --- 主要修改点在这里 ---
        # 移除书名前面可能存在的BOM字符(\ufeff)和其他不可见字符
        # lstrip('\ufeff') 会专门移除字符串左侧的BOM标记
        book_title = lines[0].lstrip('\ufeff').strip()
        # --- 修改结束 ---
        
        metadata = lines[1].lstrip('- ').strip()
        note_content = "\n".join(lines[2:]).strip()

        notes_by_book[book_title].append({
            'metadata': metadata,
            'content': note_content
        })

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for title, notes in notes_by_book.items():
        md_filename = sanitize_filename(title) + '.md'
        md_filepath = os.path.join(output_dir, md_filename)

        with open(md_filepath, 'w', encoding='utf-8') as f:
            f.write(f"# {title}\n\n")

            def sort_key(note):
                match = re.search(r'#(\d+)', note['metadata'])
                return int(match.group(1)) if match else 0
            sorted_notes = sorted(notes, key=sort_key)
            
            processed_notes = merge_consecutive_notes(sorted_notes)

            for note in processed_notes:
                note_content_in_callout = note['content'].replace('\n', '\n> ')
                f.write(f"> [!QUOTE]\n> {note_content_in_callout}\n\n")
                
                location_part, _, date_part = note['metadata'].partition('|')
                # 修复一个潜在的小问题：确保分割后不会有残留的'|'
                if not date_part:
                    date_part = "无日期信息"
                else:
                    date_part = date_part.strip()
                
                f.write(f"&emsp;*📍 {location_part.strip()}* \n")
                f.write(f"&emsp;*⏱️ {date_part}*\n\n")
                
                f.write("---\n\n")
    
    print(f"处理完成！总共为 {len(notes_by_book)} 本书生成了Markdown文件。")
    print(f"文件已保存在 '{output_dir}' 文件夹中。")

if __name__ == '__main__':
    # --- 使用说明 ---
    # 在这里设置你的Kindle笔记文件的【绝对路径】或【相对路径】
    KINDLE_NOTES_FILE = '/Users/spad0611/Documents/Documents/Code/book/My Clippings.txt'
    
    # 在这里设置你希望保存Markdown文件的目标文件夹
    OUTPUT_DIRECTORY = '/Users/spad0611/Documents/Documents/Code/book/sort'
    
    # 运行解析函数
    parse_kindle_notes(input_file=KINDLE_NOTES_FILE, output_dir=OUTPUT_DIRECTORY)