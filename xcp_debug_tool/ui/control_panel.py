from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QComboBox

class ControlPanel(QGroupBox):
    def __init__(self):
        super().__init__("4. 控制与策略区")
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        self.setLayout(layout)
        
        # 查询按钮
        btn_layout = QHBoxLayout()
        self.btn_single_query = QPushButton("单次查询")
        self.btn_timer_query = QPushButton("开始定时查询")
        btn_layout.addWidget(self.btn_single_query)
        btn_layout.addWidget(self.btn_timer_query)
        layout.addLayout(btn_layout)
        
        # 轮询参数
        params_layout = QHBoxLayout()
        params_layout.addWidget(QLabel("轮询周期:"))
        self.combo_period = QComboBox()
        self.combo_period.addItems(["20 ms", "50 ms", "100 ms", "500 ms", "1000 ms"])
        params_layout.addWidget(self.combo_period)
        layout.addLayout(params_layout)
        
        # 条件触发配置
        cond_layout = QVBoxLayout()
        cond_layout.addWidget(QLabel("条件判断逻辑 (例如: var1==1 && var2>5):"))
        self.edit_condition = QLineEdit()
        self.edit_condition.setPlaceholderText("留空表示不启用条件触发...")
        cond_layout.addWidget(self.edit_condition)
        
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("满足条件后延续查询次数:"))
        self.edit_delay_cycles = QLineEdit("0")
        delay_layout.addWidget(self.edit_delay_cycles)
        
        cond_layout.addLayout(delay_layout)
        layout.addLayout(cond_layout)
