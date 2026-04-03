import sys
from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow
from core.app_controller import AppController
import traceback
from logger.log_manager import logger

def exception_hook(exc_type, exc_value, exc_traceback):
    """全局异常捕获，防止程序直接闪退并将错误写入日志"""
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(f"Uncaught exception:\n{error_msg}", file=sys.stderr)
    logger.error(f"Uncaught exception:\n{error_msg}")

def main():
    sys.excepthook = exception_hook
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = MainWindow()
    # 绑定控制器
    controller = AppController(window)
    
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
