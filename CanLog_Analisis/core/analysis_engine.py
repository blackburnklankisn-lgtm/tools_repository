"""
分析引擎总调度器 (Analysis Engine)
统一调度各子分析模块（时序分析、DLC 检查、错误帧监控、E2E 校验），
组合输出完整的分析报告。

设计原则:
  - 高度模块化: 每个分析维度是独立子模块，由引擎统一调度
  - 可扩展: 新增模块只需添加一个 _run_module 调用
  - 异常隔离: 每个子模块错误不影响其他模块执行
"""
import traceback
from dataclasses import dataclass, field
from typing import Optional

from core.matrix_parser import MatrixData
from core.blf_parser import BlfData
from core.timing_analyzer import TimingAnalyzer, TimingReport
from core.dlc_checker import DlcChecker, DlcCheckReport
from core.error_frame_monitor import ErrorFrameMonitor, ErrorFrameReport
from core.e2e_checker import E2EChecker, E2EReport
from logger.log_manager import logger


# ---------------------------------------------------------------------------
# 综合报告
# ---------------------------------------------------------------------------
@dataclass
class AnalysisReport:
    """完整分析报告（包含所有子模块结果）"""
    # 来源文件信息
    matrix_file: str = ""
    blf_file: str = ""

    # 各子模块报告
    timing_report: Optional[TimingReport] = None
    dlc_report: Optional[DlcCheckReport] = None
    error_frame_report: Optional[ErrorFrameReport] = None
    e2e_report: Optional[E2EReport] = None

    # 各子模块执行状态
    timing_success: bool = False
    dlc_success: bool = False
    error_frame_success: bool = False
    e2e_success: bool = False

    # 错误信息（如果子模块执行失败）
    timing_error: str = ""
    dlc_error: str = ""
    error_frame_error: str = ""
    e2e_error: str = ""

    @property
    def all_success(self) -> bool:
        return (
            self.timing_success
            and self.dlc_success
            and self.error_frame_success
            and self.e2e_success
        )


# ---------------------------------------------------------------------------
# 分析引擎
# ---------------------------------------------------------------------------
class AnalysisEngine:
    """
    分析引擎。
    统一调度时序分析、DLC 检查、错误帧监控、E2E 校验四个子模块。
    每个子模块独立执行，互不影响。
    """

    def __init__(
        self,
        timing_threshold_pct: float = 10.0,
        e2e_default_profile: str = "Profile1",
    ):
        """
        Args:
            timing_threshold_pct: 时序偏差阈值百分比
            e2e_default_profile: E2E 默认 Profile 名称
        """
        self._timing_threshold = timing_threshold_pct

        # 初始化子模块
        self._timing_analyzer = TimingAnalyzer(threshold_pct=timing_threshold_pct)
        self._dlc_checker = DlcChecker()
        self._error_monitor = ErrorFrameMonitor()
        self._e2e_checker = E2EChecker(default_profile=e2e_default_profile)

        logger.info(
            f"[AnalysisEngine] 初始化完成, "
            f"时序偏差阈值: ±{timing_threshold_pct}%, "
            f"E2E 默认 Profile: {e2e_default_profile}"
        )

    def run(
        self,
        matrix_data: MatrixData,
        blf_data: BlfData,
    ) -> AnalysisReport:
        """
        执行所有分析子模块。

        Args:
            matrix_data: 解析后的矩阵数据
            blf_data: 解析后的 BLF 数据

        Returns:
            AnalysisReport 综合分析报告
        """
        logger.info("=" * 60)
        logger.info("[AnalysisEngine] ★ 开始综合分析 ★")
        logger.info(
            f"[AnalysisEngine] Matrix: {matrix_data.file_path}\n"
            f"[AnalysisEngine] BLF:    {blf_data.file_path}"
        )
        logger.info("=" * 60)

        report = AnalysisReport(
            matrix_file=matrix_data.file_path,
            blf_file=blf_data.file_path,
        )

        # ── 子模块 1: 时序分析 ──
        report.timing_report, report.timing_success, report.timing_error = (
            self._run_module(
                "时序分析 (Timing Analysis)",
                lambda: self._timing_analyzer.analyze(matrix_data, blf_data),
            )
        )

        # ── 子模块 2: DLC 一致性检查 ──
        report.dlc_report, report.dlc_success, report.dlc_error = (
            self._run_module(
                "DLC 一致性检查 (DLC Check)",
                lambda: self._dlc_checker.check(matrix_data, blf_data),
            )
        )

        # ── 子模块 3: 错误帧监控 ──
        report.error_frame_report, report.error_frame_success, report.error_frame_error = (
            self._run_module(
                "错误帧监控 (Error Frame Monitor)",
                lambda: self._error_monitor.analyze(blf_data),
            )
        )

        # ── 子模块 4: E2E 校验 ──
        report.e2e_report, report.e2e_success, report.e2e_error = (
            self._run_module(
                "E2E 校验 (E2E Protection Check)",
                lambda: self._e2e_checker.check(matrix_data, blf_data),
            )
        )

        # ── 汇总 ──
        logger.info("=" * 60)
        logger.info(
            f"[AnalysisEngine] ★ 综合分析完成 ★"
            f"\n    时序分析:   {'✅ 成功' if report.timing_success else '❌ 失败'}"
            f"\n    DLC 检查:   {'✅ 成功' if report.dlc_success else '❌ 失败'}"
            f"\n    错误帧监控: {'✅ 成功' if report.error_frame_success else '❌ 失败'}"
            f"\n    E2E 校验:   {'✅ 成功' if report.e2e_success else '❌ 失败'}"
        )
        logger.info("=" * 60)

        return report

    @staticmethod
    def _run_module(module_name: str, func) -> tuple:
        """
        安全执行一个分析子模块，捕获异常防止影响其他模块。

        Args:
            module_name: 子模块名称（用于日志）
            func: 要执行的分析函数

        Returns:
            (result, success, error_msg) 三元组
        """
        logger.info(f"[AnalysisEngine] ──── 执行子模块: {module_name} ────")
        try:
            result = func()
            logger.info(f"[AnalysisEngine] ──── {module_name}: 执行成功 ────")
            return result, True, ""
        except Exception as e:
            error_msg = traceback.format_exc()
            logger.error(
                f"[AnalysisEngine] ──── {module_name}: 执行失败 ────\n{error_msg}"
            )
            return None, False, str(e)
