import time
from logger.log_manager import logger
from elf_parser.elf_loader import ELFLoader
from elf_parser.dwarf_analyzer import DwarfAnalyzer
from PyQt5.QtWidgets import QMessageBox, QTableWidgetItem, QFileDialog

# 引入 Phase 2 的通信模块
from canoe.canoe_manager import CANoeManager
from canoe.canfd_transport import CanFdTransport
from xcp.xcp_session import XcpSession
from xcp.data_converter import DataConverter
from core.query_scheduler import QueryScheduler

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

        # 定时查询调度器
        self.scheduler = QueryScheduler(self.xcp_session)
        self.scheduler.task_finished_signal.connect(self.on_scheduled_data_received)
        self.scheduler.finished.connect(self._on_scheduler_finished)
        self.scheduler.recovery_required_signal.connect(self.on_recovery_required)

        # 条件触发状态
        self.condition_expr = ""
        self.delay_cycles = 0
        self.met_count = 0
        self.is_cond_satisfied = False

        self._bind_events()

    def _bind_events(self):
        # 绑定日志输出
        logger.addHandler(self._create_ui_log_handler())

        # 文件加载信号
        self.view.file_loader.file_loaded_signal.connect(self.on_file_loaded)
        
        # 控制区单次查询信号
        self.view.control_panel.btn_single_query.clicked.connect(self.on_single_query)
        self.view.control_panel.btn_timer_query.clicked.connect(self.on_timer_query)
        
        # 日志区信号
        self.view.log_panel.btn_export.clicked.connect(self.on_export_log)

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
        """确保 XCP 通道已连接，具备自动恢复能力"""
        # 1. 检查 CANoe COM 连接
        if self.canoe_manager.app is None:
            logger.info("CANoe COM 未连接，尝试连接...")
            if not self.canoe_manager.connect():
                return False

        # 2. 检查 Measurement 运行状态
        if not self.canoe_manager.is_running():
            logger.info("CANoe Measurement 未运行，正在尝试启动并绑定 CAPL...")
            success = self.canoe_manager.start_measurement_and_bindCAPL(
                self.REQUIRED_CAPL_FUNCTIONS
            )
            if not success:
                return False
        elif not self.canoe_manager._init_complete:
            # 如果运行中但没初始化（可能手动启动的），尝试重新绑定
            logger.info("CANoe 运行中但 CAPL 未绑定，重启 Measurement 以绑定...")
            self.canoe_manager.stop_measurement()
            if not self.canoe_manager.start_measurement_and_bindCAPL(self.REQUIRED_CAPL_FUNCTIONS):
                return False

        # 3. XCP 协议层连接验证
        if not self.xcp_session.is_connected:
            logger.info("正在建立 XCP CONNECT...")
            self.xcp_session.connect()
             
        return self.xcp_session.is_connected

    def on_single_query(self):
        """单次查询逻辑触发"""
        if not self.dwarf_analyzer:
             QMessageBox.warning(self.view, "提示", "请先加载有效的 ELF 文件！")
             return

        # 确保 CANoe 通讯底层 Ready
        is_connected = self._ensure_xcp_connected()

        # 拿到用户想要查询的变量名/指针
        var_names = self.view.variable_query.get_query_variables()
        pointers = self.view.pointer_query.get_query_pointers()
        
        # 单次查询清空旧显示（或可以增量，视需求而定，目前为全刷）
        self.view.result_display.clear_results()

        # 1. 解析变量名列表
        for var in var_names:
            try:
                result = self.dwarf_analyzer.find_variable(var)
                if result:
                    raw_data = self.xcp_session.read_memory(result['address'], result['size']) if is_connected else None
                    if raw_data:
                        parsed_val, raw_hex = DataConverter.parse_raw_value(raw_data, result['size'], result['type_info'])
                    else:
                        parsed_val, raw_hex = "读取失败(重试耗尽)", "N/A"
                    
                    self.view.result_display.update_or_add_row(
                        result['query_name'], result['address'], result['type_name'], 
                        result['size'], raw_hex, parsed_val
                    )
                else:
                    logger.error(f"> 未找到变量 {var}")
            except Exception as e:
                logger.error(f"> 查询变量 {var} 时发生异常: {e}")

        # 2. 解析原始指针
        for addr_str, size_str in pointers:
            try:
                addr = int(addr_str, 16)
                size = int(size_str)
                raw_data = self.xcp_session.read_memory(addr, size) if is_connected else None
                if raw_data:
                    parsed_val, raw_hex = DataConverter.parse_raw_value(raw_data, size, None)
                    # 指针查询要求直接显示 16 进制，而不是 10 进制
                    parsed_val = raw_hex
                else:
                    parsed_val, raw_hex = "读取失败(重试耗尽)", "N/A"
                
                self.view.result_display.update_or_add_row(
                    f"*({addr_str})", addr, "Raw Pointer", size, raw_hex, parsed_val
                )
            except Exception as e:
                logger.error(f"> 指针 {addr_str} 查询异常: {e}")

    def on_timer_query(self):
        """定时查询开关"""
        if self.scheduler.isRunning():
            self.scheduler.stop()
            # UI 重置移至 _on_scheduler_finished 处理
            logger.info("[AppController] 正在停止定时查询...")
            logger.info("[AppController] 定时查询已停止。")
        else:
            if not self.dwarf_analyzer:
                QMessageBox.warning(self.view, "提示", "请先加载有效的 ELF 文件！")
                return

            # 准备待查询列表
            items = []
            # 变量
            var_names = self.view.variable_query.get_query_variables()
            for var in var_names:
                res = self.dwarf_analyzer.find_variable(var)
                if res:
                    items.append({
                        'name': res['query_name'], 
                        'addr': res['address'], 
                        'size': res['size'], 
                        'type_info': res['type_info'],
                        'type_name': res['type_name']
                    })
            # 指针
            pointers = self.view.pointer_query.get_query_pointers()
            for addr_str, size_str in pointers:
                try:
                    items.append({
                        'name': f"*({addr_str})", 
                        'addr': int(addr_str, 16), 
                        'size': int(size_str),
                        'type_info': None,
                        'type_name': 'Raw Pointer'
                    })
                except: pass

            if not items:
                QMessageBox.warning(self.view, "提示", "查询列表为空，请先添加变量或指针。")
                return

            # 配置条件触发
            self.condition_expr = self.view.control_panel.edit_condition.text().strip()
            try:
                self.delay_cycles = int(self.view.control_panel.edit_delay_cycles.text())
            except:
                self.delay_cycles = 0
            self.met_count = 0
            self.is_cond_satisfied = False

            # 配置并启动 (采用自适应模式，全速轮询)
            self.scheduler.set_interval(0)
            self.scheduler.set_query_items(items)
            
            # 确保连接并编组 COM 对象
            if self._ensure_xcp_connected():
                import pythoncom
                try:
                    # 编组 Application 和 CAPL_Function，传递给子线程
                    app_stream = pythoncom.CoMarshalInterThreadInterfaceInStream(
                        pythoncom.IID_IDispatch, self.canoe_manager.app
                    )
                    func_stream = pythoncom.CoMarshalInterThreadInterfaceInStream(
                        pythoncom.IID_IDispatch, self.canoe_manager.get_capl_function("XCP_SendCmd")
                    )
                    self.scheduler.set_com_streams((app_stream, func_stream))
                except Exception as e:
                    logger.error(f"[AppController] COM 编组失败: {e}")
                    return

                self.scheduler.start()
                self.view.control_panel.btn_timer_query.setText("停止定时查询")
                self.view.control_panel.btn_single_query.setEnabled(False)
                logger.info(f"[AppController] 定时查询启动，频率: {interval_str}ms")

    def _on_scheduler_finished(self):
        """调度器线程结束（正常停止或异常退出）时的 UI 恢复机制"""
        # 如果不是在执行 Level 3 恢复，则恢复 UI 按钮状态
        if not getattr(self, '_is_recovering', False):
            self.view.control_panel.btn_timer_query.setText("开始定时查询")
            self.view.control_panel.btn_single_query.setEnabled(True)
            logger.info("[AppController] 定时查询已彻底停止，UI 状态已重置。")

    def on_recovery_required(self):
        """Level 3 恢复：系统级重置 (CANoe Restart + Reconnect)"""
        logger.warning("[AppController] 收到 Level 3 恢复请求，正在执行系统级重置...")
        
        self._is_recovering = True
        try:
            # 1. 停止当前调度 (直接停止线程)
            self.scheduler.stop()
            self.scheduler.wait(2000)
            
            # 2. 停止 CANoe Measurement
            self.canoe_manager.stop_measurement()
            time.sleep(1.0)
            
            # 3. 重新执行标准连接序列 (Start -> Bind -> Connect)
            success = self._ensure_xcp_connected()
            if success:
                logger.info("[AppController] Level 3 系统重置成功，正在恢复调度...")
                # 重新编组并启动
                self.on_timer_query() # 重新点击开始定时查询逻辑
            else:
                logger.error("[AppController] Level 3 系统重置最终失败。")
                QMessageBox.critical(self.view, "通讯中断", "自动化自愈尝试失败！\n请检查硬件连接、CAN 通路或 ECU 状态。")
        finally:
            self._is_recovering = False


    def on_export_log(self):
        """将当前日志框内容导出到文件"""
        content = self.view.log_panel.text_edit.toPlainText()
        if not content.strip():
            QMessageBox.information(self.view, "提示", "日志内容为空，无需导出。")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self.view, "导出系统日志", "", "Log Files (*.log);;Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.info(f"日志已成功导出至: {file_path}")
                QMessageBox.information(self.view, "成功", f"日志已保存至:\n{file_path}")
            except Exception as e:
                logger.error(f"导出日志失败: {e}")
                QMessageBox.warning(self.view, "错误", f"保存文件失败: {e}")


    def on_scheduled_data_received(self, results, elapsed_ms):
        """收到调度器返回的数据集合，更新 UI 报表"""
        # 更新实际耗时显示
        self.view.control_panel.lbl_actual_cycle.setText(f"实际采样耗时: {elapsed_ms:.1f} ms")
        self.view.control_panel.lbl_actual_cycle.setStyleSheet("color: blue; font-weight: bold; font-size: 11px;")

        eval_context = {}
        for res in results:
            if res['success']:
                # 解析
                parsed_val, raw_hex = DataConverter.parse_raw_value(
                    res['raw_data'], res['size'], res['type_info']
                )
                
                # 寻找类型描述名用于显示
                type_name = res.get('type_name', 'N/A')
                
                # 特殊处理：如果是指针查询（没有 type_info 或者是 Raw Pointer），解析值直接显示 Hex
                if res.get('type_info') is None or type_name == "Raw Pointer":
                    parsed_val = raw_hex
                
                self.view.result_display.update_or_add_row(
                    res['name'], res['addr'], type_name, res['size'], raw_hex, parsed_val
                )
                
                # 记录到条件评估上下文（仅限成功读取的项）
                # 注意：DataConverter.parse_raw_value 返回的是具体 Python 类型(int/float/dict/list)
                if self.condition_expr:
                    parsed_obj, _ = DataConverter.parse_raw_value(res['raw_data'], res['size'], res['type_info'])
                    eval_context[res['name']] = parsed_obj
            else:
                self.view.result_display.update_or_add_row(
                    res.get('name', 'Err'), res.get('addr', 0), "N/A", 0, "TIMEOUT", "ERR"
                )
        
        # self.view.result_display.table.setUpdatesEnabled(True)

        # 条件触发判定
        if self.condition_expr and not self.is_cond_satisfied:
            try:
                # 使用 eval 进行布尔运算，eval_context 包含变量名到值的映射
                # 安全起见，限制 globals
                if eval(self.condition_expr, {"__builtins__": None}, eval_context):
                    self.is_cond_satisfied = True
                    logger.info(f"[AppController] 条件满足: {self.condition_expr}")
            except Exception as e:
                # 可能是由于变量名还没搜集齐，暂不报错，继续下一轮
                pass

        # 延时停止逻辑
        if self.is_cond_satisfied:
            if self.met_count >= self.delay_cycles:
                logger.info(f"[AppController] 满足条件并达到延时次数 ({self.delay_cycles})，停止查询。")
                self.scheduler.stop()
            else:
                self.met_count += 1
                logger.info(f"[AppController] 条件已满足，延时计数: {self.met_count}/{self.delay_cycles}")

