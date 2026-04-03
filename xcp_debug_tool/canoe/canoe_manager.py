import win32com.client
import pythoncom
import time
from logger.log_manager import logger


class CANoeManager:
    """
    CANoe COM 接口管理。
    - CAPL 函数通过 OnInit 事件绑定 (CANoe COM 强制要求)
    - 系统变量通过 app.System.Namespaces 读取
    """
    def __init__(self):
        self.app = None
        self.measurement = None
        self._capl_functions = {}
        self._init_complete = False
        self._events_handler = None

    def connect(self):
        """连接到正在运行的 CANoe 实例"""
        logger.info("[CANoeManager] 正在连接 CANoe COM 服务...")
        try:
            self.app = win32com.client.Dispatch("CANoe.Application")
            self.measurement = self.app.Measurement
            logger.info(f"[CANoeManager] CANoe 连接成功。当前版本: {self.app.Version}")
            return True
        except Exception as e:
            logger.error(f"[CANoeManager] 连接 CANoe 失败: {str(e)}")
            return False

    def is_running(self):
        """检查 Measurement 是否正在运行"""
        if self.measurement:
            try:
                return self.measurement.Running
            except:
                return False
        return False

    def stop_measurement(self):
        """停止 Measurement 并等待停止"""
        if self.measurement:
            try:
                if self.measurement.Running:
                    logger.info("[CANoeManager] 正在停止 Measurement...")
                    self.measurement.Stop()
                    t0 = time.time()
                    while self.measurement.Running:
                        if time.time() - t0 > 5.0:
                            logger.warning("[CANoeManager] 等待停止超时!")
                            break
                        time.sleep(0.5)
                    logger.info("[CANoeManager] Measurement 已停止。")
            except Exception as e:
                logger.error(f"[CANoeManager] 停止 Measurement 失败: {e}")
        return True

    def start_measurement_and_bindCAPL(self, capl_func_names, timeout=10.0):
        """启动 Measurement 并在 OnInit 事件中绑定 CAPL 函数。"""
        if self.measurement is None:
            logger.error("[CANoeManager] 无法启动: 未连接至 CANoe")
            return False

        if self.measurement.Running:
            logger.info("[CANoeManager] Measurement 已在运行，先停止再重启...")
            self.measurement.Stop()
            t0 = time.time()
            while self.measurement.Running:
                if time.time() - t0 > 5:
                    break
                pythoncom.PumpWaitingMessages()
                time.sleep(0.2)

        self._capl_functions = {}
        self._init_complete = False

        manager_ref = self

        class MeasurementEvents:
            def OnInit(self):
                if manager_ref._init_complete:
                    return
                logger.info("[CANoeManager] >>> OnInit 事件触发，开始绑定 CAPL 函数...")
                for func_name in capl_func_names:
                    try:
                        func = manager_ref.app.CAPL.GetFunction(func_name)
                        manager_ref._capl_functions[func_name] = func
                        logger.info(f"[CANoeManager]   绑定成功: {func_name}")
                    except Exception as e:
                        logger.error(f"[CANoeManager]   绑定失败: {func_name} -> {e}")
                manager_ref._init_complete = True
                logger.info("[CANoeManager] >>> OnInit CAPL 函数绑定完成。")

        logger.info("[CANoeManager] 正在注册 Measurement 事件处理器...")
        self._events_handler = win32com.client.WithEvents(
            self.measurement, MeasurementEvents
        )

        logger.info("[CANoeManager] 正在启动 Measurement (等待 OnInit 事件)...")
        try:
            self.measurement.Start()
        except Exception as e:
            logger.error(f"[CANoeManager] CANoe 拒绝启动: {e}")
            return False

        start_t = time.time()
        while not self._init_complete:
            pythoncom.PumpWaitingMessages()
            if time.time() - start_t > timeout:
                logger.error("[CANoeManager] 等待 OnInit 超时！")
                return False
            time.sleep(0.1)

        while not self.measurement.Running:
            pythoncom.PumpWaitingMessages()
            if time.time() - start_t > timeout:
                logger.error("[CANoeManager] 等待 Measurement 启动超时！")
                return False
            time.sleep(0.2)

        logger.info("[CANoeManager] Measurement 运行中，CAPL 函数全部就绪。")
        return True

    def stop_measurement(self):
        if self.measurement and self.measurement.Running:
            logger.info("[CANoeManager] 正在停止 Measurement...")
            self.measurement.Stop()

    def get_capl_function(self, capl_func_name):
        """获取已绑定的 CAPL 函数 (仅用于调用，不依赖返回值)"""
        func = self._capl_functions.get(capl_func_name)
        if func is None:
            logger.error(f"[CANoeManager] CAPL 函数 '{capl_func_name}' 未绑定。")
        return func

    def read_sysvar(self, namespace, var_name):
        """
        读取 CANoe 系统变量的值。
        这是从 CAPL 端获取数据到 Python 端的可靠方式。
        """
        try:
            ns = self.app.System.Namespaces(namespace)
            var = ns.Variables(var_name)
            return var.Value
        except Exception as e:
            logger.error(f"[CANoeManager] 读取系统变量 {namespace}::{var_name} 失败: {e}")
            return None

    def write_sysvar(self, namespace, var_name, value):
        """写入 CANoe 系统变量"""
        try:
            ns = self.app.System.Namespaces(namespace)
            var = ns.Variables(var_name)
            var.Value = value
        except Exception as e:
            logger.error(f"[CANoeManager] 写入系统变量 {namespace}::{var_name} 失败: {e}")
