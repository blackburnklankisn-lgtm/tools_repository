"""
时序分析子模块 (Timing Analyzer)
对比 Matrix 定义的报文周期与 BLF 实际采集的报文周期，
输出偏差分析结果，标记超时/周期异常的报文。
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.matrix_parser import MatrixData, MessageInfo
from core.blf_parser import BlfData, MessageStats
from logger.log_manager import logger


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass
class TimingResult:
    """单条报文的时序分析结果"""
    channel: str                         # CAN Channel
    message_name: str                    # 报文名称
    arbitration_id: int                  # 报文 ID
    matrix_cycle_ms: Optional[float]     # Matrix 设定周期 (ms)
    actual_avg_ms: float                 # 实际平均周期 (ms)
    actual_max_ms: float                 # 实际最大周期 (ms)
    actual_min_ms: float                 # 实际最小周期 (ms)
    actual_count: int                    # 实际收到帧数
    deviation_pct: Optional[float]       # 偏差比例 (%)，None 表示 Matrix 无周期定义
    is_anomaly: bool = False             # 是否标记为异常
    anomaly_reason: str = ""             # 异常原因描述

    @property
    def id_hex(self) -> str:
        return f"0x{self.arbitration_id:03X}"


@dataclass
class TimingReport:
    """时序分析汇总报告"""
    total_checked: int = 0               # 总检查报文数
    total_anomalies: int = 0             # 异常数量
    threshold_pct: float = 10.0          # 使用的偏差阈值
    results: List[TimingResult] = field(default_factory=list)
    # 仅在 Log 中出现但 Matrix 中不存在的报文
    unmatched_log_ids: List[int] = field(default_factory=list)
    # 在 Matrix 中定义但 Log 中未采集到的报文
    missing_from_log_ids: List[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 分析器
# ---------------------------------------------------------------------------
class TimingAnalyzer:
    """
    时序分析器。
    对比 Matrix 基准与 BLF 实际数据，按报文逐条输出偏差。
    """

    def __init__(self, threshold_pct: float = 10.0):
        """
        Args:
            threshold_pct: 偏差阈值百分比。
                           实际周期偏差超过 ±threshold_pct% 标记为异常。
        """
        self._threshold = threshold_pct
        logger.info(f"[TimingAnalyzer] 初始化完成, 偏差阈值: ±{threshold_pct}%")

    def analyze(
        self,
        matrix_data: MatrixData,
        blf_data: BlfData,
    ) -> TimingReport:
        """
        执行时序分析。

        Args:
            matrix_data: 解析后的矩阵数据
            blf_data: 解析后的 BLF 数据

        Returns:
            TimingReport 分析报告
        """
        logger.info("[TimingAnalyzer] ===== 开始时序分析 =====")
        logger.info(
            f"[TimingAnalyzer] Matrix 报文数: {matrix_data.total_messages}, "
            f"BLF 报文 ID 数: {len(blf_data.message_stats)}"
        )

        report = TimingReport(threshold_pct=self._threshold)

        # ── 1. 遍历 Matrix 中的每条报文，与 BLF 实际数据比对 ──
        for arb_id, msg_info in matrix_data.messages.items():
            logger.debug(
                f"[TimingAnalyzer] 检查报文: {msg_info.name} "
                f"(ID=0x{arb_id:03X}, Channel={msg_info.channel}, "
                f"MatrixCycle={msg_info.cycle_time_ms}ms)"
            )

            blf_stats = blf_data.message_stats.get(arb_id)

            if blf_stats is None:
                # Matrix 中定义但 Log 中未采集到
                logger.warning(
                    f"[TimingAnalyzer] 报文 {msg_info.name} (0x{arb_id:03X}) "
                    f"在 Matrix 中定义，但 BLF 日志中未采集到！"
                )
                report.missing_from_log_ids.append(arb_id)
                continue

            result = self._evaluate_timing(msg_info, blf_stats)
            report.results.append(result)
            report.total_checked += 1

            if result.is_anomaly:
                report.total_anomalies += 1
                logger.warning(
                    f"[TimingAnalyzer] ⚠️ 异常: {result.message_name} "
                    f"(0x{arb_id:03X}) — {result.anomaly_reason}"
                )
            else:
                logger.debug(
                    f"[TimingAnalyzer] ✓ 正常: {result.message_name} "
                    f"(0x{arb_id:03X}) 偏差={result.deviation_pct}%"
                )

        # ── 2. 检查 BLF 中存在但 Matrix 中未定义的报文 ──
        matrix_ids = set(matrix_data.messages.keys())
        for arb_id in blf_data.message_stats:
            if arb_id not in matrix_ids:
                report.unmatched_log_ids.append(arb_id)
                logger.info(
                    f"[TimingAnalyzer] 报文 0x{arb_id:03X} 出现在 BLF 中，"
                    f"但 Matrix 中未定义"
                )

        # ── 3. 汇总日志 ──
        logger.info(
            f"[TimingAnalyzer] ===== 时序分析完成 ====="
            f"\n    检查报文数: {report.total_checked}"
            f"\n    异常报文数: {report.total_anomalies}"
            f"\n    Log 中缺失(Matrix有): {len(report.missing_from_log_ids)}"
            f"\n    Matrix 中缺失(Log有): {len(report.unmatched_log_ids)}"
        )

        return report

    def _evaluate_timing(
        self, msg_info: MessageInfo, blf_stats: MessageStats
    ) -> TimingResult:
        """
        评估单条报文的时序偏差。

        Args:
            msg_info: Matrix 中的报文定义
            blf_stats: BLF 中的实际统计

        Returns:
            TimingResult 评估结果
        """
        matrix_cycle = msg_info.cycle_time_ms
        actual_avg = blf_stats.avg_cycle_ms
        actual_max = blf_stats.max_cycle_ms
        actual_min = blf_stats.min_cycle_ms

        # 计算偏差
        deviation_pct = None
        is_anomaly = False
        anomaly_reason = ""

        if matrix_cycle is not None and matrix_cycle > 0:
            deviation_pct = round(
                ((actual_avg - matrix_cycle) / matrix_cycle) * 100.0, 2
            )

            logger.debug(
                f"[TimingAnalyzer] {msg_info.name}: "
                f"MatrixCycle={matrix_cycle}ms, ActualAvg={actual_avg}ms, "
                f"Deviation={deviation_pct}%"
            )

            # 检查平均周期偏差
            if abs(deviation_pct) > self._threshold:
                is_anomaly = True
                if deviation_pct > 0:
                    anomaly_reason = (
                        f"平均周期偏大 {deviation_pct:+.2f}% "
                        f"(实际 {actual_avg:.1f}ms vs 设定 {matrix_cycle}ms)"
                    )
                else:
                    anomaly_reason = (
                        f"平均周期偏小 {deviation_pct:+.2f}% "
                        f"(实际 {actual_avg:.1f}ms vs 设定 {matrix_cycle}ms)"
                    )

            # 检查最大周期是否急剧偏大（超过 2 倍设定周期视为可能丢帧）
            if actual_max > matrix_cycle * 2.0:
                is_anomaly = True
                max_reason = (
                    f"最大周期 {actual_max:.1f}ms 超过设定值 2 倍 "
                    f"(设定 {matrix_cycle}ms)，可能存在丢帧"
                )
                if anomaly_reason:
                    anomaly_reason += "; " + max_reason
                else:
                    anomaly_reason = max_reason
        else:
            logger.debug(
                f"[TimingAnalyzer] {msg_info.name}: "
                f"Matrix 未定义周期，跳过偏差计算"
            )

        return TimingResult(
            channel=msg_info.channel,
            message_name=msg_info.name,
            arbitration_id=msg_info.arbitration_id,
            matrix_cycle_ms=matrix_cycle,
            actual_avg_ms=actual_avg,
            actual_max_ms=actual_max,
            actual_min_ms=actual_min,
            actual_count=blf_stats.count,
            deviation_pct=deviation_pct,
            is_anomaly=is_anomaly,
            anomaly_reason=anomaly_reason,
        )
