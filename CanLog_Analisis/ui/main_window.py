"""
主窗口 UI 模块 (Main Window)
CAN Log Auto-Analyzer 的主界面。
采用现代化深色主题，包含矩阵上传区、Log 上传区、控制区和输出显示区。
"""
import os

from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QColor, QIcon, QPalette, QTextCharFormat
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTextEdit,
    QFileDialog,
    QFrame,
    QSplitter,
    QGroupBox,
    QSizePolicy,
    QGraphicsDropShadowEffect,
    QProgressBar,
    QStatusBar,
    QApplication,
)

from ui.result_table_widget import ResultTableWidget
from logger.log_manager import logger


# ─────────────────────────────────────────────────────────────
# 样式表 (QSS) — 深色主题
# ─────────────────────────────────────────────────────────────
DARK_THEME_QSS = """
/* ── 全局 ── */
QMainWindow, QWidget {
    background-color: #1a1b2e;
    color: #e0e0e0;
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
}

/* ── GroupBox ── */
QGroupBox {
    background-color: #22243a;
    border: 1px solid #3a3d5c;
    border-radius: 10px;
    margin-top: 14px;
    padding: 18px 14px 14px 14px;
    font-size: 13px;
    font-weight: 600;
    color: #a0b4e0;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 12px;
    background-color: #2c2f4a;
    border-radius: 6px;
    color: #7eb8f7;
}

/* ── 按钮 ── */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 #3a7bd5, stop:1 #5f4bcc);
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 10px 22px;
    font-size: 13px;
    font-weight: 600;
    min-height: 20px;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 #4c8de6, stop:1 #7a5fd6);
}
QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 #2a6bc5, stop:1 #4f3bbc);
}
QPushButton:disabled {
    background: #3a3d5c;
    color: #666;
}

/* ── 分析按钮（绿色主题） ── */
QPushButton#btn_analyze {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 #00b894, stop:1 #0984e3);
    font-size: 15px;
    min-height: 30px;
    padding: 12px 30px;
}
QPushButton#btn_analyze:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 #00d9a5, stop:1 #2299f0);
}
QPushButton#btn_analyze:disabled {
    background: #2a2d45;
    color: #555;
}

/* ── 导出按钮（橙色主题） ── */
QPushButton#btn_export {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 #e17055, stop:1 #d63031);
    font-size: 13px;
}
QPushButton#btn_export:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 #f08070, stop:1 #e64040);
}

/* ── 输出文本框 ── */
QTextEdit#output_area {
    background-color: #12132a;
    color: #c8d6e5;
    border: 1px solid #2a2d45;
    border-radius: 8px;
    padding: 12px;
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 12px;
    selection-background-color: #3a7bd5;
}

/* ── 状态标签 ── */
QLabel#status_label {
    color: #888;
    font-size: 12px;
    padding: 4px 8px;
    border-radius: 4px;
}
QLabel#status_success {
    color: #00b894;
    font-weight: 600;
}
QLabel#status_error {
    color: #e17055;
    font-weight: 600;
}
QLabel#status_loading {
    color: #fdcb6e;
    font-weight: 600;
}

/* ── 进度条 ── */
QProgressBar {
    background-color: #2a2d45;
    border: none;
    border-radius: 4px;
    min-height: 6px;
    max-height: 6px;
    text-align: center;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #3a7bd5, stop:1 #00b894);
    border-radius: 4px;
}

/* ── StatusBar ── */
QStatusBar {
    background-color: #15162a;
    color: #666;
    font-size: 11px;
    border-top: 1px solid #2a2d45;
}

/* ── Splitter ── */
QSplitter::handle {
    background: #3a3d5c;
    width: 2px;
    margin: 4px;
    border-radius: 1px;
}

/* ── 标题 Label ── */
QLabel#title_label {
    font-size: 22px;
    font-weight: 700;
    color: #7eb8f7;
    padding: 2px;
}
QLabel#subtitle_label {
    font-size: 12px;
    color: #666;
    padding: 0px 2px;
}

/* ── 文件信息 ── */
QLabel#file_info {
    color: #aab0c6;
    font-size: 11px;
    padding: 2px 6px;
    background-color: #1e2038;
    border-radius: 4px;
}
"""


class MainWindow(QMainWindow):
    """CAN Log Auto-Analyzer 主窗口"""

    # 定义 UI → Controller 的信号
    sig_load_matrix = Signal(str)    # 加载矩阵文件路径
    sig_load_blf = Signal(str)       # 加载 BLF 文件路径
    sig_start_analysis = Signal()    # 开始分析
    sig_export_report = Signal()     # 导出报告

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CAN Log Auto-Analyzer  v1.0")
        self.setMinimumSize(1080, 720)
        self.resize(1280, 820)

        self._init_ui()
        self.setStyleSheet(DARK_THEME_QSS)

    # ───────────────────────────────────────────────────────
    #  UI 初始化
    # ───────────────────────────────────────────────────────
    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(18, 14, 18, 10)
        root_layout.setSpacing(10)

        # ── 顶部标题栏 ──
        root_layout.addLayout(self._build_header())

        # ── 主体区域 Splitter（左侧控制面板 | 右侧输出区） ──
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # 左侧面板
        left_panel = self._build_left_panel()
        splitter.addWidget(left_panel)

        # 右侧输出区
        right_panel = self._build_right_panel()
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([320, 960])

        root_layout.addWidget(splitter, 1)

        # ── 底部状态栏 ──
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("就绪  |  等待文件加载...")

    # ── 顶部标题区 ──
    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)

        # 左侧标题
        title_block = QVBoxLayout()
        title_block.setSpacing(2)

        title = QLabel("⚡ CAN Log Auto-Analyzer")
        title.setObjectName("title_label")
        title_block.addWidget(title)

        subtitle = QLabel("通信矩阵校验 · 时序分析 · E2E 保护验证 · 总线健康度评估")
        subtitle.setObjectName("subtitle_label")
        title_block.addWidget(subtitle)

        layout.addLayout(title_block)
        layout.addStretch()

        return layout

    # ── 左侧控制面板 ──
    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(12)

        # 1. 矩阵上传区
        layout.addWidget(self._build_matrix_group())

        # 2. BLF 上传区
        layout.addWidget(self._build_blf_group())

        # 3. 控制区
        layout.addWidget(self._build_control_group())

        layout.addStretch()
        return panel

    # ── 矩阵上传 Group ──
    def _build_matrix_group(self) -> QGroupBox:
        group = QGroupBox("📋 通信矩阵 (Matrix)")

        layout = QVBoxLayout()
        layout.setSpacing(8)

        # 选择文件按钮
        self._btn_matrix = QPushButton("📁  选择 Matrix 文件 (.xlsx)")
        self._btn_matrix.setCursor(Qt.PointingHandCursor)
        self._btn_matrix.clicked.connect(self._on_select_matrix)
        layout.addWidget(self._btn_matrix)

        # 文件信息标签
        self._lbl_matrix_file = QLabel("未选择文件")
        self._lbl_matrix_file.setObjectName("file_info")
        self._lbl_matrix_file.setWordWrap(True)
        layout.addWidget(self._lbl_matrix_file)

        # 状态标签
        self._lbl_matrix_status = QLabel("")
        self._lbl_matrix_status.setObjectName("status_label")
        layout.addWidget(self._lbl_matrix_status)

        group.setLayout(layout)
        return group

    # ── BLF 上传 Group ──
    def _build_blf_group(self) -> QGroupBox:
        group = QGroupBox("📊 CAN Log (BLF)")

        layout = QVBoxLayout()
        layout.setSpacing(8)

        self._btn_blf = QPushButton("📁  选择 BLF 文件 (.blf)")
        self._btn_blf.setCursor(Qt.PointingHandCursor)
        self._btn_blf.clicked.connect(self._on_select_blf)
        layout.addWidget(self._btn_blf)

        self._lbl_blf_file = QLabel("未选择文件")
        self._lbl_blf_file.setObjectName("file_info")
        self._lbl_blf_file.setWordWrap(True)
        layout.addWidget(self._lbl_blf_file)

        self._lbl_blf_status = QLabel("")
        self._lbl_blf_status.setObjectName("status_label")
        layout.addWidget(self._lbl_blf_status)

        group.setLayout(layout)
        return group

    # ── 控制区 Group ──
    def _build_control_group(self) -> QGroupBox:
        group = QGroupBox("🎛️ 分析控制")

        layout = QVBoxLayout()
        layout.setSpacing(10)

        # 开始分析按钮
        self._btn_analyze = QPushButton("🔬  开始分析")
        self._btn_analyze.setObjectName("btn_analyze")
        self._btn_analyze.setCursor(Qt.PointingHandCursor)
        self._btn_analyze.setEnabled(False)
        self._btn_analyze.clicked.connect(self.sig_start_analysis.emit)
        layout.addWidget(self._btn_analyze)

        # 导出报告按钮
        self._btn_export = QPushButton("📤  导出报告")
        self._btn_export.setObjectName("btn_export")
        self._btn_export.setCursor(Qt.PointingHandCursor)
        self._btn_export.setEnabled(False)
        self._btn_export.clicked.connect(self.sig_export_report.emit)
        layout.addWidget(self._btn_export)

        # 进度条
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # 不确定进度
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        group.setLayout(layout)
        return group

    # ── 右侧输出面板（上: 日志, 下: 结果表格） ──
    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(6)

        # 使用垂直 Splitter 分割日志区和结果表格区
        v_splitter = QSplitter(Qt.Vertical)
        v_splitter.setChildrenCollapsible(False)

        # ── 上半部分: 日志输出 ──
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(4)

        header = QHBoxLayout()
        lbl = QLabel("📝 输出日志")
        lbl.setStyleSheet("font-size: 14px; font-weight: 600; color: #a0b4e0;")
        header.addWidget(lbl)
        header.addStretch()

        self._btn_clear = QPushButton("🗑 清空")
        self._btn_clear.setFixedWidth(80)
        self._btn_clear.setCursor(Qt.PointingHandCursor)
        self._btn_clear.clicked.connect(lambda: self._output.clear())
        header.addWidget(self._btn_clear)
        log_layout.addLayout(header)

        self._output = QTextEdit()
        self._output.setObjectName("output_area")
        self._output.setReadOnly(True)
        self._output.setPlaceholderText(
            "加载 Matrix 和 BLF 文件后，点击「开始分析」查看结果…"
        )
        log_layout.addWidget(self._output, 1)
        v_splitter.addWidget(log_widget)

        # ── 下半部分: 分析结果表格 ──
        self._result_table = ResultTableWidget()
        v_splitter.addWidget(self._result_table)

        v_splitter.setStretchFactor(0, 2)  # 日志占 2/5
        v_splitter.setStretchFactor(1, 3)  # 表格占 3/5

        layout.addWidget(v_splitter, 1)

        logger.info("[MainWindow] 右侧面板构建完成 (日志 + 结果表格)")
        return panel

    # ───────────────────────────────────────────────────────
    #  UI 事件处理
    # ───────────────────────────────────────────────────────
    def _on_select_matrix(self):
        """打开文件对话框选择矩阵文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 CAN 通信矩阵文件",
            "",
            "Excel 文件 (*.xlsx *.xls);;所有文件 (*)",
        )
        if file_path:
            self._lbl_matrix_file.setText(os.path.basename(file_path))
            self.sig_load_matrix.emit(file_path)

    def _on_select_blf(self):
        """打开文件对话框选择 BLF 文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 CAN Log 文件",
            "",
            "BLF 文件 (*.blf);;所有文件 (*)",
        )
        if file_path:
            self._lbl_blf_file.setText(os.path.basename(file_path))
            self.sig_load_blf.emit(file_path)

    # ───────────────────────────────────────────────────────
    #  供 Controller 调用的公共接口
    # ───────────────────────────────────────────────────────
    def set_matrix_status(self, text: str, state: str = "info"):
        """设置矩阵解析状态"""
        self._lbl_matrix_status.setText(text)
        style_map = {
            "success": "status_success",
            "error": "status_error",
            "loading": "status_loading",
            "info": "status_label",
        }
        self._lbl_matrix_status.setObjectName(style_map.get(state, "status_label"))
        # 刷新样式
        self._lbl_matrix_status.setStyleSheet(self._lbl_matrix_status.styleSheet())
        self.style().polish(self._lbl_matrix_status)

    def set_blf_status(self, text: str, state: str = "info"):
        """设置 BLF 解析状态"""
        self._lbl_blf_status.setText(text)
        style_map = {
            "success": "status_success",
            "error": "status_error",
            "loading": "status_loading",
            "info": "status_label",
        }
        self._lbl_blf_status.setObjectName(style_map.get(state, "status_label"))
        self._lbl_blf_status.setStyleSheet(self._lbl_blf_status.styleSheet())
        self.style().polish(self._lbl_blf_status)

    def set_analysis_ready(self, ready: bool):
        """设置分析按钮是否可用"""
        self._btn_analyze.setEnabled(ready)

    def set_export_ready(self, ready: bool):
        """设置导出按钮是否可用"""
        self._btn_export.setEnabled(ready)

    def display_analysis_results(self, report):
        """
        将分析报告展示到结果表格区域。

        Args:
            report: AnalysisReport 综合报告
        """
        logger.info("[MainWindow] 调用 ResultTableWidget 展示分析结果")
        self._result_table.display_report(report)

    def append_log(self, text: str, level: str = "info"):
        """
        向输出区域追加日志信息。
        level: 'info' | 'success' | 'warning' | 'error'
        """
        color_map = {
            "info": "#c8d6e5",
            "success": "#00b894",
            "warning": "#fdcb6e",
            "error": "#e17055",
        }
        color = color_map.get(level, "#c8d6e5")
        # 使用 HTML 着色
        html_text = text.replace("\n", "<br>").replace("  ", "&nbsp;&nbsp;")
        self._output.append(
            f'<span style="color:{color};">{html_text}</span>'
        )
        # 自动滚动到底部
        scrollbar = self._output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def show_progress(self, visible: bool):
        """显示/隐藏进度条"""
        self._progress.setVisible(visible)
