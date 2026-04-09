"""
E2E 校验模块 (E2E Checker)
对 Matrix 中标记为 E2E 保护的报文，提取 Counter 和 CRC 信号值，
验证 Counter 连续性和 CRC 正确性。

职责:
  - 遍历所有 E2E 报文的原始帧数据
  - Counter 连续性检查（跳变/重复检测）
  - CRC 校验验证（基于 Profile 算法）
  - 输出按报文分组的详细 E2E 校验报告
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import can

from core.matrix_parser import MatrixData, MessageInfo, SignalInfo
from core.blf_parser import BlfData, MessageStats
from core.e2e_profiles import E2EProfileBase, get_e2e_profile, get_default_profile
from logger.log_manager import logger


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class CounterError:
    """Counter 跳变/重复记录"""
    timestamp: float          # 发生时间
    frame_index: int          # 帧序号（在该 ID 的帧序列中）
    expected_value: int       # 期望值
    actual_value: int         # 实际值
    error_type: str = ""      # "jump" 或 "repeat"

    @property
    def time_str(self) -> str:
        return f"{self.timestamp:.6f}s"


@dataclass
class CrcError:
    """CRC 校验失败记录"""
    timestamp: float
    frame_index: int
    expected_crc: int         # 计算出的正确 CRC
    actual_crc: int           # 帧中的实际 CRC

    @property
    def time_str(self) -> str:
        return f"{self.timestamp:.6f}s"


@dataclass
class E2EMessageResult:
    """单条 E2E 报文的校验结果"""
    channel: str
    message_name: str
    arbitration_id: int
    profile_name: str
    total_frames: int              # 校验的总帧数
    # Counter 结果
    counter_signal_name: str = ""
    counter_errors: List[CounterError] = field(default_factory=list)
    counter_error_count: int = 0
    # CRC 结果
    crc_signal_name: str = ""
    crc_errors: List[CrcError] = field(default_factory=list)
    crc_error_count: int = 0
    # 整体状态
    is_healthy: bool = True

    @property
    def id_hex(self) -> str:
        return f"0x{self.arbitration_id:03X}"


@dataclass
class E2EReport:
    """E2E 校验汇总报告"""
    total_e2e_messages: int = 0          # 检查的 E2E 报文数量
    total_counter_errors: int = 0        # Counter 错误总数
    total_crc_errors: int = 0            # CRC 错误总数
    messages_with_errors: int = 0        # 有错误的报文数
    results: List[E2EMessageResult] = field(default_factory=list)
    # 未能检查的报文（BLF 中无数据或无原始帧）
    skipped_messages: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 信号提取工具
# ---------------------------------------------------------------------------

class SignalExtractor:
    """
    从 CAN 数据帧 payload 中提取指定信号的值。
    支持 Intel (little-endian) 和 Motorola (big-endian) 字节序。
    注意: 当前实现使用简化的 Intel 字节序提取。
    """

    @staticmethod
    def extract_signal_value(
        data: bytes,
        start_bit: int,
        bit_length: int,
        is_signed: bool = False,
    ) -> int:
        """
        从 payload 字节中提取信号值（Intel 字节序）。

        Args:
            data: CAN 帧的 payload 字节
            start_bit: 起始 bit 位置
            bit_length: 信号位长度
            is_signed: 是否有符号

        Returns:
            提取出的整数值
        """
        if not data or bit_length <= 0:
            return 0

        # 将 payload 转为 bit 数组
        total_bits = len(data) * 8
        if start_bit + bit_length > total_bits:
            logger.warning(
                f"[SignalExtractor] 信号越界: start_bit={start_bit}, "
                f"bit_length={bit_length}, payload_bits={total_bits}"
            )
            return 0

        # Intel 字节序: LSB 在低 bit 位
        value = 0
        for i in range(bit_length):
            bit_pos = start_bit + i
            byte_idx = bit_pos // 8
            bit_idx = bit_pos % 8
            if data[byte_idx] & (1 << bit_idx):
                value |= (1 << i)

        # 有符号处理
        if is_signed and bit_length > 1:
            if value & (1 << (bit_length - 1)):
                value -= (1 << bit_length)

        return value


# ---------------------------------------------------------------------------
# E2E 校验器
# ---------------------------------------------------------------------------

class E2EChecker:
    """
    AUTOSAR E2E 校验器。
    对 Matrix 中标记为 E2E 保护的报文执行:
      1. Counter 连续性检查
      2. CRC 校验验证

    使用方式:
      checker = E2EChecker()
      report = checker.check(matrix_data, blf_data)
    """

    def __init__(self, default_profile: str = "Profile1"):
        """
        Args:
            default_profile: 当 Matrix 中未指定 Profile 时使用的默认 Profile
        """
        self._default_profile_name = default_profile
        self._signal_extractor = SignalExtractor()
        logger.info(
            f"[E2EChecker] 初始化完成, 默认 Profile: {default_profile}"
        )

    def check(
        self,
        matrix_data: MatrixData,
        blf_data: BlfData,
    ) -> E2EReport:
        """
        执行 E2E 校验。

        Args:
            matrix_data: 解析后的矩阵数据
            blf_data: 解析后的 BLF 数据

        Returns:
            E2EReport 校验报告
        """
        logger.info("[E2EChecker] ===== 开始 E2E 校验 =====")

        report = E2EReport()

        # ── 1. 收集所有 E2E 报文 ──
        e2e_messages = self._collect_e2e_messages(matrix_data)

        if not e2e_messages:
            logger.info("[E2EChecker] Matrix 中未发现 E2E 保护报文，跳过校验")
            return report

        logger.info(f"[E2EChecker] 发现 {len(e2e_messages)} 条 E2E 报文")

        # ── 2. 逐条报文校验 ──
        for msg_info in e2e_messages:
            arb_id = msg_info.arbitration_id
            blf_stats = blf_data.message_stats.get(arb_id)

            if blf_stats is None or not blf_stats.raw_messages:
                skip_reason = (
                    f"{msg_info.name} (0x{arb_id:03X}): BLF 中无数据"
                )
                report.skipped_messages.append(skip_reason)
                logger.warning(f"[E2EChecker] 跳过: {skip_reason}")
                continue

            result = self._check_message(msg_info, blf_stats)
            report.results.append(result)
            report.total_e2e_messages += 1
            report.total_counter_errors += result.counter_error_count
            report.total_crc_errors += result.crc_error_count

            if not result.is_healthy:
                report.messages_with_errors += 1

        # ── 3. 汇总日志 ──
        logger.info(
            f"[E2EChecker] ===== E2E 校验完成 ====="
            f"\n    校验报文数: {report.total_e2e_messages}"
            f"\n    Counter 错误总数: {report.total_counter_errors}"
            f"\n    CRC 错误总数: {report.total_crc_errors}"
            f"\n    有问题的报文数: {report.messages_with_errors}"
            f"\n    跳过的报文数: {len(report.skipped_messages)}"
        )

        return report

    # ─────────────────────────────────────────────────────
    #  内部方法
    # ─────────────────────────────────────────────────────

    @staticmethod
    def _collect_e2e_messages(matrix_data: MatrixData) -> List[MessageInfo]:
        """从 Matrix 中收集所有标记为 E2E 的报文"""
        e2e_msgs = []
        for arb_id, msg_info in matrix_data.messages.items():
            if msg_info.e2e_enabled:
                e2e_msgs.append(msg_info)
                logger.debug(
                    f"[E2EChecker] E2E 报文: {msg_info.name} (0x{arb_id:03X}), "
                    f"Profile={msg_info.e2e_profile or 'auto'}, "
                    f"Counter={msg_info.e2e_counter_signal}, "
                    f"CRC={msg_info.e2e_crc_signal}"
                )
        return e2e_msgs

    def _check_message(
        self,
        msg_info: MessageInfo,
        blf_stats: MessageStats,
    ) -> E2EMessageResult:
        """
        对单条 E2E 报文执行 Counter + CRC 校验。

        Args:
            msg_info: Matrix 中的报文信息
            blf_stats: BLF 中该报文的统计数据（含原始帧）

        Returns:
            E2EMessageResult 校验结果
        """
        arb_id = msg_info.arbitration_id
        logger.info(
            f"[E2EChecker] 校验 {msg_info.name} (0x{arb_id:03X}), "
            f"帧数: {len(blf_stats.raw_messages)}"
        )

        # 获取 E2E Profile
        profile = self._resolve_profile(msg_info)

        # 查找 Counter 和 CRC 信号定义
        counter_sig = self._find_signal(msg_info, msg_info.e2e_counter_signal, "Counter")
        crc_sig = self._find_signal(msg_info, msg_info.e2e_crc_signal, "CRC")

        result = E2EMessageResult(
            channel=msg_info.channel,
            message_name=msg_info.name,
            arbitration_id=arb_id,
            profile_name=profile.profile_name if profile else "Unknown",
            total_frames=len(blf_stats.raw_messages),
            counter_signal_name=counter_sig.name if counter_sig else "",
            crc_signal_name=crc_sig.name if crc_sig else "",
        )

        # 按时间戳排序原始帧
        sorted_messages = sorted(blf_stats.raw_messages, key=lambda m: m.timestamp)

        # ── Counter 连续性检查 ──
        if counter_sig and profile:
            result.counter_errors = self._check_counter(
                sorted_messages, counter_sig, profile, msg_info.name
            )
            result.counter_error_count = len(result.counter_errors)

        # ── CRC 校验 ──
        if crc_sig and profile:
            result.crc_errors = self._check_crc(
                sorted_messages, crc_sig, profile, msg_info, arb_id
            )
            result.crc_error_count = len(result.crc_errors)

        # 判断整体健康状态
        result.is_healthy = (
            result.counter_error_count == 0 and result.crc_error_count == 0
        )

        status = "✓ 正常" if result.is_healthy else "⚠ 异常"
        logger.info(
            f"[E2EChecker] {msg_info.name} 结果: {status} "
            f"(Counter 错误: {result.counter_error_count}, "
            f"CRC 错误: {result.crc_error_count})"
        )

        return result

    def _resolve_profile(self, msg_info: MessageInfo) -> Optional[E2EProfileBase]:
        """确定使用哪个 E2E Profile"""
        if msg_info.e2e_profile:
            profile = get_e2e_profile(msg_info.e2e_profile)
            if profile:
                logger.debug(
                    f"[E2EChecker] {msg_info.name}: 使用 Matrix 指定的 "
                    f"{profile.profile_name}"
                )
                return profile
            logger.warning(
                f"[E2EChecker] {msg_info.name}: Matrix 指定的 Profile "
                f"'{msg_info.e2e_profile}' 不支持，回退到默认"
            )

        profile = get_e2e_profile(self._default_profile_name)
        if profile:
            logger.debug(
                f"[E2EChecker] {msg_info.name}: 使用默认 {profile.profile_name}"
            )
        else:
            profile = get_default_profile()
            logger.debug(
                f"[E2EChecker] {msg_info.name}: 使用兜底 {profile.profile_name}"
            )
        return profile

    @staticmethod
    def _find_signal(
        msg_info: MessageInfo,
        signal_name: Optional[str],
        signal_type: str,
    ) -> Optional[SignalInfo]:
        """在报文信号列表中查找指定名称的信号"""
        if not signal_name:
            logger.debug(
                f"[E2EChecker] {msg_info.name}: 未配置 {signal_type} 信号名"
            )
            return None

        for sig in msg_info.signals:
            if sig.name == signal_name:
                logger.debug(
                    f"[E2EChecker] {msg_info.name}: 找到 {signal_type} 信号 "
                    f"'{sig.name}' (start_bit={sig.start_bit}, "
                    f"bit_length={sig.bit_length})"
                )
                return sig

        logger.warning(
            f"[E2EChecker] {msg_info.name}: {signal_type} 信号 "
            f"'{signal_name}' 在信号列表中未找到"
        )
        return None

    def _check_counter(
        self,
        messages: List[can.Message],
        counter_sig: SignalInfo,
        profile: E2EProfileBase,
        msg_name: str,
    ) -> List[CounterError]:
        """
        检查 Counter 连续性。

        Args:
            messages: 按时间排序的原始 CAN 帧列表
            counter_sig: Counter 信号定义
            profile: E2E Profile 实例
            msg_name: 报文名称（用于日志）

        Returns:
            Counter 错误列表
        """
        errors: List[CounterError] = []
        prev_counter: Optional[int] = None

        logger.debug(
            f"[E2EChecker] {msg_name}: 开始 Counter 连续性检查, "
            f"Counter 范围: 0~{profile.counter_max}, "
            f"帧数: {len(messages)}"
        )

        for idx, msg in enumerate(messages):
            curr_counter = self._signal_extractor.extract_signal_value(
                msg.data,
                counter_sig.start_bit,
                counter_sig.bit_length,
            )

            if prev_counter is not None:
                if not profile.is_counter_valid(prev_counter, curr_counter):
                    expected = (prev_counter + 1) % (profile.counter_max + 1)
                    # 判断错误类型
                    if curr_counter == prev_counter:
                        error_type = "repeat"
                    else:
                        error_type = "jump"

                    error = CounterError(
                        timestamp=msg.timestamp,
                        frame_index=idx,
                        expected_value=expected,
                        actual_value=curr_counter,
                        error_type=error_type,
                    )
                    errors.append(error)

                    logger.debug(
                        f"[E2EChecker] {msg_name}: Counter {error_type} "
                        f"@ {msg.timestamp:.6f}s (frame #{idx}): "
                        f"expected={expected}, actual={curr_counter}"
                    )

            prev_counter = curr_counter

        if errors:
            logger.warning(
                f"[E2EChecker] {msg_name}: Counter 检查完成, "
                f"发现 {len(errors)} 个错误 "
                f"(jump={sum(1 for e in errors if e.error_type == 'jump')}, "
                f"repeat={sum(1 for e in errors if e.error_type == 'repeat')})"
            )
        else:
            logger.info(
                f"[E2EChecker] {msg_name}: Counter 连续性检查通过 ✓"
            )

        return errors

    def _check_crc(
        self,
        messages: List[can.Message],
        crc_sig: SignalInfo,
        profile: E2EProfileBase,
        msg_info: MessageInfo,
        data_id: int,
    ) -> List[CrcError]:
        """
        检查 CRC 校验。

        Args:
            messages: 按时间排序的原始 CAN 帧列表
            crc_sig: CRC 信号定义
            profile: E2E Profile 实例
            msg_info: 报文定义
            data_id: 用于 CRC 计算的 DataID (通常 = 报文 ID)

        Returns:
            CRC 错误列表
        """
        errors: List[CrcError] = []

        # CRC 字节位置 (假设 CRC 信号按字节对齐)
        crc_byte_pos = crc_sig.start_bit // 8

        logger.debug(
            f"[E2EChecker] {msg_info.name}: 开始 CRC 校验, "
            f"CRC byte_pos={crc_byte_pos}, "
            f"Profile={profile.profile_name}, "
            f"DataID=0x{data_id:04X}, "
            f"帧数: {len(messages)}"
        )

        for idx, msg in enumerate(messages):
            # 提取帧中实际的 CRC 值
            actual_crc = self._signal_extractor.extract_signal_value(
                msg.data,
                crc_sig.start_bit,
                crc_sig.bit_length,
            )

            # 计算期望的 CRC 值
            try:
                expected_crc = profile.compute_crc(
                    data=bytes(msg.data),
                    data_id=data_id,
                    crc_byte_pos=crc_byte_pos,
                )
            except Exception as e:
                logger.error(
                    f"[E2EChecker] {msg_info.name}: CRC 计算异常 "
                    f"@ frame #{idx}: {e}"
                )
                continue

            if actual_crc != expected_crc:
                error = CrcError(
                    timestamp=msg.timestamp,
                    frame_index=idx,
                    expected_crc=expected_crc,
                    actual_crc=actual_crc,
                )
                errors.append(error)

                # 只对前 10 条错误打 DEBUG 日志，防止洪泛
                if len(errors) <= 10:
                    logger.debug(
                        f"[E2EChecker] {msg_info.name}: CRC 不匹配 "
                        f"@ {msg.timestamp:.6f}s (frame #{idx}): "
                        f"expected=0x{expected_crc:02X}, "
                        f"actual=0x{actual_crc:02X}"
                    )

        if errors:
            logger.warning(
                f"[E2EChecker] {msg_info.name}: CRC 校验完成, "
                f"发现 {len(errors)} 个错误 "
                f"(占比 {len(errors) / len(messages) * 100:.1f}%)"
            )
        else:
            logger.info(
                f"[E2EChecker] {msg_info.name}: CRC 校验通过 ✓"
            )

        return errors
