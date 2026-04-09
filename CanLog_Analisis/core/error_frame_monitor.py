"""
错误帧监控子模块 (Error Frame Monitor)
扫描 BLF 中的 Error Frame，统计数量、时间分布，
评估物理层/节点健康度。
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from core.blf_parser import BlfData, ErrorFrameInfo
from logger.log_manager import logger


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass
class ErrorFrameCluster:
    """错误帧聚类（一段时间内密集出现的错误帧）"""
    start_time: float
    end_time: float
    count: int
    channel: Optional[int] = None

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000.0


@dataclass
class ErrorFrameReport:
    """错误帧分析报告"""
    total_error_frames: int = 0
    # 按 Channel 统计 {channel: count}
    errors_by_channel: Dict[int, int] = field(default_factory=dict)
    # 错误帧的发生时间范围
    first_error_time: Optional[float] = None
    last_error_time: Optional[float] = None
    # 错误帧密度（每秒错误帧数）
    error_rate_per_sec: float = 0.0
    # 错误帧聚类（连续密集出现的错误帧分组）
    clusters: List[ErrorFrameCluster] = field(default_factory=list)
    # 健康度评估等级: "HEALTHY", "WARNING", "CRITICAL"
    health_level: str = "HEALTHY"
    health_description: str = ""
    # 所有错误帧的时间戳列表（用于报告导出）
    error_timestamps: List[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 监控器
# ---------------------------------------------------------------------------
class ErrorFrameMonitor:
    """
    错误帧监控器。
    扫描 BLF 数据中的 Error Frame，分析分布模式并评估总线健康度。

    健康度评估标准:
      - HEALTHY:  0 个错误帧，或错误率 < 0.1/s
      - WARNING:  错误率 0.1~1.0/s，或存在聚类
      - CRITICAL: 错误率 > 1.0/s，或聚类密集
    """

    # 聚类检测阈值: 错误帧间隔小于此值（秒）视为同一聚类
    CLUSTER_GAP_THRESHOLD_S = 0.1  # 100ms

    # 健康度阈值
    RATE_WARN_THRESHOLD = 0.1   # 0.1 错误/秒
    RATE_CRIT_THRESHOLD = 1.0   # 1.0 错误/秒

    def __init__(self):
        logger.info("[ErrorFrameMonitor] 初始化完成")

    def analyze(self, blf_data: BlfData) -> ErrorFrameReport:
        """
        执行错误帧分析。

        Args:
            blf_data: 解析后的 BLF 数据

        Returns:
            ErrorFrameReport 分析报告
        """
        logger.info("[ErrorFrameMonitor] ===== 开始错误帧分析 =====")
        logger.info(
            f"[ErrorFrameMonitor] BLF 错误帧总数: {blf_data.total_error_frames}"
        )

        report = ErrorFrameReport(total_error_frames=blf_data.total_error_frames)

        if not blf_data.error_frames:
            logger.info("[ErrorFrameMonitor] 未发现错误帧，总线状态: HEALTHY ✓")
            report.health_level = "HEALTHY"
            report.health_description = "未检测到任何 Error Frame，总线状态良好"
            return report

        # ── 1. 按 Channel 统计 ──
        report.errors_by_channel = self._count_by_channel(blf_data.error_frames)
        for ch, cnt in report.errors_by_channel.items():
            logger.info(f"[ErrorFrameMonitor] Channel {ch}: {cnt} 个错误帧")

        # ── 2. 提取时间范围 ──
        sorted_errors = sorted(blf_data.error_frames, key=lambda e: e.timestamp)
        report.first_error_time = sorted_errors[0].timestamp
        report.last_error_time = sorted_errors[-1].timestamp
        report.error_timestamps = [e.timestamp for e in sorted_errors]

        logger.info(
            f"[ErrorFrameMonitor] 错误帧时间范围: "
            f"{report.first_error_time:.6f}s ~ {report.last_error_time:.6f}s"
        )

        # ── 3. 计算错误率（每秒） ──
        if blf_data.duration_seconds > 0:
            report.error_rate_per_sec = round(
                blf_data.total_error_frames / blf_data.duration_seconds, 4
            )
            logger.info(
                f"[ErrorFrameMonitor] 错误帧速率: "
                f"{report.error_rate_per_sec:.4f} 帧/秒"
            )

        # ── 4. 聚类检测 ──
        report.clusters = self._detect_clusters(sorted_errors)
        if report.clusters:
            logger.info(
                f"[ErrorFrameMonitor] 检测到 {len(report.clusters)} 个错误帧聚类"
            )
            for i, cluster in enumerate(report.clusters):
                logger.info(
                    f"[ErrorFrameMonitor]   聚类 {i + 1}: "
                    f"时间 {cluster.start_time:.6f}s ~ {cluster.end_time:.6f}s, "
                    f"数量 {cluster.count}, "
                    f"持续 {cluster.duration_ms:.1f}ms, "
                    f"Channel={cluster.channel}"
                )

        # ── 5. 健康度评估 ──
        report.health_level, report.health_description = self._assess_health(report)
        logger.info(
            f"[ErrorFrameMonitor] 健康度评估: [{report.health_level}] "
            f"{report.health_description}"
        )

        logger.info("[ErrorFrameMonitor] ===== 错误帧分析完成 =====")
        return report

    @staticmethod
    def _count_by_channel(
        error_frames: List[ErrorFrameInfo],
    ) -> Dict[int, int]:
        """按 Channel 统计错误帧数"""
        counts: Dict[int, int] = {}
        for ef in error_frames:
            ch = ef.channel if ef.channel is not None else 0
            counts[ch] = counts.get(ch, 0) + 1
        return counts

    def _detect_clusters(
        self, sorted_errors: List[ErrorFrameInfo]
    ) -> List[ErrorFrameCluster]:
        """
        检测错误帧聚类（时间上密集出现的错误帧分组）。
        如果连续两个错误帧间隔 < CLUSTER_GAP_THRESHOLD_S，
        则归入同一聚类。
        """
        if len(sorted_errors) < 2:
            logger.debug("[ErrorFrameMonitor] 错误帧数 < 2，无法进行聚类检测")
            return []

        clusters: List[ErrorFrameCluster] = []
        cluster_start = sorted_errors[0]
        cluster_count = 1
        prev = sorted_errors[0]

        for ef in sorted_errors[1:]:
            gap = ef.timestamp - prev.timestamp
            if gap <= self.CLUSTER_GAP_THRESHOLD_S:
                cluster_count += 1
                logger.debug(
                    f"[ErrorFrameMonitor] 聚类增长: gap={gap * 1000:.2f}ms, "
                    f"count={cluster_count}"
                )
            else:
                # 保存上一个聚类（至少 2 个连续错误帧才算聚类）
                if cluster_count >= 2:
                    clusters.append(
                        ErrorFrameCluster(
                            start_time=cluster_start.timestamp,
                            end_time=prev.timestamp,
                            count=cluster_count,
                            channel=cluster_start.channel,
                        )
                    )
                # 开始新聚类
                cluster_start = ef
                cluster_count = 1
            prev = ef

        # 最后一个聚类
        if cluster_count >= 2:
            clusters.append(
                ErrorFrameCluster(
                    start_time=cluster_start.timestamp,
                    end_time=prev.timestamp,
                    count=cluster_count,
                    channel=cluster_start.channel,
                )
            )

        return clusters

    def _assess_health(self, report: ErrorFrameReport) -> tuple:
        """
        基于错误率和聚类情况评估总线健康度。

        Returns:
            (health_level, description) 元组
        """
        rate = report.error_rate_per_sec
        cluster_count = len(report.clusters)

        logger.debug(
            f"[ErrorFrameMonitor] 健康度评估输入: "
            f"rate={rate:.4f}/s, clusters={cluster_count}"
        )

        if rate >= self.RATE_CRIT_THRESHOLD or cluster_count >= 3:
            return (
                "CRITICAL",
                f"错误率 {rate:.2f}/s，聚类 {cluster_count} 个，"
                f"总线通信可能严重受损，建议检查硬件接线和节点状态",
            )
        elif rate >= self.RATE_WARN_THRESHOLD or cluster_count >= 1:
            return (
                "WARNING",
                f"错误率 {rate:.4f}/s，聚类 {cluster_count} 个，"
                f"存在间歇性通信异常，建议关注相关节点和电磁环境",
            )
        else:
            return (
                "HEALTHY",
                f"错误率 {rate:.4f}/s，无密集聚类，总线状态基本正常",
            )
