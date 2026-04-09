"""
矩阵解析模块 (Matrix Parser)
负责解析 .xlsx 格式的 CAN/LIN 通信矩阵文件。
使用 canmatrix 库提取报文 ID、DLC、周期、信号等结构化信息。
"""
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import canmatrix
import canmatrix.formats

from logger.log_manager import logger


@dataclass
class SignalInfo:
    """信号描述"""
    name: str
    start_bit: int
    bit_length: int
    is_signed: bool = False
    factor: float = 1.0
    offset: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0
    unit: str = ""
    comment: str = ""
    # E2E 相关标记
    is_e2e_counter: bool = False
    is_e2e_crc: bool = False


@dataclass
class MessageInfo:
    """报文描述"""
    name: str
    arbitration_id: int
    dlc: int
    cycle_time_ms: Optional[float] = None  # Matrix 定义的周期 (ms)
    channel: str = ""
    sender: str = ""
    is_extended_id: bool = False
    is_fd: bool = False
    signals: List[SignalInfo] = field(default_factory=list)
    # E2E 保护信息
    e2e_enabled: bool = False
    e2e_profile: str = ""  # 例如 "Profile1", "Profile2", "Profile11"
    e2e_counter_signal: Optional[str] = None
    e2e_crc_signal: Optional[str] = None
    comment: str = ""


@dataclass
class MatrixData:
    """解析后的矩阵数据汇总"""
    file_path: str = ""
    channels: List[str] = field(default_factory=list)
    messages: Dict[int, MessageInfo] = field(default_factory=dict)  # key = arb_id
    # 按 channel 分组的消息
    messages_by_channel: Dict[str, List[MessageInfo]] = field(default_factory=dict)
    total_messages: int = 0
    total_signals: int = 0


class MatrixParser:
    """
    CAN 通信矩阵解析器。
    支持 .xlsx 格式的矩阵文件解析。
    """

    def __init__(self):
        self._matrix_data: Optional[MatrixData] = None

    @property
    def data(self) -> Optional[MatrixData]:
        return self._matrix_data

    def parse(self, file_path: str) -> MatrixData:
        """
        解析矩阵文件并返回结构化数据。

        Args:
            file_path: .xlsx 矩阵文件路径

        Returns:
            MatrixData 解析结果

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件格式错误或解析失败
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"矩阵文件不存在: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in (".xlsx", ".xls"):
            raise ValueError(f"不支持的矩阵文件格式: {ext}，请使用 .xlsx 格式")

        logger.info(f"开始解析矩阵文件: {file_path}")

        try:
            # canmatrix 加载 xlsx
            db_dict = canmatrix.formats.loadp(file_path)
        except Exception as e:
            raise ValueError(f"矩阵文件解析失败: {e}") from e

        matrix_data = MatrixData(file_path=file_path)
        total_signals = 0

        for channel_name, db in db_dict.items():
            # 跳过空数据库
            if not db.frames:
                continue

            ch_name = str(channel_name) if channel_name else "CAN"
            if ch_name not in matrix_data.channels:
                matrix_data.channels.append(ch_name)

            matrix_data.messages_by_channel.setdefault(ch_name, [])

            for frame in db.frames:
                msg_info = self._parse_frame(frame, ch_name)
                total_signals += len(msg_info.signals)

                matrix_data.messages[msg_info.arbitration_id] = msg_info
                matrix_data.messages_by_channel[ch_name].append(msg_info)

        matrix_data.total_messages = len(matrix_data.messages)
        matrix_data.total_signals = total_signals
        self._matrix_data = matrix_data

        logger.info(
            f"矩阵解析完成: {matrix_data.total_messages} 条报文, "
            f"{matrix_data.total_signals} 个信号, "
            f"Channel: {matrix_data.channels}"
        )
        return matrix_data

    def _parse_frame(self, frame, channel: str) -> MessageInfo:
        """解析单个 CAN Frame"""
        # 提取周期时间
        cycle_time = None
        try:
            ct_attr = frame.attribute("GenMsgCycleTime")
            if ct_attr is not None:
                cycle_time = float(ct_attr)
        except (KeyError, ValueError, TypeError):
            pass

        # 有些矩阵使用 "CycleTime" 属性
        if cycle_time is None:
            try:
                ct_attr = frame.attribute("CycleTime")
                if ct_attr is not None:
                    cycle_time = float(ct_attr)
            except (KeyError, ValueError, TypeError):
                pass

        # 提取发送节点
        sender = ""
        if frame.transmitters:
            sender = frame.transmitters[0]

        msg_info = MessageInfo(
            name=frame.name,
            arbitration_id=frame.arbitration_id.id,
            dlc=frame.size,
            cycle_time_ms=cycle_time,
            channel=channel,
            sender=sender,
            is_extended_id=frame.arbitration_id.extended,
            comment=frame.comment or "",
        )

        # 解析信号
        for signal in frame.signals:
            sig_info = self._parse_signal(signal)
            msg_info.signals.append(sig_info)

            # 自动识别 E2E 信号（根据命名惯例）
            sig_name_lower = signal.name.lower()
            if any(kw in sig_name_lower for kw in ("counter", "alivecnt", "alive_cnt", "rollingcnt")):
                sig_info.is_e2e_counter = True
                msg_info.e2e_counter_signal = signal.name
                msg_info.e2e_enabled = True
            elif any(kw in sig_name_lower for kw in ("crc", "checksum", "chksum")):
                sig_info.is_e2e_crc = True
                msg_info.e2e_crc_signal = signal.name
                msg_info.e2e_enabled = True

        return msg_info

    @staticmethod
    def _parse_signal(signal) -> SignalInfo:
        """解析单个 CAN Signal"""
        return SignalInfo(
            name=signal.name,
            start_bit=signal.start_bit,
            bit_length=signal.size,
            is_signed=signal.is_signed,
            factor=float(signal.factor) if signal.factor else 1.0,
            offset=float(signal.offset) if signal.offset else 0.0,
            min_val=float(signal.min) if signal.min else 0.0,
            max_val=float(signal.max) if signal.max else 0.0,
            unit=signal.unit or "",
            comment=signal.comment or "",
        )
