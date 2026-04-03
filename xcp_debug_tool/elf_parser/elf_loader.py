import os
from elftools.elf.elffile import ELFFile
from logger.log_manager import logger

class ELFLoader:
    def __init__(self):
        self.file_path = None
        self.elf_file = None
        self.dwarf_info = None
        self.stream = None

    def load_file(self, path):
        """加载 ELF 文件并校验是否包含 DWARF 信息"""
        if not os.path.exists(path):
            raise FileNotFoundError(f"文件不存在: {path}")

        try:
            # 这里必须保持 stream 打开，因为 DWARF 解析是按需 seek 读取的
            if self.stream:
                self.stream.close()

            self.stream = open(path, 'rb')
            self.elf_file = ELFFile(self.stream)
            
            # 校验是否含有 DWARF 调试信息
            if not self.elf_file.has_dwarf_info():
                self.stream.close()
                self.stream = None
                raise ValueError("该 ELF 文件不包含 DWARF 调试信息，无法用于在线寻址分析。")

            self.dwarf_info = self.elf_file.get_dwarf_info()
            self.file_path = path
            
            logger.info(f"[ELFLoader] 成功加载 ELF 文件: {os.path.basename(path)}")
            logger.info(f"[ELFLoader] 包含 {self.elf_file.num_sections()} 个 Sections")
            
            return True

        except Exception as e:
            if self.stream:
                self.stream.close()
                self.stream = None
            logger.error(f"[ELFLoader] 加载 ELF 失败: {str(e)}")
            raise e

    def close(self):
        if self.stream:
            self.stream.close()
            self.stream = None
            self.elf_file = None
            self.dwarf_info = None

    def __del__(self):
        self.close()
