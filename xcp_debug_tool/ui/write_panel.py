from PyQt5.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QFormLayout, 
    QLineEdit, QPushButton, QLabel, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal

class WritePanel(QGroupBox):
    """
    XCP 变量写入面板
    支持通过变量名 (DWARF) 或直接物理地址进行内存修改。
    """
    resolve_var_signal = pyqtSignal(str)  # 发送变量名给 Controller 解析
    execute_write_signal = pyqtSignal(dict) # 发送写入请求给 Controller

    def __init__(self):
        super().__init__("变量写入")
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        form = QFormLayout()
        
        # 1. 变量名输入与解析
        self.edit_var_name = QLineEdit()
        self.edit_var_name.setPlaceholderText("例如: Lin_u8LinDrvStatus 或 Van.member1")
        self.btn_resolve = QPushButton("从 DWARF 解析")
        
        var_layout = QHBoxLayout()
        var_layout.addWidget(self.edit_var_name)
        var_layout.addWidget(self.btn_resolve)
        form.addRow("变量名称:", var_layout)

        # 2. 地址输入 (Hex)
        self.edit_address = QLineEdit()
        self.edit_address.setPlaceholderText("解析会自动填充，也可手动输入 0x...")
        form.addRow("内存地址:", self.edit_address)

        # 3. 写入大小 (Bytes)
        self.edit_size = QLineEdit()
        self.edit_size.setPlaceholderText("解析会自动填充")
        form.addRow("写入长度:", self.edit_size)

        # 4. 写入值 (Hex String)
        self.edit_value = QLineEdit()
        self.edit_value.setPlaceholderText("Hex 格式，空格分隔，如: 01 02 03 04")
        form.addRow("写入数值:", self.edit_value)

        layout.addLayout(form)

        # 5. 操作按钮
        self.btn_write = QPushButton("执行写入 (DOWNLOAD)")
        self.btn_write.setStyleSheet("background-color: #4A148C; color: white; font-weight: bold; height: 30px;")
        layout.addWidget(self.btn_write)

        # 6. 状态显示
        self.lbl_status = QLabel("状态: 等待操作")
        self.lbl_status.setStyleSheet("color: #888;")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        # 绑定内部信号
        self.btn_resolve.clicked.connect(self._on_resolve_clicked)
        self.btn_write.clicked.connect(self._on_write_clicked)

    def _on_resolve_clicked(self):
        name = self.edit_var_name.text().strip()
        if not name:
            QMessageBox.warning(self, "警告", "请输入变量名称再进行解析。")
            return
        self.resolve_var_signal.emit(name)

    def _on_write_clicked(self):
        # 验证输入
        addr_str = self.edit_address.text().strip()
        size_str = self.edit_size.text().strip()
        val_str = self.edit_value.text().strip()

        if not addr_str or not size_str or not val_str:
            QMessageBox.warning(self, "警告", "地址、长度和数值均不能为空。")
            return

        # 简单预检：尝试解析地址和数据
        try:
            addr = int(addr_str, 16) if addr_str.lower().startswith('0x') else int(addr_str, 10)
            size = int(size_str)
            # 解析空格分隔的 Hex
            data_bytes = bytes.fromhex(val_str.replace(" ", ""))
            
            if len(data_bytes) != size:
                QMessageBox.warning(self, "警告", f"输入数据长度 ({len(data_bytes)}) 与指定长度 ({size}) 不符！")
                return

            # 根据用户要求进行大小端转化 (输入通常为直观的高位在前，发送需转为小端)
            # 例如输入 00 01 02 03 -> 写入 03 02 01 00
            data_to_send = data_bytes[::-1]

            # 弹出确认框
            reply = QMessageBox.question(
                self, "确认写入",
                f"确定要向地址 {hex(addr)} 写入 {size} 字节数据吗？\n"
                f"原始输入: {data_bytes.hex().upper()}\n"
                f"调整后发送(小端): {data_to_send.hex().upper()}",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.execute_write_signal.emit({
                    'addr': addr,
                    'size': size,
                    'data': data_to_send
                })
        except Exception as e:
            QMessageBox.critical(self, "错误", f"输入格式非法: {e}")

    def update_resolution_result(self, success, info=None):
        """由 Controller 调用以更新解析出的地址和大小"""
        if success and info:
            self.edit_address.setText(hex(info['address']))
            self.edit_size.setText(str(info['size']))
            self.lbl_status.setText(f"状态: 变量解析成功 ({info['type_name']})")
            self.lbl_status.setStyleSheet("color: green;")
        else:
            self.lbl_status.setText("状态: 变量解析失败，请检查名称。")
            self.lbl_status.setStyleSheet("color: red;")

    def set_write_status(self, success, msg):
        """更新写入结果"""
        self.lbl_status.setText(f"状态: {msg}")
        if success:
            self.lbl_status.setStyleSheet("color: green;")
        else:
            self.lbl_status.setStyleSheet("color: red;")
