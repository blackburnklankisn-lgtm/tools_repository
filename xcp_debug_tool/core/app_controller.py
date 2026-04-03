from logger.log_manager import logger
from elf_parser.elf_loader import ELFLoader
from elf_parser.dwarf_analyzer import DwarfAnalyzer
from PyQt5.QtWidgets import QMessageBox, QTableWidgetItem

# 引入 Phase 2 的通信模块
from canoe.canoe_manager import CANoeManager
from canoe.canfd_transport import CanFdTransport
from xcp.xcp_session import XcpSession
from xcp.data_converter import DataConverter

class AppController:
    """
    负责将 UI 和底层的解析引擎/通信引擎连接起来，处理界面事件交互。
    """
    def __init__(self, main_window):
        self.view = main_window
        self.elf_loader = ELFLoader()
        self.dwarf_analyzer = None

        # 初始化通信层
        self.canoe_manager = CANoeManager()
        self.transport = CanFdTransport(self.canoe_manager)
        self.xcp_session = XcpSession(self.transport)

        self._bind_events()

    def _bind_events(self):
        # 绑定日志输出
        logger.addHandler(self._create_ui_log_handler())

        # 文件加载信号
        self.view.file_loader.file_loaded_signal.connect(self.on_file_loaded)
        
        # 控制区单次查询信号
        self.view.control_panel.btn_single_query.clicked.connect(self.on_single_query)

    def _create_ui_log_handler(self):
        """创建一个 logging.Handler 用于将日志发送给 UI 的 LogPanel"""
        import logging
        class UILogHandler(logging.Handler):
            def __init__(self, log_panel):
                super().__init__()
                self.log_panel = log_panel

            def emit(self, record):
                msg = self.format(record)
                self.log_panel.append_log(msg, level=record.levelno)
                
        handler = UILogHandler(self.view.log_panel)
        handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        return handler

    def on_file_loaded(self, file_path):
        """当用户选择了 ELF 文件"""
        try:
            logger.info("=================================")
            logger.info(f"开始加载文件: {file_path}")
            
            if self.dwarf_analyzer:
                self.dwarf_analyzer = None
            self.elf_loader.close()
            
            self.elf_loader.load_file(file_path)
            self.dwarf_analyzer = DwarfAnalyzer(self.elf_loader.dwarf_info)
            self.dwarf_analyzer.scan_all_global_variables()
            
            QMessageBox.information(self.view, "成功", "ELF/DWARF 解析环境准备完毕！")

        except Exception as e:
            QMessageBox.critical(self.view, "错误", f"加载或解析 ELF 失败:\n{str(e)}")

    # 需要在 OnInit 中绑定的 CAPL 函数列表 (v4.0)
    # 响应数据通过 System Variables 传输，无需绑定读取函数
    REQUIRED_CAPL_FUNCTIONS = [
        "XCP_SendCmd",
    ]

    def _ensure_xcp_connected(self):
        """确保 XCP 通道已连接，如果没连上就帮连"""
        # 1. 先确保 CANoe COM 连接
        if self.canoe_manager.app is None:
            if not self.canoe_manager.connect():
                logger.error("无法通过 COM 连接 CANoe 环境！")
                return False

        # 2. 确保 Measurement 运行并 CAPL 函数已绑定
        if not self.canoe_manager.is_running() or not self.canoe_manager._init_complete:
            logger.info("正在启动 CANoe 并绑定 CAPL 函数 (OnInit 模式)...")
            success = self.canoe_manager.start_measurement_and_bindCAPL(
                self.REQUIRED_CAPL_FUNCTIONS
            )
            if not success:
                logger.error("CANoe Measurement 启动或 CAPL 函数绑定失败！")
                return False

        # 3. XCP 协议层连接
        if not self.xcp_session.is_connected:
            self.xcp_session.connect()
             
        return self.xcp_session.is_connected

    def on_single_query(self):
        """单次查询逻辑触发"""
        if not self.dwarf_analyzer:
             QMessageBox.warning(self.view, "提示", "请先加载有效的 ELF 文件！")
             return

        # 确保 CANoe 通讯底层 Ready
        is_connected = self._ensure_xcp_connected()

        # 拿到用户想要查询的变量名
        var_names = self.view.variable_query.get_query_variables()
        pointers = self.view.pointer_query.get_query_pointers()
        
        self.view.result_display.clear_results()
        self.view.result_display.table.setRowCount(0)

        row_idx = 0
        
        # 内部解析结果填充表格助手函数
        def add_row(name, addr, t_name, size, raw_hex, parsed_val):
             nonlocal row_idx
             self.view.result_display.table.insertRow(row_idx)
             self.view.result_display.table.setItem(row_idx, 0, QTableWidgetItem(str(name)))
             self.view.result_display.table.setItem(row_idx, 1, QTableWidgetItem(hex(addr) if type(addr) is int else str(addr)))
             self.view.result_display.table.setItem(row_idx, 2, QTableWidgetItem(str(t_name)))
             self.view.result_display.table.setItem(row_idx, 3, QTableWidgetItem(str(size)))
             self.view.result_display.table.setItem(row_idx, 4, QTableWidgetItem(str(raw_hex)))
             self.view.result_display.table.setItem(row_idx, 5, QTableWidgetItem(str(parsed_val)))
             row_idx += 1

        # 解析变量名
        for var in var_names:
            logger.debug(f"> 解析变量: {var}")
            result = self.dwarf_analyzer.find_variable(var)
            if result:
                # 执行实际拉取数据动作
                raw_data = None
                if is_connected:
                    raw_data = self.xcp_session.read_memory(result['address'], result['size'])
                
                if raw_data:
                    parsed_val, raw_hex = DataConverter.parse_raw_value(raw_data, result['size'], result['type_info'])
                else:
                    parsed_val, raw_hex = "未读取/断开", "N/A"
                    
                add_row(result['query_name'], result['address'], result['type_name'], result['size'], raw_hex, parsed_val)
            else:
                 logger.error(f"> 未找到变量 {var} 的地址映射。")

        # 处理直接指针
        for addr_str, size_str in pointers:
            try:
                addr = int(addr_str, 16)
                size = int(size_str)
                raw_data = None
                if is_connected:
                     raw_data = self.xcp_session.read_memory(addr, size)
                     
                if raw_data:
                     # 指针读取时不知道实际类型，回退为 generic 解析
                     parsed_val, raw_hex = DataConverter.parse_raw_value(raw_data, size, None)
                else:
                     parsed_val, raw_hex = "未读取/断开", "N/A"
                     
                add_row(f"*({addr_str})", addr, "Raw Pointer", size, raw_hex, parsed_val)
            except ValueError:
                logger.error(f"> 指针参数非法: {addr_str}, {size_str}")

