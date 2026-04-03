from PyQt5.QtWidgets import QGroupBox, QGridLayout, QLabel, QLineEdit, QComboBox

class VariableQueryPanel(QGroupBox):
    def __init__(self):
        super().__init__("2. 变量查询区 (支持基本类型与结构体)")
        self.query_inputs = [] # 保存所有的输入框引用
        self._init_ui()
        
    def _init_ui(self):
        layout = QGridLayout()
        self.setLayout(layout)
        
        # 减少行数到 5 行，或者根据需要调整
        for i in range(8):
            lbl = QLabel(f"变量 {i+1}:")
            edit = QLineEdit()
            edit.setPlaceholderText("例如: my_struct.field1")
            
            layout.addWidget(lbl, i, 0)
            layout.addWidget(edit, i, 1)
            
            self.query_inputs.append(edit)
            
    def get_query_variables(self):
        """返回所有填入的变量名"""
        return [edit.text().strip() for edit in self.query_inputs if edit.text().strip()]
