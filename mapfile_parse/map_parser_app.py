import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import re
import os

class MapParser:
    """
    Map 文件解析器类，用于提取 .map 文件中的变量信息。
    主要针对 GHS (Green Hills Software) 格式进行解析，但也具备一定的泛用性。
    """
    def __init__(self):
        self.variables = [] # 存储解析出的变量信息
        
    def parse_file(self, filepath):
        """
        按行解析 map 文件，提取变量名、起始地址、大小、类型等信息。
        带有容错机制的正则表达式提取。
        """
        self.variables.clear()
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.readlines()
        except Exception as e:
            raise Exception(f"读取文件失败: {str(e)}")
            
        for line in content:
            line = line.strip()
            if not line:
                continue
                
            # 使用空白字符分割
            tokens = line.split()
            if not tokens:
                continue
                
            parsed_var = None

            # 格式 1: [段名] 地址+大小 变量名 (例如 var_cleared_8 3463a969+000011 ComM_ChanState)
            # 或 地址+大小 变量名 (例如 3463a969+000011 ComM_ChanState)
            for i, token in enumerate(tokens):
                if '+' in token:
                    parts = token.split('+')
                    # 假定前半部分是 5~16 位的十六进制地址，后半部分是大小
                    if len(parts) == 2 and re.match(r'^[0-9a-fA-F]{5,16}$', parts[0]) and re.match(r'^[0-9a-fA-F]+$', parts[1]):
                        if i + 1 < len(tokens):
                            name_token = tokens[i+1]
                            section = tokens[i-1] if i > 0 else "Unknown"
                            # 去掉可能跟随的详细路径（例如 BootMgr...2FDATA 等）
                            name = name_token.split('...')[0]
                            parsed_var = {
                                'name': name,
                                'address_str': parts[0],
                                'size': parts[1],
                                'type': f"Variable / {section}"
                            }
                        break

            # 格式 2: [可能有空段名缩进] 地址 大小 变量名 (例如 3463a969 00000011 ComM_ChanState)
            if not parsed_var and len(tokens) >= 3:
                # 寻找连续的两个十六进制 (地址 和 大小) 及紧随其后的名称
                for i in range(len(tokens) - 2):
                    if re.match(r'^[0-9a-fA-F]{5,16}$', tokens[i]) and re.match(r'^[0-9a-fA-F]+$', tokens[i+1]):
                        name_token = tokens[i+2]
                        # 确保 token 不是特定关键字
                        if name_token.lower() not in ('object', 'func', 'data', 'bss', 'text', 'notyp'):
                            name = name_token.split('...')[0]
                            section = tokens[i-1] if i > 0 else "Unknown"
                            parsed_var = {
                                'name': name,
                                'address_str': tokens[i],
                                'size': tokens[i+1],
                                'type': f"Variable / {section}"
                            }
                            break

            # 格式 3: 常规编译器的 Name Address Size Type Bind Section
            if not parsed_var and 4 <= len(tokens) <= 7:
                name = tokens[0]
                addr_str = tokens[1]
                
                # 变量名不应以 . 或 * 开头 (通常是段名或文件注释)
                if not name.startswith('.') and not name.startswith('*'):
                    # 检查地址是否为合法的十六进制
                    if re.match(r'^(0x)?[0-9a-fA-F]{5,16}$', addr_str):
                        size_str = "0"
                        type_str = "Unknown"
                        
                        is_func = False
                        for token in tokens[2:]:
                            if re.match(r'^(0x)?[0-9a-fA-F]+$', token) and token.isdigit():
                                size_str = token
                            elif token.lower() in ('object', 'notyp', 'data', 'bss'):
                                type_str = token
                            elif token.lower() in ('func', 'code', 'text'):
                                is_func = True
                                
                        if not is_func:
                            section_name = ""
                            for token in reversed(tokens):
                                if token.startswith('.'):
                                    section_name = token
                                    break
                            
                            var_type_combined = f"{type_str} {section_name}".strip()
                            if not var_type_combined or var_type_combined == "Unknown":
                                var_type_combined = "Variable"
                                
                            parsed_var = {
                                'name': name,
                                'address_str': addr_str,
                                'size': size_str, # 保留原格式展示
                                'type': var_type_combined
                            }

            # 尝试在这个 line 中抓取可能包含的编译目标对象路径作为来源文件
            source_file = ""
            for t in tokens:
                if t.endswith('.o)') or t.endswith('.a') or t.endswith('.o') or t.endswith('.obj') or '.a(' in t:
                    source_file = t
                    break

            if parsed_var:
                try:
                    addr_val = int(parsed_var['address_str'], 16)
                    parsed_var['address_val'] = addr_val
                    parsed_var['address_str'] = hex(addr_val)
                    parsed_var['source'] = source_file
                    self.variables.append(parsed_var)
                except ValueError:
                    pass

        # === 增加增强型查重功能 ===
        # 有时候同一个变量在 Map 中多次出现，例如：
        # .data.CanSM_CommNoCommunication (Unknown)
        # CanSM_CommNoCommunication (data_C0)
        # E:/workspace/.../CanSM_src.a(CanSM_Merged.o)
        # 这些都被解析到了同一个 Address 和 Size。
        # 我们按照 (Address, Size) 分组，并保留“看起来最正常”的名称和有效段信息
        unique_vars = {}
        for var in self.variables:
            try:
                size_val = int(var['size'], 16)
            except ValueError:
                size_val = var['size']

            key = (var['address_val'], size_val)

            # --- 清理变量名称 ---
            clean_name = var['name']
            # 去除前缀 .data., .bss., .rodata. 等类似节区前缀
            for prefix in ['.data.', '.bss.', '.rodata.', '.sdata.', '.sbss.']:
                if clean_name.startswith(prefix):
                    clean_name = clean_name[len(prefix):]
            # 去除可能包含的绝对路径或者编码字符如 ..D.3A.2F (D:\) 或 ...
            if '..' in clean_name:
                clean_name = clean_name.split('..')[0]
            if '/' in clean_name or '\\' in clean_name or clean_name.endswith('.o)'):
                clean_name = clean_name.split('/')[-1].split('\\')[-1]

            var['name'] = clean_name  # 更新为净化后的名称

            # --- 计算该条记录的优先级 (越大越好) ---
            score = 0
            if clean_name and clean_name[0].isalpha():
                score += 50
            if var['type'].endswith('.o)'):
                score -= 100
            elif var['type'] == 'Variable / Unknown' or 'Unknown' in var['type']:
                score -= 10
            elif var['type'].startswith('Variable / .'):
                score -= 5
            else:
                score += 20 # 有真正的段名，如 data_C0_CORE_C0

            var['_score'] = score # 暂存分数

            if key not in unique_vars:
                unique_vars[key] = var
            else:
                existing = unique_vars[key]
                # 合并或保留最长的来源路径信息
                if var.get('source') and not existing.get('source'):
                    existing['source'] = var['source']
                elif var.get('source') and existing.get('source') and len(var['source']) > len(existing['source']):
                    existing['source'] = var['source']

                # 比较分数，更新优胜名字和类型
                if score > existing['_score']:
                    existing['name'] = var['name']
                    existing['type'] = var['type']
                    existing['_score'] = score
                elif score == existing['_score']:
                    # 如果分一样，且当前名称更短(不含路径)，也可优先
                    if len(clean_name) < len(existing['name']):
                        existing['name'] = clean_name

        # 清除内部算分标记并转回 list
        for var in unique_vars.values():
            var.pop('_score', None)

        self.variables = list(unique_vars.values())
        
        # 按照地址排序，方便后续展示或区间检索
        self.variables.sort(key=lambda x: x['address_val'])
        return len(self.variables)

    def search_by_name(self, name_query):
        """
        按照变量名查询 (支持部分包含匹配，忽略大​​小写)
        """
        results = []
        name_query = name_query.lower()
        for var in self.variables:
            if name_query in var['name'].lower():
                results.append(var)
        return results

    def search_by_address_range(self, start_addr, end_addr):
        """
        按照十六进制地址区间查找
        """
        results = []
        for var in self.variables:
            if start_addr <= var['address_val'] <= end_addr:
                results.append(var)
        return results


class MapParserApp:
    """
    基于 Tkinter 的 GUI 应用类，负责界面布局和交互逻辑
    """
    def __init__(self, root):
        self.root = root
        self.root.title("嵌入式 Map 文件解析与检索工具 (GHS)")
        self.root.geometry("850x650")
        
        self.parser = MapParser()
        self.current_file = ""
        
        self._setup_ui()
        
    def _setup_ui(self):
        style = ttk.Style()
        # 选择较为清晰的界面主题，取决于系统支持
        if 'clam' in style.theme_names():
            style.theme_use('clam')
            
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # --- 顶部：文件选择区 ---
        frame_file = ttk.LabelFrame(main_frame, text=" 1. 文件选择与解析 ", padding=10)
        frame_file.pack(fill=tk.X, pady=(0, 10))
        
        self.btn_select_file = ttk.Button(frame_file, text="打开 .map 文件", command=self.on_select_file)
        self.btn_select_file.pack(side=tk.LEFT, padx=5)
        
        self.entry_file_path = ttk.Entry(frame_file, state='readonly')
        self.entry_file_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # --- 中间部分：查询区 ---
        frame_query = ttk.Frame(main_frame)
        frame_query.pack(fill=tk.X, pady=(0, 10))
        
        # 功能区一：按变量名查询
        frame_name_query = ttk.LabelFrame(frame_query, text=" 2. 按变量名查询 ", padding=10)
        frame_name_query.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        ttk.Label(frame_name_query, text="输入需要检索的变量名:").pack(anchor=tk.W, padx=5, pady=(0, 5))
        
        search_box_frame = ttk.Frame(frame_name_query)
        search_box_frame.pack(fill=tk.X)
        self.entry_var_name = ttk.Entry(search_box_frame)
        self.entry_var_name.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.btn_query_name = ttk.Button(search_box_frame, text="查询变量", command=self.on_query_name)
        self.btn_query_name.pack(side=tk.RIGHT, padx=5)
        
        # 功能区二：按地址区间查询
        frame_addr_query = ttk.LabelFrame(frame_query, text=" 3. 按地址区间查询 ", padding=10)
        frame_addr_query.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        ttk.Label(frame_addr_query, text="起始地址(Hex):").grid(row=0, column=0, padx=5, pady=2, sticky=tk.E)
        self.entry_start_addr = ttk.Entry(frame_addr_query, width=15)
        self.entry_start_addr.grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(frame_addr_query, text="结束地址(Hex):").grid(row=1, column=0, padx=5, pady=2, sticky=tk.E)
        self.entry_end_addr = ttk.Entry(frame_addr_query, width=15)
        self.entry_end_addr.grid(row=1, column=1, padx=5, pady=2)
        
        self.btn_query_range = ttk.Button(frame_addr_query, text="区间遍历", command=self.on_query_range)
        self.btn_query_range.grid(row=0, column=2, rowspan=2, padx=10, pady=2)
        
        # --- 底部：输出与日志区 ---
        frame_output = ttk.LabelFrame(main_frame, text=" 输出终端 (日志与结果) ", padding=10)
        frame_output.pack(fill=tk.BOTH, expand=True)
        
        # 文本框与滚动条
        # 我们使用相对深色的背景以提升极客感和代码可视性
        self.text_output = tk.Text(frame_output, wrap=tk.NONE, font=("Consolas", 10), bg="#1e1e1e", fg="#d4d4d4")
        
        scrolly = ttk.Scrollbar(frame_output, orient=tk.VERTICAL, command=self.text_output.yview)
        scrollx = ttk.Scrollbar(frame_output, orient=tk.HORIZONTAL, command=self.text_output.xview)
        self.text_output.config(yscrollcommand=scrolly.set, xscrollcommand=scrollx.set)
        
        scrolly.pack(side=tk.RIGHT, fill=tk.Y)
        scrollx.pack(side=tk.BOTTOM, fill=tk.X)
        self.text_output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 输出操作按钮
        frame_out_ops = ttk.Frame(main_frame)
        frame_out_ops.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(frame_out_ops, text="清空输出屏幕", command=self.clear_output).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_out_ops, text="导出当前结果到文本文件...", command=self.export_output).pack(side=tk.LEFT, padx=5)

        self.log_message("[系统] 工具启动就绪。请点击左上角的“选择文件”按钮以解析 .map 文件。\n")

    def on_select_file(self):
        """ 处理用户点击选择文件的事件 """
        filepath = filedialog.askopenfilename(
            title="选择 Map 或 TXT 文件",
            filetypes=[("Map Files", "*.map"), ("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if filepath:
            self.current_file = filepath
            self.entry_file_path.config(state=tk.NORMAL)
            self.entry_file_path.delete(0, tk.END)
            self.entry_file_path.insert(0, filepath)
            self.entry_file_path.config(state='readonly')
            
            self.log_message(f"[系统] 正在准备解析文件: {filepath} ...")
            self.root.update_idletasks() # 刷新UI，让用户看到加载状态
            
            try:
                count = self.parser.parse_file(filepath)
                self.log_message(f"[成功] 解析完成！成功识别并提取出 {count} 个 全局变量/静态变量 / 内存段。\n")
            except Exception as e:
                self.log_message(f"[错误] 解析时发生异常: {str(e)}\n")
                messagebox.showerror("解析错误", str(e))

    def on_query_name(self):
        """ 根据变量名检索 """
        # 判断是否有文件解析过
        if not self.parser.variables:
            messagebox.showwarning("警告: 未解析", "请先选择并解析一个 map 文件！")
            return
            
        name_query = self.entry_var_name.get().strip()
        if not name_query:
            messagebox.showwarning("提示", "检索的变量名不能为空，请输入内容！")
            return
            
        self.log_message(f">>> 正在执行变量检索: '{name_query}'")
        results = self.parser.search_by_name(name_query)
        
        if not results:
            self.log_message("    -> 检索失败: 未找到任何匹配该名称的变量。\n")
        else:
            self.log_message(f"    -> 检索成功: 找到 {len(results)} 个匹配项:")
            for var in results:
                src = var.get('source', '')
                src_str = f" | 来源: {src}" if src else ""
                self.log_message(f"       [{var['type']:<18}] 变量名称: {var['name']:<25} 起始地址: {var['address_str']:<12} 大小(Size): {var['size']:<8}{src_str}")
            self.log_message("") # 空行分隔

    def on_query_range(self):
        """ 根据地址区间遍历 """
        if not self.parser.variables:
            messagebox.showwarning("警告: 未解析", "请先选择并解析一个 map 文件！")
            return
            
        start_str = self.entry_start_addr.get().strip()
        end_str = self.entry_end_addr.get().strip()
        
        if not start_str or not end_str:
            messagebox.showwarning("提示", "请输入完整的起始地址和结束地址！")
            return
            
        try:
            # 兼容包含 0x 或者仅纯数字/字母 的 16 进制输入
            start_addr = int(start_str, 16)
            end_addr = int(end_str, 16)
        except ValueError:
            messagebox.showerror("格式错误", f"非法的十六进制地址！\n\n请检查: '{start_str}' 到 '{end_str}'\n您可以输入类似 '0x34540000' 或纯数字 '34540000'")
            self.log_message(f"[错误] 解析至非法输入: {start_str} - {end_str}\n")
            return
            
        # 边界防呆判断
        if start_addr > end_addr:
            messagebox.showwarning("提示", f"逻辑错误：起始地址 ({hex(start_addr)}) 大于结束地址 ({hex(end_addr)})，请重新调整输入顺序！")
            return
            
        self.log_message(f">>> 正在执行区间检索: {hex(start_addr)} 到 {hex(end_addr)}")
        results = self.parser.search_by_address_range(start_addr, end_addr)
        
        if not results:
            self.log_message("    -> 检索失败: 在该地址区间范围内，目前未找到任何变量。\n")
        else:
            self.log_message(f"    -> 检索成功: 在区间内找到 {len(results)} 个变量对象 (列表已按地址升序排列):")
            
            # --- 内存大小计算 ---
            # 假设 start_addr 到 end_addr 为 [start, end) 或总容量为 end_addr - start_addr
            total_capacity = end_addr - start_addr
            if total_capacity <= 0:
                total_capacity = 1 # 防呆，如果在非法或者同一地址范围内
                
            used_memory = 0
            intervals = []
            for var in results:
                try:
                    size_val = int(var['size'], 16)
                except ValueError:
                    size_val = 0
                # 取实际和区间交叉的范围进行计算？一般简单把大小算即可。但严谨起见求个和。
                intervals.append((var['address_val'], var['address_val'] + size_val))
                
            # 合并覆盖的区间
            if intervals:
                intervals.sort()
                merged = []
                current_start, current_end = intervals[0]
                for s, e in intervals[1:]:
                    if s <= current_end:
                        current_end = max(current_end, e)
                    else:
                        merged.append((current_start, current_end))
                        current_start, current_end = s, e
                merged.append((current_start, current_end))
                
                # 校验计算在 [start_addr, end_addr] 范围内交集的已使用空间
                for s, e in merged:
                    s = max(s, start_addr)
                    e = min(e, end_addr)
                    if e > s:
                        used_memory += (e - s)
            
            remaining_memory = total_capacity - used_memory
            self.log_message(f"       [统计] 所选区间跨度: {total_capacity} bytes")
            self.log_message(f"       [统计] 目前已使用大小: {used_memory} bytes")
            self.log_message(f"       [统计] 还剩余可用空间: {remaining_memory if remaining_memory >= 0 else 0} bytes")
            self.log_message("")
            
            # 添加表头使输出视觉层级更好看
            self.log_message(f"       {'起始地址':<12} | {'大小':<6} | {'类型/段属性':<20} | {'变量名称':<25} | {'来源定义文件 (Source)'}")
            self.log_message(f"       {'-'*12}-+-{'-'*6}-+-{'-'*20}-+-{'-'*25}-+-{'-'*20}")
            for var in results:
                src = var.get('source', '')
                self.log_message(f"       {var['address_str']:<12} | {var['size']:<6} | {var['type']:<20} | {var['name']:<25} | {src}")
            self.log_message("")

    def log_message(self, message):
        """ 向多行输出终端追加文本，并自动滚动到底部以便能够直接看到最新消息 """
        self.text_output.insert(tk.END, message + "\n")
        self.text_output.see(tk.END)
        
    def clear_output(self):
        """ 清空当前输出终端的内容 """
        self.text_output.delete("1.0", tk.END)
        self.log_message("[系统] 终端已清空。\n")
        
    def export_output(self):
        """ 将当前输出终端显示的查询结果保存为其它的文本文件 """
        content = self.text_output.get("1.0", tk.END)
        if not content.strip():
            messagebox.showinfo("提示", "目前输出窗口没有实质内容，无需导出。")
            return
            
        filepath = filedialog.asksaveasfilename(
            title="将输出结果导出并另存",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("导出成功", f"当前所显示的结果已经成功保存到了:\n{filepath}")
                self.log_message(f"[系统] 输出内容已成功导出 -> {filepath}\n")
            except Exception as e:
                messagebox.showerror("导出错误", f"在导出文件期间意外发生了错误:\n{str(e)}")

if __name__ == "__main__":
    # 实例化主窗口并在桌面建立事件循环
    root = tk.Tk()
    app = MapParserApp(root)
    root.mainloop()
