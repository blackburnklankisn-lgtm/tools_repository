from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView

class ResultDisplayPanel(QGroupBox):
    def __init__(self):
        super().__init__("查询结果区")
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "变量名/路径", "物理地址", "类型", "大小(Bytes)", "Raw Data (Hex)", "解析值(十进制/浮点)"
        ])
        
        # 自适应列宽
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch) # 变量名自适应
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        
        layout.addWidget(self.table)
        
    def clear_results(self):
        self.table.setRowCount(0)
