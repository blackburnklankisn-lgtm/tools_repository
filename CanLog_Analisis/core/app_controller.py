"""
应用控制器 (App Controller)
MVC 架构中的 Controller 层。
协调 UI 交互与后台业务逻辑（解析、分析）。
"""
import os
import traceback
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

from core.matrix_parser import MatrixParser, MatrixData
from core.blf_parser import BlfParser, BlfData
from core.analysis_engine import AnalysisEngine, AnalysisReport
from logger.log_manager import logger


# ---------------------------------------------------------------------------
# 后台工作线程：矩阵解析
# ---------------------------------------------------------------------------
class MatrixParseWorker(QThread):
    """矩阵文件解析工作线程"""
    finished = Signal(object)   # MatrixData or Exception
    progress = Signal(str)      # 进度消息

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self._file_path = file_path

    def run(self):
        try:
            self.progress.emit("正在解析矩阵文件...")
            parser = MatrixParser()
            data = parser.parse(self._file_path)
            self.finished.emit(data)
        except Exception as e:
            logger.error(f"矩阵解析失败: {traceback.format_exc()}")
            self.finished.emit(e)


# ---------------------------------------------------------------------------
# 后台工作线程：BLF 解析
# ---------------------------------------------------------------------------
class BlfParseWorker(QThread):
    """BLF 文件解析工作线程"""
    finished = Signal(object)   # BlfData or Exception
    progress = Signal(str)

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self._file_path = file_path

    def run(self):
        try:
            self.progress.emit("正在解析 BLF 文件，请稍候...")
            parser = BlfParser()
            data = parser.parse(self._file_path)
            self.finished.emit(data)
        except Exception as e:
            logger.error(f"BLF 解析失败: {traceback.format_exc()}")
            self.finished.emit(e)


# ---------------------------------------------------------------------------
# 后台工作线程：深度分析
# ---------------------------------------------------------------------------
class AnalysisWorker(QThread):
    """深度分析工作线程"""
    finished = Signal(object)   # AnalysisReport or Exception
    progress = Signal(str)

    def __init__(
        self,
        matrix_data: MatrixData,
        blf_data: BlfData,
        timing_threshold_pct: float = 10.0,
        parent=None,
    ):
        super().__init__(parent)
        self._matrix_data = matrix_data
        self._blf_data = blf_data
        self._threshold = timing_threshold_pct

    def run(self):
        try:
            self.progress.emit("正在执行深度分析...")
            logger.info("[AnalysisWorker] 工作线程启动")

            engine = AnalysisEngine(timing_threshold_pct=self._threshold)
            report = engine.run(self._matrix_data, self._blf_data)

            logger.info("[AnalysisWorker] 工作线程完成")
            self.finished.emit(report)
        except Exception as e:
            logger.error(f"[AnalysisWorker] 分析失败: {traceback.format_exc()}")
            self.finished.emit(e)


# ---------------------------------------------------------------------------
# 应用控制器
# ---------------------------------------------------------------------------
class AppController(QObject):
    """
    应用控制器。
    连接 UI 信号和后台解析/分析逻辑。
    """

    def __init__(self, main_window):
        super().__init__()
        self._window = main_window
        self._matrix_data: Optional[MatrixData] = None
        self._blf_data: Optional[BlfData] = None
        self._analysis_report: Optional[AnalysisReport] = None
        self._worker: Optional[QThread] = None

        # 绑定 UI 信号
        self._connect_signals()
        logger.info("[AppController] 初始化完成，信号已绑定")

    def _connect_signals(self):
        """连接主窗口的信号到控制器槽函数"""
        w = self._window
        w.sig_load_matrix.connect(self._on_load_matrix)
        w.sig_load_blf.connect(self._on_load_blf)
        w.sig_start_analysis.connect(self._on_start_analysis)
        w.sig_export_report.connect(self._on_export_report)
        logger.debug("[AppController] 所有 UI 信号已连接")

    # ═══════════════════════════════════════════════════════
    #  Matrix 加载
    # ═══════════════════════════════════════════════════════
    def _on_load_matrix(self, file_path: str):
        """处理矩阵文件加载请求"""
        logger.info(f"[AppController] 收到 Matrix 加载请求: {file_path}")
        self._window.set_matrix_status("解析中...", "loading")
        self._window.append_log(f"📂 加载矩阵文件: {os.path.basename(file_path)}")

        worker = MatrixParseWorker(file_path)
        worker.progress.connect(lambda msg: self._window.append_log(f"  ⏳ {msg}"))
        worker.finished.connect(self._on_matrix_parsed)
        worker.start()
        self._worker = worker

    def _on_matrix_parsed(self, result):
        """矩阵解析完成回调"""
        if isinstance(result, Exception):
            logger.error(f"[AppController] Matrix 解析回调: 失败 - {result}")
            self._window.set_matrix_status("解析失败", "error")
            self._window.append_log(f"  ❌ 矩阵解析失败: {result}", level="error")
            return

        self._matrix_data = result
        logger.info(
            f"[AppController] Matrix 解析回调: 成功, "
            f"报文={result.total_messages}, 信号={result.total_signals}"
        )
        self._window.set_matrix_status("解析成功 ✓", "success")
        self._window.append_log(
            f"  ✅ 矩阵解析成功:\n"
            f"      Channel(s): {result.channels}\n"
            f"      报文总数: {result.total_messages}\n"
            f"      信号总数: {result.total_signals}",
            level="success",
        )
        self._check_ready()

    # ═══════════════════════════════════════════════════════
    #  BLF 加载
    # ═══════════════════════════════════════════════════════
    def _on_load_blf(self, file_path: str):
        """处理 BLF 文件加载请求"""
        logger.info(f"[AppController] 收到 BLF 加载请求: {file_path}")
        self._window.set_blf_status("解析中...", "loading")
        self._window.append_log(f"📂 加载 BLF 文件: {os.path.basename(file_path)}")

        worker = BlfParseWorker(file_path)
        worker.progress.connect(lambda msg: self._window.append_log(f"  ⏳ {msg}"))
        worker.finished.connect(self._on_blf_parsed)
        worker.start()
        self._worker = worker

    def _on_blf_parsed(self, result):
        """BLF 解析完成回调"""
        if isinstance(result, Exception):
            logger.error(f"[AppController] BLF 解析回调: 失败 - {result}")
            self._window.set_blf_status("解析失败", "error")
            self._window.append_log(f"  ❌ BLF 解析失败: {result}", level="error")
            return

        self._blf_data = result
        logger.info(
            f"[AppController] BLF 解析回调: 成功, "
            f"消息={result.total_messages}, 错误帧={result.total_error_frames}"
        )
        self._window.set_blf_status("解析成功 ✓", "success")

        # 打印基础统计信息
        lines = [
            f"  ✅ BLF 解析成功:",
            f"      总消息数: {result.total_messages}",
            f"      Channels: {result.channels}",
            f"      持续时间: {result.duration_seconds:.2f} s",
            f"      错误帧数: {result.total_error_frames}",
        ]
        for ch, bl in result.channel_busload.items():
            lines.append(f"      Channel {ch} Busload: {bl:.2f}%")
        lines.append(f"      报文 ID 数量: {len(result.message_stats)}")
        count = 0
        for arb_id, stats in sorted(result.message_stats.items()):
            if count >= 20:
                lines.append(f"      ... (共 {len(result.message_stats)} 条)")
                break
            lines.append(
                f"      ID 0x{arb_id:03X}: "
                f"Count={stats.count}, "
                f"Avg={stats.avg_cycle_ms:.1f}ms, "
                f"Max={stats.max_cycle_ms:.1f}ms, "
                f"Min={stats.min_cycle_ms:.1f}ms"
            )
            count += 1

        self._window.append_log("\n".join(lines), level="success")
        self._check_ready()

    # ═══════════════════════════════════════════════════════
    #  深度分析（第三步核心）
    # ═══════════════════════════════════════════════════════
    def _on_start_analysis(self):
        """开始深度分析"""
        if not self._matrix_data or not self._blf_data:
            logger.warning("[AppController] 分析请求被拒: 数据未就绪")
            self._window.append_log(
                "⚠️ 请先加载矩阵文件和 BLF 文件！", level="warning"
            )
            return

        logger.info("[AppController] 收到开始分析请求")
        self._window.append_log("🔬 开始深度分析...", level="info")
        self._window.show_progress(True)
        self._window.set_analysis_ready(False)  # 禁用按钮防止重复点击

        worker = AnalysisWorker(
            matrix_data=self._matrix_data,
            blf_data=self._blf_data,
            timing_threshold_pct=10.0,
        )
        worker.progress.connect(lambda msg: self._window.append_log(f"  ⏳ {msg}"))
        worker.finished.connect(self._on_analysis_finished)
        worker.start()
        self._worker = worker

    def _on_analysis_finished(self, result):
        """深度分析完成回调"""
        self._window.show_progress(False)
        self._window.set_analysis_ready(True)  # 恢复按钮

        if isinstance(result, Exception):
            logger.error(f"[AppController] 分析回调: 失败 - {result}")
            self._window.append_log(
                f"  ❌ 分析执行失败: {result}", level="error"
            )
            return

        self._analysis_report = result
        logger.info("[AppController] 分析回调: 成功，开始更新 UI")

        # ── 在日志区输出简要汇总 ──
        self._print_analysis_summary(result)

        # ── 在表格区显示详细结果 ──
        self._window.display_analysis_results(result)

        # ── 启用导出按钮 ──
        self._window.set_export_ready(True)

        logger.info("[AppController] 分析结果已展示到 UI")

    def _print_analysis_summary(self, report: AnalysisReport):
        """在日志区输出分析结果的简要汇总"""
        lines = ["", "═" * 50, "🔬 深度分析完成 — 结果汇总", "═" * 50]

        # 时序分析汇总
        if report.timing_success and report.timing_report:
            tr = report.timing_report
            lines.append(
                f"  ⏱ 时序分析: "
                f"检查 {tr.total_checked} 条, "
                f"异常 {tr.total_anomalies} 条, "
                f"缺失 {len(tr.missing_from_log_ids)} 条"
            )
            if tr.total_anomalies > 0:
                for r in tr.results:
                    if r.is_anomaly:
                        lines.append(
                            f"      ⚠ {r.message_name} (0x{r.arbitration_id:03X}): "
                            f"{r.anomaly_reason}"
                        )
        elif not report.timing_success:
            lines.append(f"  ⏱ 时序分析: ❌ 失败 — {report.timing_error}")

        # DLC 检查汇总
        if report.dlc_success and report.dlc_report:
            dr = report.dlc_report
            if dr.total_mismatches == 0:
                lines.append(f"  📏 DLC 检查: ✅ 全部一致 ({dr.total_checked} 条)")
            else:
                lines.append(
                    f"  📏 DLC 检查: ⚠ {dr.total_mismatches} 条不一致"
                )
                for mm in dr.mismatches:
                    lines.append(
                        f"      ⚠ {mm.message_name} ({mm.id_hex}): "
                        f"Matrix={mm.matrix_dlc}, 实际={mm.actual_dlc}"
                    )
        elif not report.dlc_success:
            lines.append(f"  📏 DLC 检查: ❌ 失败 — {report.dlc_error}")

        # 错误帧监控汇总
        if report.error_frame_success and report.error_frame_report:
            ef = report.error_frame_report
            lines.append(
                f"  ⚡ 错误帧: [{ef.health_level}] "
                f"总数 {ef.total_error_frames}, "
                f"速率 {ef.error_rate_per_sec:.4f}/s"
            )
        elif not report.error_frame_success:
            lines.append(f"  ⚡ 错误帧: ❌ 失败 — {report.error_frame_error}")

        # E2E 校验汇总
        if report.e2e_success and report.e2e_report:
            e2e = report.e2e_report
            if e2e.total_e2e_messages == 0:
                lines.append(f"  🔒 E2E: ℹ️ 无 E2E 保护报文")
            elif e2e.total_counter_errors == 0 and e2e.total_crc_errors == 0:
                lines.append(
                    f"  🔒 E2E: ✅ 全部通过 ({e2e.total_e2e_messages} 条报文)"
                )
            else:
                lines.append(
                    f"  🔒 E2E: ⚠ Counter 错误 {e2e.total_counter_errors}, "
                    f"CRC 错误 {e2e.total_crc_errors} "
                    f"({e2e.messages_with_errors}/{e2e.total_e2e_messages} 报文异常)"
                )
                for r in e2e.results:
                    if not r.is_healthy:
                        lines.append(
                            f"      ⚠ {r.message_name} ({r.id_hex}): "
                            f"Counter={r.counter_error_count}, "
                            f"CRC={r.crc_error_count}"
                        )
        elif not report.e2e_success:
            lines.append(f"  🔒 E2E: ❌ 失败 — {report.e2e_error}")

        lines.append("═" * 50)

        # 根据是否有异常选择日志级别
        has_issues = (
            (report.timing_report and report.timing_report.total_anomalies > 0)
            or (report.dlc_report and report.dlc_report.total_mismatches > 0)
            or (
                report.error_frame_report
                and report.error_frame_report.health_level != "HEALTHY"
            )
            or (
                report.e2e_report
                and (
                    report.e2e_report.total_counter_errors > 0
                    or report.e2e_report.total_crc_errors > 0
                )
            )
        )
        level = "warning" if has_issues else "success"
        self._window.append_log("\n".join(lines), level=level)

    # ═══════════════════════════════════════════════════════
    #  导出报告（第五步核心）
    # ═══════════════════════════════════════════════════════
    def _on_export_report(self):
        """导出分析报告为 .xlsx 或 .csv"""
        logger.info("[AppController] 收到导出报告请求")

        if not self._analysis_report:
            logger.warning("[AppController] 导出请求被拒: 无分析报告")
            self._window.append_log(
                "⚠️ 请先完成分析再导出报告！", level="warning"
            )
            return

        # 弹出文件保存对话框
        from PySide6.QtWidgets import QFileDialog

        default_name = (
            f"CAN_Analysis_Report_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self._window,
            "导出分析报告",
            default_name,
            "Excel 文件 (*.xlsx);;CSV 文件 (*.csv)",
        )

        if not file_path:
            logger.info("[AppController] 导出取消: 用户未选择文件路径")
            return

        logger.info(f"[AppController] 导出目标路径: {file_path}")
        self._window.append_log(f"📤 正在导出报告到: {file_path}")

        try:
            from core.report_exporter import ReportExporter

            exporter = ReportExporter()
            actual_path = exporter.export(self._analysis_report, file_path)

            self._window.append_log(
                f"  ✅ 报告导出成功: {actual_path}",
                level="success",
            )
            logger.info(f"[AppController] 报告导出成功: {actual_path}")

        except Exception as e:
            logger.error(f"[AppController] 报告导出失败: {e}")
            self._window.append_log(
                f"  ❌ 报告导出失败: {e}", level="error"
            )

    # ═══════════════════════════════════════════════════════
    #  辅助方法
    # ═══════════════════════════════════════════════════════
    def _check_ready(self):
        """检查是否两个文件都已解析，启用/禁用分析按钮"""
        ready = self._matrix_data is not None and self._blf_data is not None
        self._window.set_analysis_ready(ready)
        logger.debug(
            f"[AppController] 就绪检查: Matrix={'✓' if self._matrix_data else '✗'}, "
            f"BLF={'✓' if self._blf_data else '✗'}, Ready={ready}"
        )
