"""
分析结果表格 UI 组件 (Result Table Widget)
用于在主窗口中以 Tab 页的形式展示各维度的分析结果。
包含：时序分析结果表、DLC 检查结果表、错误帧监控结果表。
"""
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLabel,
)

from core.analysis_engine import AnalysisReport
from core.timing_analyzer import TimingReport, TimingResult
from core.dlc_checker import DlcCheckReport
from core.error_frame_monitor import ErrorFrameReport
from core.e2e_checker import E2EReport, E2EMessageResult
from logger.log_manager import logger


# ─────────────────────────────────────────────────────────────
# 表格样式常量
# ─────────────────────────────────────────────────────────────
COLOR_NORMAL = QColor("#c8d6e5")
COLOR_ANOMALY_BG = QColor("#3d1c1c")      # 异常行背景
COLOR_ANOMALY_TEXT = QColor("#e17055")     # 异常行文字
COLOR_SUCCESS_TEXT = QColor("#00b894")     # 正常项文字
COLOR_WARNING_BG = QColor("#3d3a1c")      # 警告行背景
COLOR_WARNING_TEXT = QColor("#fdcb6e")     # 警告行文字
COLOR_HEADER_BG = QColor("#2c2f4a")

# 表格通用 QSS
TABLE_QSS = """
QTableWidget {
    background-color: #12132a;
    color: #c8d6e5;
    border: 1px solid #2a2d45;
    border-radius: 6px;
    gridline-color: #2a2d45;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
    selection-background-color: #3a7bd5;
}
QTableWidget::item {
    padding: 4px 8px;
}
QHeaderView::section {
    background-color: #2c2f4a;
    color: #7eb8f7;
    border: 1px solid #3a3d5c;
    padding: 6px 8px;
    font-weight: 600;
    font-size: 12px;
}
QTabWidget::pane {
    background-color: #1a1b2e;
    border: 1px solid #3a3d5c;
    border-radius: 6px;
}
QTabBar::tab {
    background-color: #22243a;
    color: #a0b4e0;
    border: 1px solid #3a3d5c;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 12px;
    min-width: 120px;
}
QTabBar::tab:selected {
    background-color: #1a1b2e;
    color: #7eb8f7;
    border-bottom: 2px solid #3a7bd5;
}
QTabBar::tab:hover {
    background-color: #2c2f4a;
}
"""


class ResultTableWidget(QWidget):
    """
    分析结果展示面板。
    以 QTabWidget 组织多个分析维度的表格。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        logger.info("[ResultTableWidget] UI 组件初始化完成")

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 标题
        header = QLabel("📊 分析结果")
        header.setStyleSheet(
            "font-size: 14px; font-weight: 600; color: #a0b4e0; padding: 4px;"
        )
        layout.addWidget(header)

        # Tab Widget
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(TABLE_QSS)
        layout.addWidget(self._tabs, 1)

    # ─────────────────────────────────────────────────────
    #  公共接口: 填充分析结果
    # ─────────────────────────────────────────────────────
    def display_report(self, report: AnalysisReport):
        """
        根据 AnalysisReport 填充所有 Tab 的表格。

        Args:
            report: 分析引擎返回的综合报告
        """
        logger.info("[ResultTableWidget] 开始更新 UI 表格...")

        # 清空旧 Tab
        self._tabs.clear()

        # ── Tab 1: 时序分析 ──
        if report.timing_success and report.timing_report:
            self._add_timing_tab(report.timing_report)
        elif not report.timing_success:
            self._add_error_tab("⏱ 时序分析", report.timing_error)

        # ── Tab 2: DLC 检查 ──
        if report.dlc_success and report.dlc_report:
            self._add_dlc_tab(report.dlc_report)
        elif not report.dlc_success:
            self._add_error_tab("📏 DLC 检查", report.dlc_error)

        # ── Tab 3: 错误帧监控 ──
        if report.error_frame_success and report.error_frame_report:
            self._add_error_frame_tab(report.error_frame_report)
        elif not report.error_frame_success:
            self._add_error_tab("⚡ 错误帧", report.error_frame_error)

        # ── Tab 4: E2E 校验 ──
        if report.e2e_success and report.e2e_report:
            self._add_e2e_tab(report.e2e_report)
        elif not report.e2e_success:
            self._add_error_tab("🔒 E2E 校验", report.e2e_error)

        logger.info("[ResultTableWidget] UI 表格更新完成")

    # ─────────────────────────────────────────────────────
    #  时序分析 Tab
    # ─────────────────────────────────────────────────────
    def _add_timing_tab(self, timing_report: TimingReport):
        """构建时序分析结果表格"""
        logger.info(
            f"[ResultTableWidget] 构建时序分析 Tab: "
            f"{len(timing_report.results)} 条结果, "
            f"{timing_report.total_anomalies} 条异常"
        )

        headers = [
            "Channel", "报文名称", "报文 ID", "Matrix 周期(ms)",
            "实际平均(ms)", "实际最大(ms)", "实际最小(ms)",
            "帧数", "偏差(%)", "状态",
        ]
        table = self._create_table(headers, len(timing_report.results))

        for row, result in enumerate(timing_report.results):
            items = [
                result.channel,
                result.message_name,
                result.id_hex,
                f"{result.matrix_cycle_ms:.0f}" if result.matrix_cycle_ms else "N/A",
                f"{result.actual_avg_ms:.1f}",
                f"{result.actual_max_ms:.1f}",
                f"{result.actual_min_ms:.1f}",
                str(result.actual_count),
                f"{result.deviation_pct:+.1f}" if result.deviation_pct is not None else "N/A",
                "⚠ 异常" if result.is_anomaly else "✓ 正常",
            ]

            for col, text in enumerate(items):
                item = QTableWidgetItem(str(text))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setTextAlignment(Qt.AlignCenter)

                # 异常行高亮
                if result.is_anomaly:
                    item.setBackground(QBrush(COLOR_ANOMALY_BG))
                    item.setForeground(QBrush(COLOR_ANOMALY_TEXT))
                elif col == 9:  # 状态列
                    item.setForeground(QBrush(COLOR_SUCCESS_TEXT))

                table.setItem(row, col, item)

            # 设置 tooltip 显示异常原因
            if result.is_anomaly and result.anomaly_reason:
                for col in range(len(headers)):
                    table.item(row, col).setToolTip(result.anomaly_reason)

        # 汇总信息作为 Tab 标题
        anomaly_count = timing_report.total_anomalies
        tab_label = f"⏱ 时序分析 ({anomaly_count} 异常)" if anomaly_count else "⏱ 时序分析 ✓"
        self._tabs.addTab(table, tab_label)

        # 补充: 缺失/多余报文的子表
        if timing_report.missing_from_log_ids or timing_report.unmatched_log_ids:
            self._add_timing_misc_tab(timing_report)

        logger.info("[ResultTableWidget] 时序分析 Tab 构建完成")

    def _add_timing_misc_tab(self, timing_report: TimingReport):
        """补充 Tab: Matrix/BLF 匹配差异"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        if timing_report.missing_from_log_ids:
            lbl = QLabel(
                f"⚠️ Matrix 中定义但 BLF 中未采集到的报文 "
                f"({len(timing_report.missing_from_log_ids)} 条):"
            )
            lbl.setStyleSheet("color: #fdcb6e; font-size: 12px; padding: 4px;")
            layout.addWidget(lbl)

            ids_text = ", ".join(
                f"0x{aid:03X}" for aid in timing_report.missing_from_log_ids
            )
            ids_lbl = QLabel(ids_text)
            ids_lbl.setStyleSheet(
                "color: #aab0c6; font-size: 11px; padding: 2px 8px;"
            )
            ids_lbl.setWordWrap(True)
            layout.addWidget(ids_lbl)

        if timing_report.unmatched_log_ids:
            lbl = QLabel(
                f"ℹ️ BLF 中出现但 Matrix 中未定义的报文 "
                f"({len(timing_report.unmatched_log_ids)} 条):"
            )
            lbl.setStyleSheet("color: #74b9ff; font-size: 12px; padding: 4px;")
            layout.addWidget(lbl)

            ids_text = ", ".join(
                f"0x{aid:03X}" for aid in timing_report.unmatched_log_ids
            )
            ids_lbl = QLabel(ids_text)
            ids_lbl.setStyleSheet(
                "color: #aab0c6; font-size: 11px; padding: 2px 8px;"
            )
            ids_lbl.setWordWrap(True)
            layout.addWidget(ids_lbl)

        layout.addStretch()
        self._tabs.addTab(widget, "🔍 匹配差异")

    # ─────────────────────────────────────────────────────
    #  DLC 检查 Tab
    # ─────────────────────────────────────────────────────
    def _add_dlc_tab(self, dlc_report: DlcCheckReport):
        """构建 DLC 检查结果表格"""
        logger.info(
            f"[ResultTableWidget] 构建 DLC 检查 Tab: "
            f"{dlc_report.total_checked} 检查, "
            f"{dlc_report.total_mismatches} 不一致"
        )

        if dlc_report.total_mismatches == 0:
            # 全部一致 — 显示简单信息
            widget = QWidget()
            layout = QVBoxLayout(widget)
            lbl = QLabel(
                f"✅ DLC 一致性检查: 全部通过\n"
                f"共检查 {dlc_report.total_checked} 条报文，未发现 DLC 不一致"
            )
            lbl.setStyleSheet(
                "color: #00b894; font-size: 14px; font-weight: 600; padding: 20px;"
            )
            lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(lbl)
            layout.addStretch()
            self._tabs.addTab(widget, "📏 DLC 检查 ✓")
            return

        headers = ["Channel", "报文名称", "报文 ID", "Matrix DLC", "实际 DLC", "差异"]
        table = self._create_table(headers, dlc_report.total_mismatches)

        for row, mm in enumerate(dlc_report.mismatches):
            diff = mm.actual_dlc - mm.matrix_dlc
            items = [
                mm.channel,
                mm.message_name,
                mm.id_hex,
                str(mm.matrix_dlc),
                str(mm.actual_dlc),
                f"{diff:+d}",
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(str(text))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setTextAlignment(Qt.AlignCenter)
                item.setBackground(QBrush(COLOR_WARNING_BG))
                item.setForeground(QBrush(COLOR_WARNING_TEXT))
                table.setItem(row, col, item)

        self._tabs.addTab(
            table,
            f"📏 DLC ({dlc_report.total_mismatches} 不一致)",
        )
        logger.info("[ResultTableWidget] DLC 检查 Tab 构建完成")

    # ─────────────────────────────────────────────────────
    #  错误帧 Tab
    # ─────────────────────────────────────────────────────
    def _add_error_frame_tab(self, ef_report: ErrorFrameReport):
        """构建错误帧监控结果页"""
        logger.info(
            f"[ResultTableWidget] 构建错误帧 Tab: "
            f"总数={ef_report.total_error_frames}, "
            f"健康度={ef_report.health_level}"
        )

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        # 健康度状态卡片
        health_colors = {
            "HEALTHY": ("#00b894", "✅"),
            "WARNING": ("#fdcb6e", "⚠️"),
            "CRITICAL": ("#e17055", "🔴"),
        }
        color, icon = health_colors.get(
            ef_report.health_level, ("#c8d6e5", "❓")
        )

        health_card = QLabel(
            f"{icon} 总线健康度: [{ef_report.health_level}]\n"
            f"{ef_report.health_description}"
        )
        health_card.setStyleSheet(
            f"color: {color}; font-size: 14px; font-weight: 600; "
            f"padding: 12px; background-color: #22243a; "
            f"border-radius: 8px; border: 1px solid #3a3d5c;"
        )
        health_card.setWordWrap(True)
        layout.addWidget(health_card)

        # 统计数据
        stats_text = (
            f"    总错误帧数: {ef_report.total_error_frames}\n"
            f"    错误率: {ef_report.error_rate_per_sec:.4f} 帧/秒\n"
        )
        if ef_report.first_error_time is not None:
            stats_text += (
                f"    首次错误: {ef_report.first_error_time:.6f}s\n"
                f"    末次错误: {ef_report.last_error_time:.6f}s\n"
            )
        for ch, cnt in ef_report.errors_by_channel.items():
            stats_text += f"    Channel {ch}: {cnt} 个错误帧\n"

        stats_lbl = QLabel(stats_text)
        stats_lbl.setStyleSheet(
            "color: #c8d6e5; font-size: 12px; padding: 8px; "
            "font-family: 'Cascadia Code', monospace;"
        )
        layout.addWidget(stats_lbl)

        # 聚类表格
        if ef_report.clusters:
            cluster_header = QLabel(f"⚡ 错误帧聚类 ({len(ef_report.clusters)} 个)")
            cluster_header.setStyleSheet(
                "color: #a0b4e0; font-size: 13px; font-weight: 600; padding: 4px;"
            )
            layout.addWidget(cluster_header)

            headers = ["#", "起始时间(s)", "结束时间(s)", "持续(ms)", "数量", "Channel"]
            table = self._create_table(headers, len(ef_report.clusters))
            for row, cluster in enumerate(ef_report.clusters):
                items = [
                    str(row + 1),
                    f"{cluster.start_time:.6f}",
                    f"{cluster.end_time:.6f}",
                    f"{cluster.duration_ms:.1f}",
                    str(cluster.count),
                    str(cluster.channel) if cluster.channel is not None else "N/A",
                ]
                for col, text in enumerate(items):
                    item = QTableWidgetItem(text)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setForeground(QBrush(COLOR_ANOMALY_TEXT))
                    table.setItem(row, col, item)

            table.setMaximumHeight(200)
            layout.addWidget(table)

        layout.addStretch()

        tab_label = f"⚡ 错误帧 [{ef_report.health_level}]"
        self._tabs.addTab(widget, tab_label)
        logger.info("[ResultTableWidget] 错误帧 Tab 构建完成")

    # ─────────────────────────────────────────────────────
    #  E2E 校验 Tab
    # ─────────────────────────────────────────────────────
    def _add_e2e_tab(self, e2e_report: E2EReport):
        """构建 E2E 校验结果页"""
        logger.info(
            f"[ResultTableWidget] 构建 E2E Tab: "
            f"报文数={e2e_report.total_e2e_messages}, "
            f"Counter错误={e2e_report.total_counter_errors}, "
            f"CRC错误={e2e_report.total_crc_errors}"
        )

        if e2e_report.total_e2e_messages == 0:
            widget = QWidget()
            layout = QVBoxLayout(widget)
            lbl = QLabel(
                "ℹ️ Matrix 中未发现 E2E 保护报文\n"
                "无需执行 E2E 校验"
            )
            lbl.setStyleSheet(
                "color: #74b9ff; font-size: 14px; font-weight: 600; padding: 20px;"
            )
            lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(lbl)
            layout.addStretch()
            self._tabs.addTab(widget, "🔒 E2E (无报文)")
            return

        # ── 汇总信息卡片 ──
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setSpacing(10)

        has_errors = (
            e2e_report.total_counter_errors > 0
            or e2e_report.total_crc_errors > 0
        )

        if has_errors:
            summary_text = (
                f"⚠️ E2E 校验发现问题:\n"
                f"    检查报文数: {e2e_report.total_e2e_messages}\n"
                f"    Counter 错误总数: {e2e_report.total_counter_errors}\n"
                f"    CRC 错误总数: {e2e_report.total_crc_errors}\n"
                f"    有问题的报文: {e2e_report.messages_with_errors}"
            )
            summary_color = "#e17055"
        else:
            summary_text = (
                f"✅ E2E 校验全部通过\n"
                f"    检查报文数: {e2e_report.total_e2e_messages}\n"
                f"    Counter 错误: 0\n"
                f"    CRC 错误: 0"
            )
            summary_color = "#00b894"

        summary_card = QLabel(summary_text)
        summary_card.setStyleSheet(
            f"color: {summary_color}; font-size: 13px; font-weight: 600; "
            f"padding: 12px; background-color: #22243a; "
            f"border-radius: 8px; border: 1px solid #3a3d5c;"
            f"font-family: 'Cascadia Code', monospace;"
        )
        summary_card.setWordWrap(True)
        main_layout.addWidget(summary_card)

        # ── 报文级别汇总表 ──
        headers = [
            "Channel", "报文名称", "报文 ID", "Profile",
            "帧数", "Counter 信号", "Counter 错误",
            "CRC 信号", "CRC 错误", "状态",
        ]
        table = self._create_table(headers, len(e2e_report.results))

        for row, result in enumerate(e2e_report.results):
            items = [
                result.channel,
                result.message_name,
                result.id_hex,
                result.profile_name,
                str(result.total_frames),
                result.counter_signal_name or "N/A",
                str(result.counter_error_count),
                result.crc_signal_name or "N/A",
                str(result.crc_error_count),
                "⚠ 异常" if not result.is_healthy else "✓ 正常",
            ]

            for col, text in enumerate(items):
                item = QTableWidgetItem(str(text))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setTextAlignment(Qt.AlignCenter)

                if not result.is_healthy:
                    item.setBackground(QBrush(COLOR_ANOMALY_BG))
                    item.setForeground(QBrush(COLOR_ANOMALY_TEXT))
                elif col == 9:
                    item.setForeground(QBrush(COLOR_SUCCESS_TEXT))

                table.setItem(row, col, item)

        main_layout.addWidget(table, 1)

        # 跳过的报文提示
        if e2e_report.skipped_messages:
            skip_lbl = QLabel(
                f"⚠ 跳过 {len(e2e_report.skipped_messages)} 条报文:"
            )
            skip_lbl.setStyleSheet(
                "color: #fdcb6e; font-size: 11px; padding: 4px;"
            )
            main_layout.addWidget(skip_lbl)
            for msg in e2e_report.skipped_messages:
                lbl = QLabel(f"  · {msg}")
                lbl.setStyleSheet(
                    "color: #aab0c6; font-size: 11px; padding: 0px 8px;"
                )
                main_layout.addWidget(lbl)

        error_count = (
            e2e_report.total_counter_errors + e2e_report.total_crc_errors
        )
        tab_label = (
            f"🔒 E2E ({error_count} 错误)"
            if error_count
            else "🔒 E2E ✓"
        )
        self._tabs.addTab(widget, tab_label)

        # ── 补充: 详细错误 Tab ──
        if has_errors:
            self._add_e2e_detail_tab(e2e_report)

        logger.info("[ResultTableWidget] E2E Tab 构建完成")

    def _add_e2e_detail_tab(self, e2e_report: E2EReport):
        """构建 E2E 帧级别错误详情 Tab"""
        # 收集所有错误条目
        all_errors = []
        for result in e2e_report.results:
            for err in result.counter_errors:
                all_errors.append((
                    result.message_name,
                    result.id_hex,
                    "Counter",
                    err.error_type.upper(),
                    err.time_str,
                    f"#{err.frame_index}",
                    str(err.expected_value),
                    str(err.actual_value),
                ))
            for err in result.crc_errors:
                all_errors.append((
                    result.message_name,
                    result.id_hex,
                    "CRC",
                    "MISMATCH",
                    err.time_str,
                    f"#{err.frame_index}",
                    f"0x{err.expected_crc:02X}",
                    f"0x{err.actual_crc:02X}",
                ))

        if not all_errors:
            return

        # 限制最多显示 500 条
        display_errors = all_errors[:500]

        headers = [
            "报文名称", "报文 ID", "类型", "错误",
            "时间戳", "帧序号", "期望值", "实际值",
        ]
        table = self._create_table(headers, len(display_errors))

        for row, (name, id_hex, etype, err_type, ts, idx, exp, act) in enumerate(display_errors):
            items = [name, id_hex, etype, err_type, ts, idx, exp, act]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setTextAlignment(Qt.AlignCenter)
                item.setForeground(QBrush(COLOR_ANOMALY_TEXT))
                table.setItem(row, col, item)

        tab_title = f"🔍 E2E 详情 ({len(all_errors)} 错误)"
        if len(all_errors) > 500:
            tab_title += " (前500条)"
        self._tabs.addTab(table, tab_title)

        logger.info(
            f"[ResultTableWidget] E2E 详情 Tab 构建完成: "
            f"{len(display_errors)}/{len(all_errors)} 条显示"
        )

    # ─────────────────────────────────────────────────────
    #  辅助方法
    # ─────────────────────────────────────────────────────
    def _add_error_tab(self, title: str, error_msg: str):
        """为执行失败的子模块添加错误提示 Tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        lbl = QLabel(f"❌ {title} 执行失败:\n{error_msg}")
        lbl.setStyleSheet(
            "color: #e17055; font-size: 13px; padding: 20px;"
        )
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        layout.addStretch()
        self._tabs.addTab(widget, f"{title} ❌")

    @staticmethod
    def _create_table(headers: List[str], row_count: int) -> QTableWidget:
        """创建并配置一个 QTableWidget"""
        table = QTableWidget(row_count, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(False)
        table.setShowGrid(True)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)

        # 列宽自适应
        header_view = table.horizontalHeader()
        for i in range(len(headers)):
            if i == 1:  # 报文名称列稍宽
                header_view.setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                header_view.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        return table
