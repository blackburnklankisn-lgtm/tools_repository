from PyQt5.QtWidgets import QGroupBox, QHBoxLayout, QPushButton, QLineEdit, QLabel, QFileDialog
from PyQt5.QtCore import pyqtSignal

class FileLoaderPanel(QGroupBox):
    # 定义自定义信号，当加载 ELF 文件后抛出路径
    file_loaded_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__("1. 文件加载区 (ELF/DWARF)")
        self._init_ui()
        
    def _init_ui(self):
        layout = QHBoxLayout()
        self.setLayout(layout)
        
        self.btn_load = QPushButton("加载 ELF 文件")
        self.btn_load.clicked.connect(self._on_load_clicked)
        
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("请选择带有调试信息的 .elf 文件（包含 DWARF）")
        
        layout.addWidget(self.btn_load)
        layout.addWidget(self.path_edit)

    def _on_load_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 ELF 文件", "", "ELF Files (*.elf *.out);;All Files (*)")
        if file_path:
            self.path_edit.setText(file_path)
            self.file_loaded_signal.emit(file_path)
