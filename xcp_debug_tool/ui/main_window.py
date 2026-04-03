from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTabWidget, QScrollArea
)
from PyQt5.QtCore import Qt

from ui.file_loader_panel import FileLoaderPanel
from ui.variable_query_panel import VariableQueryPanel
from ui.pointer_query_panel import PointerQueryPanel
from ui.control_panel import ControlPanel
from ui.result_display_panel import ResultDisplayPanel
from ui.log_panel import LogPanel

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XCP 在线调试工具 v1.0")
        self.resize(1100, 720)
        
        self._init_ui()
        
    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        # 1. 顶部：文件加载区
        self.file_loader = FileLoaderPanel()
        main_layout.addWidget(self.file_loader)
        
        # 2. 中间：分为左右两个主要区域使用 QSplitter 方便调节大小
        splitter_mid = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter_mid, stretch=1)
        
        # 2.1 左侧区域：查询区与控制区 (放入滚动区域)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(5, 5, 5, 5) # 减小边距
        left_layout.setSpacing(10)
        
        # 使用选项卡切换 变量查询 和 指针查询，节省垂直空间
        self.query_tabs = QTabWidget()
        self.variable_query = VariableQueryPanel()
        self.pointer_query = PointerQueryPanel()
        
        self.query_tabs.addTab(self.variable_query, "变量查询")
        self.query_tabs.addTab(self.pointer_query, "指针查询")
        
        self.control_panel = ControlPanel()
        
        left_layout.addWidget(self.query_tabs)
        left_layout.addWidget(self.control_panel)
        left_layout.addStretch()
        
        scroll_area.setWidget(left_widget)
        splitter_mid.addWidget(scroll_area)
        
        # 2.2 右侧区域：结果展示区
        self.result_display = ResultDisplayPanel()
        splitter_mid.addWidget(self.result_display)
        
        # 宽度的初始比例 (例如左边 35%，右边 65%)
        splitter_mid.setSizes([400, 800])
        
        # 3. 底部：日志输出区
        self.log_panel = LogPanel()
        main_layout.addWidget(self.log_panel)
