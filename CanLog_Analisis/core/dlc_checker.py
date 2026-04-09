"""
DLC 一致性检查子模块 (DLC Checker)
对比 Matrix 定义的 DLC 与 BLF 实际采集到的 DLC，
输出不一致警告。
"""
from dataclasses import dataclass, field
from typing import List

from core.matrix_parser import MatrixData
from core.blf_parser import BlfData
from logger.log_manager import logger


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass
class DlcMismatchItem:
    """单条 DLC 不一致记录"""
    channel: str
    message_name: str
    arbitration_id: int
    matrix_dlc: int
    actual_dlc: int

    @property
    def id_hex(self) -> str:
        return f"0x{self.arbitration_id:03X}"


@dataclass
class DlcCheckReport:
    """DLC 检查汇总报告"""
    total_checked: int = 0
    total_mismatches: int = 0
    mismatches: List[DlcMismatchItem] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 检查器
# ---------------------------------------------------------------------------
class DlcChecker:
    """
    DLC 一致性检查器。
    逐条比对 Matrix 中的 DLC 定义与 BLF 中实际采集到的 DLC。
    """

    def __init__(self):
        logger.info("[DlcChecker] 初始化完成")

    def check(
        self,
        matrix_data: MatrixData,
        blf_data: BlfData,
    ) -> DlcCheckReport:
        """
        执行 DLC 一致性检查。

        Args:
            matrix_data: 解析后的矩阵数据
            blf_data: 解析后的 BLF 数据

        Returns:
            DlcCheckReport 检查报告
        """
        logger.info("[DlcChecker] ===== 开始 DLC 一致性检查 =====")

        report = DlcCheckReport()

        for arb_id, msg_info in matrix_data.messages.items():
            blf_stats = blf_data.message_stats.get(arb_id)
            if blf_stats is None:
                # 该报文在 BLF 中不存在，跳过（TimingAnalyzer 会报告）
                logger.debug(
                    f"[DlcChecker] 跳过 {msg_info.name} (0x{arb_id:03X}): "
                    f"BLF 中无此报文"
                )
                continue

            report.total_checked += 1
            matrix_dlc = msg_info.dlc
            actual_dlc = blf_stats.dlc

            logger.debug(
                f"[DlcChecker] 检查 {msg_info.name} (0x{arb_id:03X}): "
                f"Matrix DLC={matrix_dlc}, 实际 DLC={actual_dlc}"
            )

            if matrix_dlc != actual_dlc:
                mismatch = DlcMismatchItem(
                    channel=msg_info.channel,
                    message_name=msg_info.name,
                    arbitration_id=arb_id,
                    matrix_dlc=matrix_dlc,
                    actual_dlc=actual_dlc,
                )
                report.mismatches.append(mismatch)
                report.total_mismatches += 1

                logger.warning(
                    f"[DlcChecker] ⚠️ DLC 不一致: {msg_info.name} "
                    f"(0x{arb_id:03X}) — "
                    f"Matrix={matrix_dlc}, 实际={actual_dlc}"
                )

        logger.info(
            f"[DlcChecker] ===== DLC 检查完成 ====="
            f"\n    检查报文数: {report.total_checked}"
            f"\n    不一致数: {report.total_mismatches}"
        )

        return report
