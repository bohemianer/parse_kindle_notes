import os
import opencc

# ================= 配置区域 =================
# 1. 在这里填写文件路径 或 文件夹路径
# 注意：如果是 Windows 路径，建议在引号前加 r，例如 r"C:\Users\Documents\Note.md"
TARGET_PATH = r"/Users/spad0611/Desktop/Matched_Notes/段永平商业逻辑篇段永平.md"

# 2. 转换模式
# 't2s'   = 繁体 -> 简体 (默认，仅字面转换)
# 'tw2sp' = 台湾繁体 -> 大陆简体 (包含词汇转换，如：滑鼠->鼠标，软体->软件)
CONVERSION_MODE = 'hk2s'  # 香港繁体 -> 大陆简体

# 3. 如果输入是文件夹，只处理以下后缀的文件
TARGET_EXTENSIONS = ('.md', '.txt', '.py', '.json')
# ===========================================

def convert_single_file(file_path, converter):
    """转换单个文件"""
    try:
        # 生成新文件名 (例如: readme.md -> readme_sc.md)
        file_dir, file_fullname = os.path.split(file_path)
        file_name, file_ext = os.path.splitext(file_fullname)
        
        # 防止重复转换已经转换过的文件
        if file_name.endswith("_sc"):
            print(f"跳过: {file_fullname} (看似已转换)")
            return

        output_name = f"{file_name}_sc{file_ext}"
        output_path = os.path.join(file_dir, output_name)

        # 读取
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 转换
        new_content = converter.convert(content)

        # 写入
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        print(f"✅ [成功] {file_fullname} -> {output_name}")

    except Exception as e:
        print(f"❌ [错误] {file_path}: {e}")

def main():
    # 检查路径是否存在
    if not os.path.exists(TARGET_PATH):
        print(f"错误: 找不到路径 '{TARGET_PATH}'")
        return

    # 初始化转换器 (只初始化一次，提高效率)
    print(f"正在初始化转换引擎 ({CONVERSION_MODE})...")
    converter = opencc.OpenCC(CONVERSION_MODE)
    
    # 判断是文件还是文件夹
    if os.path.isfile(TARGET_PATH):
        # --- 模式 A: 单个文件 ---
        print(f"正在处理单文件: {TARGET_PATH}")
        convert_single_file(TARGET_PATH, converter)
    
    elif os.path.isdir(TARGET_PATH):
        # --- 模式 B: 整个文件夹 ---
        print(f"正在扫描文件夹: {TARGET_PATH}")
        count = 0
        for root, dirs, files in os.walk(TARGET_PATH):
            for file in files:
                if file.lower().endswith(TARGET_EXTENSIONS):
                    full_path = os.path.join(root, file)
                    convert_single_file(full_path, converter)
                    count += 1
        
        if count == 0:
            print("未找到符合后缀要求的文本文件。")
        else:
            print(f"\n处理完成，共扫描 {count} 个文件。")

if __name__ == "__main__":
    main()