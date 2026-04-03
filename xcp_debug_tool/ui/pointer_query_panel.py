from PyQt5.QtWidgets import QGroupBox, QGridLayout, QLabel, QLineEdit

class PointerQueryPanel(QGroupBox):
    def __init__(self):
        super().__init__("3. 指针直接查询区")
        self.pointer_inputs = []
        self._init_ui()
        
    def _init_ui(self):
        layout = QGridLayout()
        self.setLayout(layout)
        
        # 提供 3 组地址查询
        layout.addWidget(QLabel("物理地址 (Hex):"), 0, 1)
        layout.addWidget(QLabel("大小 (Bytes):"), 0, 2)
        
        for i in range(3):
            lbl = QLabel(f"指针 {i+1}:")
            addr_edit = QLineEdit()
            addr_edit.setPlaceholderText("例如: 0x80004000")
            size_edit = QLineEdit()
            size_edit.setPlaceholderText("字节数")
            
            layout.addWidget(lbl, i+1, 0)
            layout.addWidget(addr_edit, i+1, 1)
            layout.addWidget(size_edit, i+1, 2)
            
            self.pointer_inputs.append((addr_edit, size_edit))
            
    def get_query_pointers(self):
        """返回填入的有效指针数组 (addr, size)"""
        results = []
        for addr_edit, size_edit in self.pointer_inputs:
            addr = addr_edit.text().strip()
            size = size_edit.text().strip()
            if addr and size:
                results.append((addr, size))
        return results
