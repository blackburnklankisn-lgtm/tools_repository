import tkinter as tk
from tkinter import filedialog, messagebox
import os
import pypandoc
import subprocess
import sys

def convert_md_to_docx(md_filepath, docx_filepath):
    try:
        # Try to use pypandoc directly which will look for pandoc in PATH
        pypandoc.convert_file(md_filepath, 'docx', outputfile=docx_filepath)
    except OSError:
        # If pypandoc fails to find pandoc, we can try to find it in the default winget install path
        pandoc_path = r"C:\Program Files\Pandoc\pandoc.exe"
        if os.path.exists(pandoc_path):
            subprocess.run([pandoc_path, md_filepath, "-o", docx_filepath], check=True)
        else:
            raise Exception("Pandoc is not installed or not found in PATH. Please install Pandoc (e.g. via 'winget install pandoc') to support mathematical formulas.")

class MdToDocxApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Markdown to DOCX Converter")
        self.root.geometry("550x250")
        self.root.configure(padx=20, pady=20)
        
        # Styles
        label_font = ("Helvetica", 10)
        
        # Source File Section
        tk.Label(root, text="Source Markdown File (.md):", font=label_font).pack(anchor="w")
        
        self.src_frame = tk.Frame(root)
        self.src_frame.pack(fill="x", pady=(0, 15))
        
        self.src_entry = tk.Entry(self.src_frame, width=60)
        self.src_entry.pack(side="left", expand=True, fill="x", padx=(0, 10))
        
        self.src_btn = tk.Button(self.src_frame, text="Browse", command=self.browse_src, width=10)
        self.src_btn.pack(side="right")
        
        # Destination File Section
        tk.Label(root, text="Destination Document (.docx):", font=label_font).pack(anchor="w")
        
        self.dest_frame = tk.Frame(root)
        self.dest_frame.pack(fill="x", pady=(0, 20))
        
        self.dest_entry = tk.Entry(self.dest_frame, width=60)
        self.dest_entry.pack(side="left", expand=True, fill="x", padx=(0, 10))
        
        self.dest_btn = tk.Button(self.dest_frame, text="Browse", command=self.browse_dest, width=10)
        self.dest_btn.pack(side="right")
        
        # Convert Button
        self.convert_btn = tk.Button(root, text="格式转化 (Convert)", bg="#4CAF50", fg="white", 
                                     font=("Helvetica", 11, "bold"), command=self.convert,
                                     width=20, height=2)
        self.convert_btn.pack()
        
        # Provide default file path as requested
        default_md = r"D:\recording\AI_tool\tools_repository\mdTodocs\ip_application_bayesian_autonomous_debugging_integrated.md"
        if os.path.exists(default_md):
            self.src_entry.insert(0, default_md)
            default_docx = default_md.rsplit('.', 1)[0] + ".docx"
            self.dest_entry.insert(0, default_docx)

    def browse_src(self):
        filename = filedialog.askopenfilename(
            title="Select Markdown File",
            filetypes=(("Markdown files", "*.md"), ("All files", "*.*"))
        )
        if filename:
            self.src_entry.delete(0, tk.END)
            self.src_entry.insert(0, os.path.normpath(filename))
            
            # Automatically suggest destination file path
            dest_filename = filename.rsplit('.', 1)[0] + ".docx"
            self.dest_entry.delete(0, tk.END)
            self.dest_entry.insert(0, os.path.normpath(dest_filename))

    def browse_dest(self):
        filename = filedialog.asksaveasfilename(
            title="Save as DOCX",
            defaultextension=".docx",
            filetypes=(("Word Document", "*.docx"), ("All files", "*.*"))
        )
        if filename:
            self.dest_entry.delete(0, tk.END)
            self.dest_entry.insert(0, os.path.normpath(filename))

    def convert(self):
        src = self.src_entry.get().strip()
        dest = self.dest_entry.get().strip()
        
        if not src or not dest:
            messagebox.showwarning("Input Error", "Please provide both source and destination paths.")
            return
            
        if not os.path.exists(src):
            messagebox.showerror("File Error", "Source Markdown file does not exist.")
            return
            
        try:
            self.convert_btn.config(text="Converting...", state="disabled")
            self.root.update()
            
            convert_md_to_docx(src, dest)
            
            messagebox.showinfo("Success", f"Successfully converted to:\n{dest}")
        except Exception as e:
            messagebox.showerror("Conversion Error", f"An error occurred during conversion:\n{str(e)}")
        finally:
            self.convert_btn.config(text="格式转化 (Convert)", state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    app = MdToDocxApp(root)
    root.mainloop()
