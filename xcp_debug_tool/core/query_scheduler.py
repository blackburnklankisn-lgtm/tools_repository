import time
from PyQt5.QtCore import QThread, pyqtSignal
from logger.log_manager import logger

class QueryScheduler(QThread):
    """
    后台调度器，负责定期触发 XCP 读取请求。
    """
    # 信号：任务完成，传回结果列表和当次耗时(ms)
    task_finished_signal = pyqtSignal(list, float)
    # 信号：需要系统级恢复 (Level 3)
    recovery_required_signal = pyqtSignal()
    
    def __init__(self, xcp_session):
        super().__init__()
        self.xcp_session = xcp_session
        self.interval_ms = 500  # 默认 500ms
        self.is_running = False
        
        # 待查询的变量列表: [{'name': '...', 'addr': 0x..., 'size': ..., 'type_info': ...}, ...]
        self.query_items = []

    def set_interval(self, ms):
        self.interval_ms = max(10, ms) # 最小 10ms

    def set_query_items(self, items):
        """设置需要轮询的项"""
        self.query_items = items

    def set_com_streams(self, streams):
        """接收来自主线程编组的 COM streams"""
        self.app_stream, self.func_stream = streams

    def stop(self):
        self.is_running = False

    def run(self):
        import pythoncom
        import win32com.client
        from canoe.canoe_manager import CANoeManager
        from canoe.canfd_transport import CanFdTransport
        from xcp.xcp_session import XcpSession

        # 初始化线程的 COM 环境
        pythoncom.CoInitialize()
        
        self.is_running = True
        logger.info(f"[QueryScheduler] 调度器启动，间隔: {self.interval_ms}ms")
        
        # 解组 (Unmarshal) 主线程传过来的 COM objects
        try:
            app_disp = pythoncom.CoGetInterfaceAndReleaseStream(self.app_stream, pythoncom.IID_IDispatch)
            self.app_stream = None
            local_app = win32com.client.Dispatch(app_disp)
            
            func_disp = pythoncom.CoGetInterfaceAndReleaseStream(self.func_stream, pythoncom.IID_IDispatch)
            self.func_stream = None
            local_func = win32com.client.Dispatch(func_disp)
            
            local_canoe = CANoeManager()
            local_canoe.app = local_app
            local_canoe.measurement = local_app.Measurement
            local_canoe._capl_functions["XCP_SendCmd"] = local_func
            local_canoe._init_complete = True
        except Exception as e:
            logger.error(f"[QueryScheduler] 线程 COM 对象解组失败！: {e}")
            self.is_running = False
            pythoncom.CoUninitialize()
            return

        local_transport = CanFdTransport(local_canoe)
        local_xcp = XcpSession(local_transport)
        
        while self.is_running:
            start_time = time.time()
            results = []
            
            # --- 自动化逻辑：Level 2 & 3 恢复检测 ---
            # 如果本地连接标记为 False，或者主线程已经断开，则尝试 Level 2 恢复
            if not local_xcp.is_connected or not self.xcp_session.is_connected:
                # 如果主线程和本地都断了，且当前是轮询状态，尝试 Level 2
                logger.warning("[QueryScheduler] 检测到 XCP 连接断足或未同步，尝试 Level 2 恢复...")
                if local_xcp.connect():
                    logger.info("[QueryScheduler] Level 2 恢复成功。")
                    # 同步到主线程 session 对象 (注意：这只是个 flag)
                    self.xcp_session.is_connected = True
                else:
                    logger.error("[QueryScheduler] Level 2 恢复失败，请求 Level 3 系统级重置。")
                    self.recovery_required_signal.emit()
                    time.sleep(3.0) # 等待主线程 Reset CANoe
                    continue # 跳过本轮

            # --- 正常查询 ---
            for item in self.query_items:
                if not self.is_running: break
                addr, size, name = item['addr'], item['size'], item['name']
                type_info = item.get('type_info')
                type_name = item.get('type_name', 'N/A')
                
                try:
                    raw_data = local_xcp.read_memory(addr, size)
                    if raw_data:
                        results.append({
                            'name': name, 'addr': addr, 'size': size,
                            'type_info': type_info, 'type_name': type_name,
                            'raw_data': raw_data, 'success': True
                        })
                    else:
                        results.append({'name': name, 'addr': addr, 'success': False})
                except Exception as e:
                    logger.error(f"[QueryScheduler] 读取 {name} 异常: {e}")
                    results.append({'name': name, 'addr': addr, 'success': False})
            
            # 统计并上报
            elapsed = (time.time() - start_time) * 1000
            if self.is_running and results:
                failure_count = sum(1 for r in results if not r.get('success', False))
                logger.debug(f"[QueryScheduler] 轮询完成: 成功={len(results)-failure_count}, 失败={failure_count}, 耗时={elapsed:.1f}ms")
                self.task_finished_signal.emit(results, elapsed)
                
                # 如果本轮全员失败，主动切断连接标记以触发下一轮的 Level 2 恢复
                if failure_count > 0 and failure_count == len(self.query_items):
                    logger.error("[QueryScheduler] 本轮全员失败，切断连接状态以触发自愈。")
                    local_xcp.is_connected = False

            sleep_time = max(0, self.interval_ms - elapsed)
            time.sleep(sleep_time / 1000.0)

        # 释放线程 COM 资源
        pythoncom.CoUninitialize()
        logger.info("[QueryScheduler] 调度器已停止。")
