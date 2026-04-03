# ==========================================
# 依赖安装提示：
# 在运行此脚本之前，请在终端执行以下命令安装依赖：
# pip install PyMuPDF
# ==========================================

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import fitz  # PyMuPDF
import os

class PDFSplitterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("本地 PDF 批量切分工具")
        self.root.geometry("750x650")
        self.root.minsize(700, 600)
        
        self.pdf_path = None
        self.pdf_total_pages = 0
        self.output_dir = None
        
        self.setup_ui()
        
    def setup_ui(self):
        # 字体和内边距默认配置
        padding_opts = {'padx': 10, 'pady': 5}
        
        # --- 1. 核心交互与文件选择区 ---
        file_frame = ttk.LabelFrame(self.root, text="第一步：选择原始 PDF 文档")
        file_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.select_btn = ttk.Button(file_frame, text="选择源 PDF 文件", command=self.select_pdf)
        self.select_btn.grid(row=0, column=0, **padding_opts)
        
        self.file_label = ttk.Label(file_frame, text="未选择文件", foreground="gray")
        self.file_label.grid(row=0, column=1, sticky=tk.W, **padding_opts)
        
        self.outdir_btn = ttk.Button(file_frame, text="选择输出目录\n(默认同级目录)", command=self.select_output_dir)
        self.outdir_btn.grid(row=1, column=0, **padding_opts)
        
        self.outdir_label = ttk.Label(file_frame, text="默认保存在原始 PDF 同级目录", foreground="gray")
        self.outdir_label.grid(row=1, column=1, sticky=tk.W, **padding_opts)
        
        # --- 2. 多段切分参数输入区 ---
        task_frame = ttk.LabelFrame(self.root, text="第二步：设置切分任务 (最多5组，留空则忽略)")
        task_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 表头
        ttk.Label(task_frame, text="任务序号").grid(row=0, column=0, **padding_opts)
        ttk.Label(task_frame, text="起始页码 (包含)").grid(row=0, column=1, **padding_opts)
        ttk.Label(task_frame, text="结束页码 (包含)").grid(row=0, column=2, **padding_opts)
        ttk.Label(task_frame, text="切分后文件名").grid(row=0, column=3, sticky=tk.W, **padding_opts)
        
        self.input_rows = []
        for i in range(5):
            ttk.Label(task_frame, text=f"任务 {i+1}").grid(row=i+1, column=0, **padding_opts)
            
            start_var = tk.StringVar()
            end_var = tk.StringVar()
            name_var = tk.StringVar()
            
            start_entry = ttk.Entry(task_frame, textvariable=start_var, width=15)
            start_entry.grid(row=i+1, column=1, **padding_opts)
            
            end_entry = ttk.Entry(task_frame, textvariable=end_var, width=15)
            end_entry.grid(row=i+1, column=2, **padding_opts)
            
            name_entry = ttk.Entry(task_frame, textvariable=name_var, width=35)
            name_entry.grid(row=i+1, column=3, sticky=tk.W, **padding_opts)
            
            self.input_rows.append({
                'start': start_var,
                'end': end_var,
                'name': name_var
            })
            
        # --- 3. 执行控制区 ---
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.start_btn = ttk.Button(control_frame, text="▶ 开始切分", command=self.start_split, style="Accent.TButton")
        self.start_btn.pack(side=tk.LEFT, ipady=5, ipadx=10)
        
        # 用一个简单的Style高亮按钮（如果系统支持）
        style = ttk.Style()
        style.configure("Accent.TButton", font=("Helvetica", 10, "bold"))
        
        # --- 4. 日志与进度显示窗口 ---
        log_frame = ttk.LabelFrame(self.root, text="执行日志与进度")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.log_text = tk.Text(log_frame, state='disabled', wrap=tk.WORD, height=12, font=("Consolas", 10))
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,0), pady=5)
        
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0,5), pady=5)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        self.log("工具已启动，请先选择需要切分的原始 PDF 文件。")
        self.log("提示: 建议预先确认好每个切分任务的起始和结束页码。\n")

    def log(self, message):
        """线程安全的日志输出"""
        def append():
            self.log_text.config(state='normal')
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state='disabled')
        self.root.after(0, append)
        
    def select_pdf(self):
        file_path = filedialog.askopenfilename(
            title="选择 PDF 文件",
            filetypes=[("PDF Documents", "*.pdf"), ("All Files", "*.*")]
        )
        if file_path:
            try:
                # 使用 PyMuPDF 快速打开获取信息
                doc = fitz.open(file_path)
                self.pdf_total_pages = doc.page_count
                doc.close()
                
                self.pdf_path = file_path
                self.output_dir = os.path.dirname(file_path)
                
                self.file_label.config(text=f"已选择: {os.path.basename(file_path)} (共 {self.pdf_total_pages} 页)", foreground="blue")
                self.outdir_label.config(text=f"输出至: {self.output_dir}", foreground="black")
                self.log(f"已加载 PDF: {file_path}")
                self.log(f"文件总页数: {self.pdf_total_pages} 页")
                
            except Exception as e:
                messagebox.showerror("打开文件错误", f"无法读取该 PDF 文件:\n{e}")
                self.log(f"[错误] 加载 PDF 失败: {e}")

    def select_output_dir(self):
        dir_path = filedialog.askdirectory(title="选择输出目录")
        if dir_path:
            self.output_dir = dir_path
            self.outdir_label.config(text=f"输出至: {self.output_dir}", foreground="blue")
            self.log(f"已更改输出目录为: {self.output_dir}")

    def start_split(self):
        if not self.pdf_path:
            messagebox.showwarning("操作提示", "请先选择一个原始 PDF 文档！")
            return
            
        tasks = []
        # 校验输入
        for i, row in enumerate(self.input_rows):
            start_val = row['start'].get().strip()
            end_val = row['end'].get().strip()
            name_val = row['name'].get().strip()
            
            # 允许用户只填部分，完全为空的一行直接跳过
            if not start_val and not end_val and not name_val:
                continue
                
            # 部分填写视为信息不完整
            if not start_val or not end_val or not name_val:
                self.log(f"[错误] 任务 {i+1} 第一阶段校验失败：信息不完整（必须填写起始页、结束页和文件名）。")
                return 
                
            try:
                start_page = int(start_val)
                end_page = int(end_val)
            except ValueError:
                self.log(f"[错误] 任务 {i+1} 校验失败：页码必须是纯数字。")
                return
                
            if start_page < 1 or start_page > end_page or end_page > self.pdf_total_pages:
                self.log(f"[错误] 任务 {i+1} 校验失败：页码无效。要求 1 <= 起始页 <= 结束页 <= 总页数({self.pdf_total_pages}页)。")
                return
                
            # 自动补充 .pdf 后缀
            if not name_val.lower().endswith('.pdf'):
                name_val += '.pdf'
                
            tasks.append({
                'row_index': i + 1,
                'start': start_page,
                'end': end_page,
                'filename': name_val
            })
            
        if len(tasks) == 0:
            self.log("[提示] 没有检测到有效的切分任务，请至少填写一行信息。")
            return
            
        # 禁用按钮，防止重复点击
        self.start_btn.config(state='disabled')
        
        # 开启后台线程执行切分，防止主 UI 假死
        thread = threading.Thread(target=self.process_split, args=(tasks,), daemon=True)
        thread.start()

    def process_split(self, tasks):
        self.log("\n>>> 开始执行批量切分任务...")
        doc = None
        try:
            doc = fitz.open(self.pdf_path)
            
            for task in tasks:
                start_page = task['start']
                end_page = task['end']
                filename = task['filename']
                row_idx = task['row_index']
                
                self.log(f"正在处理第 {row_idx} 个切分任务：{start_page}页 - {end_page}页...")
                
                # PyMuPDF 打开是 0 索引的
                start_idx = start_page - 1
                end_idx = end_page - 1
                
                try:
                    out_pdf = fitz.open()
                    out_pdf.insert_pdf(doc, from_page=start_idx, to_page=end_idx)
                    
                    out_path = os.path.join(self.output_dir, filename)
                    out_pdf.save(out_path)
                    out_pdf.close()
                    
                    self.log(f"  --> [成功] 任务 {row_idx} 已保存至: {filename}")
                except Exception as e:
                    self.log(f"  --> [失败] 任务 {row_idx} 发生错误: {e}")
                    
            self.log("所有切分任务执行完成！")
            self.log("-----------------------------------------")
            
        except Exception as e:
            self.log(f"[严重错误] PDF 处理异常: {e}")
            
        finally:
            if doc:
                doc.close()
            # 恢复按钮状态
            self.root.after(0, lambda: self.start_btn.config(state='normal'))

if __name__ == "__main__":
    root = tk.Tk()
    app = PDFSplitterApp(root)
    root.mainloop()
