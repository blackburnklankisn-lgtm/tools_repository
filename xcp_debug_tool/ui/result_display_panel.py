from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView

class ResultDisplayPanel(QGroupBox):
    def __init__(self):
        super().__init__("查询结果区")
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
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
        
        self.table.setWordWrap(True)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        
        layout.addWidget(self.table)
        
        # 缓存行索引，方便快速更新
        # key: (name, addr), value: row_idx
        self._row_map = {}

    def clear_results(self):
        self.table.setRowCount(0)
        self._row_map = {}

    def update_or_add_row(self, name, addr, type_name, size, raw_hex, parsed_val):
        """
        高频更新时调用的核心函数：基于 (name, addr) 查找行，存在则更新，不存在则添加。
        """
        key = (name, addr)
        if key in self._row_map:
            row_idx = self._row_map[key]
        else:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            self._row_map[key] = row_idx
            
            # 只有第一次添加时，填充前 4 列基本静态信息
            name_item = QTableWidgetItem(str(name))
            addr_item = QTableWidgetItem(hex(addr) if isinstance(addr, int) else str(addr))
            type_item = QTableWidgetItem(str(type_name))
            size_item = QTableWidgetItem(str(size))
            
            # 设置顶部对齐，防止内容多时垂直居中导致看不到开始部分
            from PyQt5.QtCore import Qt
            for item in [name_item, addr_item, type_item, size_item]:
                 item.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
                 
            self.table.setItem(row_idx, 0, name_item)
            self.table.setItem(row_idx, 1, addr_item)
            self.table.setItem(row_idx, 2, type_item)
            self.table.setItem(row_idx, 3, size_item)

        # 每次都更新 Raw Data 和 解析值
        raw_item = QTableWidgetItem(str(raw_hex))
        parsed_item = QTableWidgetItem(str(parsed_val))
        
        from PyQt5.QtCore import Qt
        raw_item.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
        parsed_item.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        self.table.setItem(row_idx, 4, raw_item)
        self.table.setItem(row_idx, 5, parsed_item)
        
        # 触发该行高度重新计算（有些版本会自动，有些需要手动触发一下）
        self.table.resizeRowToContents(row_idx)
