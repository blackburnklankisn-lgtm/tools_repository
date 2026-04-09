"""
报告导出模块 (Report Exporter)
将 AnalysisReport 中的各维度分析结果导出为 .xlsx 或 .csv 文件。

每个分析维度导出为独立的 Sheet（xlsx）或独立文件（csv）：
  - Sheet 1: 概览 (Overview)
  - Sheet 2: 时序分析 (Timing Analysis)
  - Sheet 3: 时序匹配差异 (Timing Mismatches)
  - Sheet 4: DLC 检查 (DLC Check)
  - Sheet 5: 错误帧 (Error Frames)
  - Sheet 6: E2E 汇总 (E2E Summary)
  - Sheet 7: E2E 详情 (E2E Details)

设计原则:
  - 高度模块化: 每个 Sheet 的数据构建是独立方法
  - 容错: 某个 Sheet 构建失败不影响其他 Sheet
  - 日志充足: 每个步骤都有详细日志
"""
import os
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

from core.analysis_engine import AnalysisReport
from core.timing_analyzer import TimingReport
from core.dlc_checker import DlcCheckReport
from core.error_frame_monitor import ErrorFrameReport
from core.e2e_checker import E2EReport
from logger.log_manager import logger


class ReportExporter:
    """
    分析报告导出器。
    将 AnalysisReport 的分析结果导出为 .xlsx 或 .csv 格式。
    """

    # 支持的导出格式
    SUPPORTED_FORMATS = (".xlsx", ".csv")

    def __init__(self):
        logger.info("[ReportExporter] 初始化完成")

    def export(
        self,
        report: AnalysisReport,
        output_path: str,
    ) -> str:
        """
        导出分析报告到文件。

        Args:
            report: AnalysisReport 综合分析报告
            output_path: 输出文件路径（.xlsx 或 .csv）

        Returns:
            实际输出文件路径

        Raises:
            ValueError: 不支持的文件格式
            IOError: 写入文件失败
        """
        ext = os.path.splitext(output_path)[1].lower()
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"不支持的导出格式: '{ext}'，"
                f"请使用 {self.SUPPORTED_FORMATS}"
            )

        logger.info(f"[ReportExporter] 开始导出报告到: {output_path}")

        # 构建所有 Sheet 的 DataFrame
        sheets = self._build_all_sheets(report)

        if ext == ".xlsx":
            self._export_xlsx(sheets, output_path)
        elif ext == ".csv":
            self._export_csv(sheets, output_path)

        logger.info(
            f"[ReportExporter] 报告导出完成: {output_path} "
            f"({len(sheets)} 个 Sheet)"
        )
        return output_path

    # ═══════════════════════════════════════════════════════
    #  Sheet 数据构建
    # ═══════════════════════════════════════════════════════

    def _build_all_sheets(
        self, report: AnalysisReport
    ) -> Dict[str, pd.DataFrame]:
        """
        构建所有 Sheet 的 DataFrame 字典。
        每个 Sheet 独立构建，某个失败不影响其他。

        Returns:
            {sheet_name: DataFrame} 字典
        """
        sheets: Dict[str, pd.DataFrame] = {}

        # ── Sheet 1: 概览 ──
        df = self._safe_build("概览", lambda: self._build_overview(report))
        if df is not None:
            sheets["Overview"] = df

        # ── Sheet 2: 时序分析 ──
        if report.timing_success and report.timing_report:
            df = self._safe_build(
                "时序分析",
                lambda: self._build_timing_sheet(report.timing_report),
            )
            if df is not None:
                sheets["Timing Analysis"] = df

            # ── Sheet 3: 时序匹配差异 ──
            df = self._safe_build(
                "匹配差异",
                lambda: self._build_timing_mismatch_sheet(report.timing_report),
            )
            if df is not None and not df.empty:
                sheets["Timing Mismatches"] = df

        # ── Sheet 4: DLC 检查 ──
        if report.dlc_success and report.dlc_report:
            df = self._safe_build(
                "DLC 检查",
                lambda: self._build_dlc_sheet(report.dlc_report),
            )
            if df is not None:
                sheets["DLC Check"] = df

        # ── Sheet 5: 错误帧 ──
        if report.error_frame_success and report.error_frame_report:
            df = self._safe_build(
                "错误帧",
                lambda: self._build_error_frame_sheet(report.error_frame_report),
            )
            if df is not None:
                sheets["Error Frames"] = df

        # ── Sheet 6: E2E 汇总 ──
        if report.e2e_success and report.e2e_report:
            df = self._safe_build(
                "E2E 汇总",
                lambda: self._build_e2e_summary_sheet(report.e2e_report),
            )
            if df is not None:
                sheets["E2E Summary"] = df

            # ── Sheet 7: E2E 详情 ──
            df = self._safe_build(
                "E2E 详情",
                lambda: self._build_e2e_detail_sheet(report.e2e_report),
            )
            if df is not None and not df.empty:
                sheets["E2E Details"] = df

        logger.info(
            f"[ReportExporter] 构建完成: {len(sheets)} 个 Sheet — "
            f"{list(sheets.keys())}"
        )
        return sheets

    def _safe_build(
        self, name: str, builder_func
    ) -> Optional[pd.DataFrame]:
        """安全执行 Sheet 构建，捕获异常"""
        try:
            logger.debug(f"[ReportExporter] 构建 Sheet: {name}")
            df = builder_func()
            logger.debug(
                f"[ReportExporter] Sheet '{name}' 构建成功: "
                f"{len(df)} 行, {len(df.columns)} 列"
            )
            return df
        except Exception as e:
            logger.error(
                f"[ReportExporter] Sheet '{name}' 构建失败: {e}\n"
                f"{traceback.format_exc()}"
            )
            return None

    # ─────────────────────────────────────────────────────
    #  Sheet 1: 概览
    # ─────────────────────────────────────────────────────
    @staticmethod
    def _build_overview(report: AnalysisReport) -> pd.DataFrame:
        """概览信息表"""
        rows = [
            ("报告生成时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ("Matrix 文件", report.matrix_file),
            ("BLF 文件", report.blf_file),
            ("", ""),
            ("─── 分析结果概览 ───", ""),
        ]

        # 时序
        if report.timing_success and report.timing_report:
            tr = report.timing_report
            rows.append(("时序分析 - 状态", "✅ 成功"))
            rows.append(("时序分析 - 检查报文数", str(tr.total_checked)))
            rows.append(("时序分析 - 异常报文数", str(tr.total_anomalies)))
            rows.append(("时序分析 - 偏差阈值", f"±{tr.threshold_pct}%"))
            rows.append((
                "时序分析 - Log 缺失报文数",
                str(len(tr.missing_from_log_ids)),
            ))
            rows.append((
                "时序分析 - Matrix 外报文数",
                str(len(tr.unmatched_log_ids)),
            ))
        elif not report.timing_success:
            rows.append(("时序分析 - 状态", f"❌ 失败: {report.timing_error}"))

        rows.append(("", ""))

        # DLC
        if report.dlc_success and report.dlc_report:
            dr = report.dlc_report
            rows.append(("DLC 检查 - 状态", "✅ 成功"))
            rows.append(("DLC 检查 - 检查报文数", str(dr.total_checked)))
            rows.append(("DLC 检查 - 不一致数", str(dr.total_mismatches)))
        elif not report.dlc_success:
            rows.append(("DLC 检查 - 状态", f"❌ 失败: {report.dlc_error}"))

        rows.append(("", ""))

        # 错误帧
        if report.error_frame_success and report.error_frame_report:
            ef = report.error_frame_report
            rows.append(("错误帧 - 状态", "✅ 成功"))
            rows.append(("错误帧 - 总数", str(ef.total_error_frames)))
            rows.append(("错误帧 - 速率 (帧/秒)", f"{ef.error_rate_per_sec:.4f}"))
            rows.append(("错误帧 - 健康度", ef.health_level))
            rows.append(("错误帧 - 聚类数", str(len(ef.clusters))))
        elif not report.error_frame_success:
            rows.append(("错误帧 - 状态", f"❌ 失败: {report.error_frame_error}"))

        rows.append(("", ""))

        # E2E
        if report.e2e_success and report.e2e_report:
            e2e = report.e2e_report
            rows.append(("E2E 校验 - 状态", "✅ 成功"))
            rows.append(("E2E 校验 - 报文数", str(e2e.total_e2e_messages)))
            rows.append(("E2E 校验 - Counter 错误", str(e2e.total_counter_errors)))
            rows.append(("E2E 校验 - CRC 错误", str(e2e.total_crc_errors)))
            rows.append(("E2E 校验 - 异常报文数", str(e2e.messages_with_errors)))
        elif not report.e2e_success:
            rows.append(("E2E 校验 - 状态", f"❌ 失败: {report.e2e_error}"))

        return pd.DataFrame(rows, columns=["项目", "值"])

    # ─────────────────────────────────────────────────────
    #  Sheet 2: 时序分析
    # ─────────────────────────────────────────────────────
    @staticmethod
    def _build_timing_sheet(timing_report: TimingReport) -> pd.DataFrame:
        """时序分析结果表"""
        rows = []
        for r in timing_report.results:
            rows.append({
                "Channel": r.channel,
                "报文名称": r.message_name,
                "报文 ID": r.id_hex,
                "Matrix 周期 (ms)": r.matrix_cycle_ms if r.matrix_cycle_ms else "N/A",
                "实际平均周期 (ms)": round(r.actual_avg_ms, 2),
                "实际最大周期 (ms)": round(r.actual_max_ms, 2),
                "实际最小周期 (ms)": round(r.actual_min_ms, 2),
                "帧数": r.actual_count,
                "偏差 (%)": round(r.deviation_pct, 2) if r.deviation_pct is not None else "N/A",
                "状态": "异常" if r.is_anomaly else "正常",
                "异常原因": r.anomaly_reason if r.is_anomaly else "",
            })

        df = pd.DataFrame(rows)
        logger.debug(
            f"[ReportExporter] 时序分析 Sheet: {len(rows)} 行, "
            f"异常 {sum(1 for r in timing_report.results if r.is_anomaly)} 条"
        )
        return df

    # ─────────────────────────────────────────────────────
    #  Sheet 3: 时序匹配差异
    # ─────────────────────────────────────────────────────
    @staticmethod
    def _build_timing_mismatch_sheet(
        timing_report: TimingReport,
    ) -> pd.DataFrame:
        """Matrix/BLF 匹配差异表"""
        rows = []

        for aid in timing_report.missing_from_log_ids:
            rows.append({
                "报文 ID": f"0x{aid:03X}",
                "类型": "Matrix 有 / BLF 缺失",
                "说明": "该报文在 Matrix 中定义，但 BLF 日志中未采集到",
            })

        for aid in timing_report.unmatched_log_ids:
            rows.append({
                "报文 ID": f"0x{aid:03X}",
                "类型": "BLF 有 / Matrix 未定义",
                "说明": "该报文出现在 BLF 日志中，但 Matrix 中无定义",
            })

        return pd.DataFrame(rows)

    # ─────────────────────────────────────────────────────
    #  Sheet 4: DLC 检查
    # ─────────────────────────────────────────────────────
    @staticmethod
    def _build_dlc_sheet(dlc_report: DlcCheckReport) -> pd.DataFrame:
        """DLC 检查结果表"""
        if dlc_report.total_mismatches == 0:
            return pd.DataFrame(
                [{"结果": "DLC 一致性检查全部通过",
                  "检查报文数": dlc_report.total_checked}]
            )

        rows = []
        for mm in dlc_report.mismatches:
            rows.append({
                "Channel": mm.channel,
                "报文名称": mm.message_name,
                "报文 ID": mm.id_hex,
                "Matrix DLC": mm.matrix_dlc,
                "实际 DLC": mm.actual_dlc,
                "差异": mm.actual_dlc - mm.matrix_dlc,
            })

        return pd.DataFrame(rows)

    # ─────────────────────────────────────────────────────
    #  Sheet 5: 错误帧
    # ─────────────────────────────────────────────────────
    @staticmethod
    def _build_error_frame_sheet(
        ef_report: ErrorFrameReport,
    ) -> pd.DataFrame:
        """错误帧分析结果表"""
        rows = []

        # 概览行
        rows.append({
            "类型": "概览",
            "总数/数量": ef_report.total_error_frames,
            "速率 (帧/秒)": ef_report.error_rate_per_sec,
            "健康度": ef_report.health_level,
            "描述": ef_report.health_description,
            "起始时间 (s)": "",
            "结束时间 (s)": "",
            "持续 (ms)": "",
            "Channel": "",
        })

        # 按 Channel 统计
        for ch, cnt in ef_report.errors_by_channel.items():
            rows.append({
                "类型": f"Channel {ch} 统计",
                "总数/数量": cnt,
                "速率 (帧/秒)": "",
                "健康度": "",
                "描述": "",
                "起始时间 (s)": "",
                "结束时间 (s)": "",
                "持续 (ms)": "",
                "Channel": ch,
            })

        # 聚类信息
        for i, cluster in enumerate(ef_report.clusters):
            rows.append({
                "类型": f"聚类 {i + 1}",
                "总数/数量": cluster.count,
                "速率 (帧/秒)": "",
                "健康度": "",
                "描述": "",
                "起始时间 (s)": f"{cluster.start_time:.6f}",
                "结束时间 (s)": f"{cluster.end_time:.6f}",
                "持续 (ms)": f"{cluster.duration_ms:.1f}",
                "Channel": cluster.channel if cluster.channel is not None else "N/A",
            })

        # 错误帧时间戳（最多 1000 条）
        for i, ts in enumerate(ef_report.error_timestamps[:1000]):
            rows.append({
                "类型": "错误帧",
                "总数/数量": i + 1,
                "速率 (帧/秒)": "",
                "健康度": "",
                "描述": "",
                "起始时间 (s)": f"{ts:.6f}",
                "结束时间 (s)": "",
                "持续 (ms)": "",
                "Channel": "",
            })

        return pd.DataFrame(rows)

    # ─────────────────────────────────────────────────────
    #  Sheet 6: E2E 汇总
    # ─────────────────────────────────────────────────────
    @staticmethod
    def _build_e2e_summary_sheet(e2e_report: E2EReport) -> pd.DataFrame:
        """E2E 校验汇总表"""
        if e2e_report.total_e2e_messages == 0:
            return pd.DataFrame(
                [{"结果": "Matrix 中未发现 E2E 保护报文"}]
            )

        rows = []
        for r in e2e_report.results:
            rows.append({
                "Channel": r.channel,
                "报文名称": r.message_name,
                "报文 ID": r.id_hex,
                "Profile": r.profile_name,
                "总帧数": r.total_frames,
                "Counter 信号": r.counter_signal_name or "N/A",
                "Counter 错误数": r.counter_error_count,
                "CRC 信号": r.crc_signal_name or "N/A",
                "CRC 错误数": r.crc_error_count,
                "状态": "异常" if not r.is_healthy else "正常",
            })

        # 追加跳过的报文
        for skip_msg in e2e_report.skipped_messages:
            rows.append({
                "Channel": "",
                "报文名称": skip_msg,
                "报文 ID": "",
                "Profile": "",
                "总帧数": 0,
                "Counter 信号": "",
                "Counter 错误数": "",
                "CRC 信号": "",
                "CRC 错误数": "",
                "状态": "跳过",
            })

        return pd.DataFrame(rows)

    # ─────────────────────────────────────────────────────
    #  Sheet 7: E2E 详情
    # ─────────────────────────────────────────────────────
    @staticmethod
    def _build_e2e_detail_sheet(e2e_report: E2EReport) -> pd.DataFrame:
        """E2E 帧级别错误详情表"""
        rows = []

        for result in e2e_report.results:
            # Counter 错误
            for err in result.counter_errors:
                rows.append({
                    "报文名称": result.message_name,
                    "报文 ID": result.id_hex,
                    "错误类型": "Counter",
                    "错误子类型": err.error_type.upper(),
                    "时间戳 (s)": f"{err.timestamp:.6f}",
                    "帧序号": err.frame_index,
                    "期望值": str(err.expected_value),
                    "实际值": str(err.actual_value),
                })

            # CRC 错误
            for err in result.crc_errors:
                rows.append({
                    "报文名称": result.message_name,
                    "报文 ID": result.id_hex,
                    "错误类型": "CRC",
                    "错误子类型": "MISMATCH",
                    "时间戳 (s)": f"{err.timestamp:.6f}",
                    "帧序号": err.frame_index,
                    "期望值": f"0x{err.expected_crc:02X}",
                    "实际值": f"0x{err.actual_crc:02X}",
                })

        logger.debug(
            f"[ReportExporter] E2E 详情 Sheet: {len(rows)} 条错误记录"
        )
        return pd.DataFrame(rows)

    # ═══════════════════════════════════════════════════════
    #  文件写入
    # ═══════════════════════════════════════════════════════

    @staticmethod
    def _export_xlsx(
        sheets: Dict[str, pd.DataFrame], output_path: str
    ):
        """导出为 .xlsx 文件（多 Sheet）"""
        logger.info(f"[ReportExporter] 写入 XLSX: {output_path}")

        try:
            with pd.ExcelWriter(
                output_path,
                engine="xlsxwriter",
            ) as writer:
                for sheet_name, df in sheets.items():
                    logger.debug(
                        f"[ReportExporter] 写入 Sheet '{sheet_name}': "
                        f"{len(df)} 行"
                    )
                    df.to_excel(writer, sheet_name=sheet_name, index=False)

                    # 格式美化
                    workbook = writer.book
                    worksheet = writer.sheets[sheet_name]

                    # 设置列宽自适应
                    for col_idx, col_name in enumerate(df.columns):
                        max_len = max(
                            df[col_name].astype(str).map(len).max(),
                            len(str(col_name)),
                        )
                        # 限制最大列宽
                        col_width = min(max_len + 3, 50)
                        worksheet.set_column(col_idx, col_idx, col_width)

                    # 表头格式
                    header_fmt = workbook.add_format({
                        "bold": True,
                        "bg_color": "#2c2f4a",
                        "font_color": "#7eb8f7",
                        "border": 1,
                        "border_color": "#3a3d5c",
                        "text_wrap": True,
                        "valign": "vcenter",
                        "align": "center",
                    })
                    for col_idx, col_name in enumerate(df.columns):
                        worksheet.write(0, col_idx, col_name, header_fmt)

            logger.info(
                f"[ReportExporter] XLSX 写入成功: {output_path}"
            )

        except Exception as e:
            logger.error(
                f"[ReportExporter] XLSX 写入失败: {e}\n"
                f"{traceback.format_exc()}"
            )
            raise IOError(f"XLSX 写入失败: {e}") from e

    @staticmethod
    def _export_csv(
        sheets: Dict[str, pd.DataFrame], output_path: str
    ):
        """
        导出为 .csv 文件。
        由于 CSV 不支持多 Sheet，每个 Sheet 导出为独立文件。
        命名规则: {basename}_{sheet_name}.csv
        """
        base_dir = os.path.dirname(output_path)
        base_name = os.path.splitext(os.path.basename(output_path))[0]

        logger.info(
            f"[ReportExporter] 写入 CSV 到目录: {base_dir}, "
            f"基础文件名: {base_name}"
        )

        exported_files = []
        for sheet_name, df in sheets.items():
            safe_name = sheet_name.replace(" ", "_").replace("/", "_")
            csv_path = os.path.join(base_dir, f"{base_name}_{safe_name}.csv")

            try:
                df.to_csv(csv_path, index=False, encoding="utf-8-sig")
                exported_files.append(csv_path)
                logger.debug(
                    f"[ReportExporter] CSV 写入: {csv_path} ({len(df)} 行)"
                )
            except Exception as e:
                logger.error(
                    f"[ReportExporter] CSV 写入失败 '{csv_path}': {e}"
                )

        logger.info(
            f"[ReportExporter] CSV 导出完成: {len(exported_files)} 个文件"
        )
