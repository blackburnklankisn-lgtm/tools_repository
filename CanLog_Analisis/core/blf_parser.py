"""
BLF 日志解析模块 (BLF Parser)
负责解析 .blf 格式的 CAN log 文件。
使用 python-can 库遍历所有消息，提取基础统计信息。
"""
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import can

from logger.log_manager import logger


@dataclass
class MessageStats:
    """单个报文 ID 的统计数据"""
    arbitration_id: int
    channel: Optional[int] = None
    is_extended_id: bool = False
    is_fd: bool = False
    count: int = 0
    dlc: int = 0
    timestamps: List[float] = field(default_factory=list)
    # 以下在统计完成后填充
    avg_cycle_ms: float = 0.0
    max_cycle_ms: float = 0.0
    min_cycle_ms: float = 0.0
    # 原始数据帧列表（供后续 E2E 校验使用）
    raw_messages: List[can.Message] = field(default_factory=list)


@dataclass
class ErrorFrameInfo:
    """错误帧记录"""
    timestamp: float
    channel: Optional[int] = None


@dataclass
class BlfData:
    """BLF 解析结果汇总"""
    file_path: str = ""
    channels: List[int] = field(default_factory=list)
    total_messages: int = 0
    total_error_frames: int = 0
    duration_seconds: float = 0.0
    first_timestamp: float = 0.0
    last_timestamp: float = 0.0
    # 按 ID 的统计 {arb_id: MessageStats}
    message_stats: Dict[int, MessageStats] = field(default_factory=dict)
    # 按 Channel 的消息数量 {channel: count}
    channel_message_counts: Dict[int, int] = field(default_factory=dict)
    # 按 Channel 的总线负载率 (Busload) {channel: busload%}
    channel_busload: Dict[int, float] = field(default_factory=dict)
    # 错误帧列表
    error_frames: List[ErrorFrameInfo] = field(default_factory=list)


class BlfParser:
    """
    BLF 日志文件解析器。
    遍历 .blf 文件，提取报文统计、周期分析、Busload 和错误帧信息。
    """

    # CAN 标准比特率（默认 500kbps），用于 Busload 估算
    DEFAULT_BITRATE = 500_000

    def __init__(self, bitrate: int = DEFAULT_BITRATE):
        self._bitrate = bitrate
        self._blf_data: Optional[BlfData] = None

    @property
    def data(self) -> Optional[BlfData]:
        return self._blf_data

    def parse(self, file_path: str, store_raw: bool = True) -> BlfData:
        """
        解析 BLF 文件并提取统计数据。

        Args:
            file_path: .blf 文件路径
            store_raw: 是否保留原始消息数据（用于后续 E2E 校验），
                       大型文件可设为 False 以节省内存。

        Returns:
            BlfData 解析结果

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件格式错误或解析失败
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"BLF 文件不存在: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        if ext != ".blf":
            raise ValueError(f"不支持的日志文件格式: {ext}，请使用 .blf 格式")

        logger.info(f"开始解析 BLF 文件: {file_path}")

        blf_data = BlfData(file_path=file_path)
        channels_set = set()
        channel_bits: Dict[int, int] = defaultdict(int)  # 用于 Busload 计算

        try:
            reader = can.BLFReader(file_path)
        except Exception as e:
            raise ValueError(f"BLF 文件打开失败: {e}") from e

        first_ts = None
        last_ts = None
        msg_count = 0

        try:
            for msg in reader:
                # 错误帧处理
                if msg.is_error_frame:
                    blf_data.error_frames.append(
                        ErrorFrameInfo(
                            timestamp=msg.timestamp,
                            channel=msg.channel,
                        )
                    )
                    blf_data.total_error_frames += 1
                    continue

                # 远程帧等不纳入常规统计
                if msg.is_remote_frame:
                    continue

                msg_count += 1
                arb_id = msg.arbitration_id
                ch = msg.channel if msg.channel is not None else 0

                channels_set.add(ch)

                # 累加 channel 消息数量
                blf_data.channel_message_counts[ch] = (
                    blf_data.channel_message_counts.get(ch, 0) + 1
                )

                # Busload 估算: 每帧约 (DLC*8 + 47) bit（标准帧开销约 47 bit）
                frame_bits = (msg.dlc * 8) + 47
                if msg.is_extended_id:
                    frame_bits += 18  # 扩展帧额外位
                channel_bits[ch] += frame_bits

                # 时间戳范围
                if first_ts is None:
                    first_ts = msg.timestamp
                last_ts = msg.timestamp

                # 按 ID 统计
                if arb_id not in blf_data.message_stats:
                    blf_data.message_stats[arb_id] = MessageStats(
                        arbitration_id=arb_id,
                        channel=ch,
                        is_extended_id=msg.is_extended_id,
                        is_fd=msg.is_fd,
                        dlc=msg.dlc,
                    )

                stats = blf_data.message_stats[arb_id]
                stats.count += 1
                stats.timestamps.append(msg.timestamp)
                if store_raw:
                    stats.raw_messages.append(msg)

        except Exception as e:
            logger.error(f"BLF 遍历过程中出错: {e}")
            raise ValueError(f"BLF 文件读取错误: {e}") from e

        # 汇总基础信息
        blf_data.total_messages = msg_count
        blf_data.channels = sorted(channels_set)
        if first_ts is not None and last_ts is not None:
            blf_data.first_timestamp = first_ts
            blf_data.last_timestamp = last_ts
            blf_data.duration_seconds = last_ts - first_ts

        # 计算各 ID 的周期统计
        for arb_id, stats in blf_data.message_stats.items():
            self._calc_cycle_stats(stats)

        # 计算各 Channel 的 Busload
        if blf_data.duration_seconds > 0:
            for ch, bits in channel_bits.items():
                # Busload = 实际传输 bit 数 / (持续时间 × 比特率) × 100%
                busload = (bits / (blf_data.duration_seconds * self._bitrate)) * 100.0
                blf_data.channel_busload[ch] = round(busload, 2)

        self._blf_data = blf_data

        logger.info(
            f"BLF 解析完成: {msg_count} 条消息, "
            f"{blf_data.total_error_frames} 个错误帧, "
            f"Channels: {blf_data.channels}, "
            f"持续时间: {blf_data.duration_seconds:.2f}s"
        )
        return blf_data

    @staticmethod
    def _calc_cycle_stats(stats: MessageStats):
        """计算单个报文 ID 的周期统计（ms）"""
        if len(stats.timestamps) < 2:
            stats.avg_cycle_ms = 0.0
            stats.max_cycle_ms = 0.0
            stats.min_cycle_ms = 0.0
            return

        deltas = []
        sorted_ts = sorted(stats.timestamps)
        for i in range(1, len(sorted_ts)):
            delta_ms = (sorted_ts[i] - sorted_ts[i - 1]) * 1000.0  # s -> ms
            deltas.append(delta_ms)

        stats.avg_cycle_ms = round(sum(deltas) / len(deltas), 2) if deltas else 0.0
        stats.max_cycle_ms = round(max(deltas), 2) if deltas else 0.0
        stats.min_cycle_ms = round(min(deltas), 2) if deltas else 0.0
