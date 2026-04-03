import logging
from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QTextEdit, QHBoxLayout, QPushButton
from PyQt5.QtGui import QTextCursor, QColor
from PyQt5.QtCore import Qt

class LogPanel(QGroupBox):
    def __init__(self):
        super().__init__("系统日志输出")
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 控制栏
        ctrl_layout = QHBoxLayout()
        self.btn_clear = QPushButton("清空日志")
        self.btn_export = QPushButton("导出日志...")
        ctrl_layout.addWidget(self.btn_clear)
        ctrl_layout.addWidget(self.btn_export)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)
        
        # 富文本输出区
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        # 极客深色风格
        self.text_edit.setStyleSheet("background-color: #1E1E1E; color: #D4D4D4; font-family: Consolas;")
        layout.addWidget(self.text_edit)
        
        self.btn_clear.clicked.connect(self.text_edit.clear)

    def append_log(self, text, level=logging.INFO):
        """支持颜色的日志输出"""
        color = "#D4D4D4" # Default
        if level >= logging.ERROR:
            color = "#F44747" # Red
        elif level == logging.WARNING:
            color = "#D7BA7D" # Yellow
        elif level == logging.DEBUG:
            color = "#808080" # Gray
            
        # 组装 HTML
        html_msg = f'<span style="color: {color};">{text}</span>'
        self.text_edit.append(html_msg)
        
        # 滚动到底部
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.text_edit.setTextCursor(cursor)
