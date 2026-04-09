"""
CAN Log Auto-Analyzer — 入口文件
MVC 架构：
  - Model:      core/matrix_parser.py, core/blf_parser.py
  - View:       ui/main_window.py
  - Controller: core/app_controller.py
"""
import sys
import traceback

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from ui.main_window import MainWindow
from core.app_controller import AppController
from logger.log_manager import logger


def exception_hook(exc_type, exc_value, exc_traceback):
    """全局异常捕获，防止程序直接闪退并将错误写入日志"""
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(f"Uncaught exception:\n{error_msg}", file=sys.stderr)
    logger.error(f"Uncaught exception:\n{error_msg}")


def main():
    sys.excepthook = exception_hook

    # 启用高 DPI 适配
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow()
    controller = AppController(window)  # noqa: F841 — Controller 持有引用

    window.show()
    logger.info("CAN Log Auto-Analyzer 启动完成")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
