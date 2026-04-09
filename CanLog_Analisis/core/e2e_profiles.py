"""
AUTOSAR E2E Profile 实现模块 (E2E Profiles)
提供各 E2E Profile 的 CRC 计算算法。

支持的 Profile:
  - Profile 1  (CRC-8/SAE-J1850)
  - Profile 2  (CRC-8/SAE-J1850, 类似 P1 但 Counter 范围不同)
  - Profile 11 (CRC-8)

设计原则:
  - 使用抽象基类，便于后续扩展新的 Profile
  - 每个 Profile 封装独立的 CRC 计算 + Counter 范围定义
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from logger.log_manager import logger


# ─────────────────────────────────────────────────────────────
# CRC 算术表（预计算）
# ─────────────────────────────────────────────────────────────

def _build_crc8_sae_j1850_table() -> List[int]:
    """
    构建 CRC-8/SAE-J1850 查找表。
    多项式: 0x1D, 初始值: 0xFF, 最终异或: 0xFF
    """
    poly = 0x1D
    table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ poly) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
        table.append(crc)
    return table


def _build_crc8_table() -> List[int]:
    """
    构建标准 CRC-8 查找表。
    多项式: 0x07, 初始值: 0x00, 最终异或: 0x00
    (某些 E2E Profile 11 变种使用)
    """
    poly = 0x07
    table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ poly) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
        table.append(crc)
    return table


# 预计算 CRC 查找表（模块级别，只生成一次）
CRC8_SAE_J1850_TABLE = _build_crc8_sae_j1850_table()
CRC8_TABLE = _build_crc8_table()

logger.debug("[E2EProfiles] CRC 查找表已初始化")


# ─────────────────────────────────────────────────────────────
# CRC 计算函数
# ─────────────────────────────────────────────────────────────

def crc8_sae_j1850(data: bytes, init: int = 0xFF, xor_out: int = 0xFF) -> int:
    """
    CRC-8/SAE-J1850 计算。
    这是 AUTOSAR E2E Profile 1 和 Profile 2 常用的 CRC 算法。

    Args:
        data: 输入字节序列
        init: 初始 CRC 值 (默认 0xFF)
        xor_out: 最终异或值 (默认 0xFF)

    Returns:
        8-bit CRC 结果
    """
    crc = init
    for byte in data:
        crc = CRC8_SAE_J1850_TABLE[(crc ^ byte) & 0xFF]
    return crc ^ xor_out


def crc8_standard(data: bytes, init: int = 0x00, xor_out: int = 0x00) -> int:
    """
    标准 CRC-8 计算。
    部分 Profile 11 实现使用此变种。

    Args:
        data: 输入字节序列
        init: 初始 CRC 值 (默认 0x00)
        xor_out: 最终异或值 (默认 0x00)

    Returns:
        8-bit CRC 结果
    """
    crc = init
    for byte in data:
        crc = CRC8_TABLE[(crc ^ byte) & 0xFF]
    return crc ^ xor_out


# ─────────────────────────────────────────────────────────────
# 抽象基类
# ─────────────────────────────────────────────────────────────

class E2EProfileBase(ABC):
    """
    E2E Profile 抽象基类。
    每个具体 Profile 需要实现:
      - counter_max: Counter 最大值（循环范围上限）
      - compute_crc: 根据 Profile 规则计算 CRC
    """

    @property
    @abstractmethod
    def profile_name(self) -> str:
        """Profile 名称标识"""
        ...

    @property
    @abstractmethod
    def counter_max(self) -> int:
        """Counter 最大值（含）。Counter 循环范围: 0 ~ counter_max"""
        ...

    @abstractmethod
    def compute_crc(
        self,
        data: bytes,
        data_id: int = 0,
        crc_byte_pos: int = 0,
    ) -> int:
        """
        根据 Profile 规则计算 CRC 值。

        Args:
            data: 完整的 CAN 数据帧 payload
            data_id: Data ID (部分 Profile 需要)
            crc_byte_pos: CRC 信号在 payload 中的字节位置

        Returns:
            计算出的 CRC 值
        """
        ...

    def is_counter_valid(self, prev_counter: int, curr_counter: int) -> bool:
        """
        检查 Counter 是否连续递增。
        prev_counter -> curr_counter 应满足:
          curr = (prev + 1) % (counter_max + 1)

        Args:
            prev_counter: 上一帧的 Counter 值
            curr_counter: 当前帧的 Counter 值

        Returns:
            True 表示连续，False 表示跳变/重复
        """
        expected = (prev_counter + 1) % (self.counter_max + 1)
        return curr_counter == expected


# ─────────────────────────────────────────────────────────────
# Profile 1 实现
# ─────────────────────────────────────────────────────────────

class E2EProfile1(E2EProfileBase):
    """
    AUTOSAR E2E Profile 1。

    特征:
      - Counter: 4-bit, 范围 0~14
      - CRC: CRC-8/SAE-J1850
      - CRC 计算范围: CRC 字节用 0x00 替代后的整个 payload + DataID
    """

    @property
    def profile_name(self) -> str:
        return "Profile1"

    @property
    def counter_max(self) -> int:
        return 14  # 0~14，值 15 通常保留

    def compute_crc(
        self,
        data: bytes,
        data_id: int = 0,
        crc_byte_pos: int = 0,
    ) -> int:
        """
        Profile 1 CRC 计算。
        1. 将 CRC 字节位置的值替换为 0x00
        2. 计算整个 payload 的 CRC-8/SAE-J1850
        3. 再追加 DataID 的低字节和高字节
        """
        # 构建 CRC 输入数据: CRC 位置置零
        data_list = list(data)
        if 0 <= crc_byte_pos < len(data_list):
            data_list[crc_byte_pos] = 0x00

        # CRC 输入 = payload(CRC置零) + DataID_Low + DataID_High
        crc_input = bytes(data_list) + bytes([data_id & 0xFF, (data_id >> 8) & 0xFF])

        result = crc8_sae_j1850(crc_input)
        return result


# ─────────────────────────────────────────────────────────────
# Profile 2 实现
# ─────────────────────────────────────────────────────────────

class E2EProfile2(E2EProfileBase):
    """
    AUTOSAR E2E Profile 2。

    特征:
      - Counter: 4-bit, 范围 0~15
      - CRC: CRC-8/SAE-J1850
      - CRC 计算范围: 与 Profile 1 类似，但 Counter 范围扩展到 15
    """

    @property
    def profile_name(self) -> str:
        return "Profile2"

    @property
    def counter_max(self) -> int:
        return 15  # 0~15

    def compute_crc(
        self,
        data: bytes,
        data_id: int = 0,
        crc_byte_pos: int = 0,
    ) -> int:
        """Profile 2 CRC 计算 (与 Profile 1 算法相同)"""
        data_list = list(data)
        if 0 <= crc_byte_pos < len(data_list):
            data_list[crc_byte_pos] = 0x00

        crc_input = bytes(data_list) + bytes([data_id & 0xFF, (data_id >> 8) & 0xFF])
        return crc8_sae_j1850(crc_input)


# ─────────────────────────────────────────────────────────────
# Profile 11 实现
# ─────────────────────────────────────────────────────────────

class E2EProfile11(E2EProfileBase):
    """
    AUTOSAR E2E Profile 11。

    特征:
      - Counter: 4-bit, 范围 0~14
      - CRC: CRC-8 (Poly=0x1D, Init=0xFF, XorOut=0xFF，同 SAE-J1850)
      - CRC 计算范围: DataID (2 bytes) + payload(CRC 字节置零)
    """

    @property
    def profile_name(self) -> str:
        return "Profile11"

    @property
    def counter_max(self) -> int:
        return 14

    def compute_crc(
        self,
        data: bytes,
        data_id: int = 0,
        crc_byte_pos: int = 0,
    ) -> int:
        """
        Profile 11 CRC 计算。
        CRC 输入顺序: DataID_Low + DataID_High + payload(CRC 置零)
        """
        data_list = list(data)
        if 0 <= crc_byte_pos < len(data_list):
            data_list[crc_byte_pos] = 0x00

        crc_input = bytes([data_id & 0xFF, (data_id >> 8) & 0xFF]) + bytes(data_list)
        return crc8_sae_j1850(crc_input)


# ─────────────────────────────────────────────────────────────
# Profile 工厂
# ─────────────────────────────────────────────────────────────

# 已注册的 Profile 映射
_PROFILE_REGISTRY = {
    "profile1": E2EProfile1,
    "profile2": E2EProfile2,
    "profile11": E2EProfile11,
    # 别名
    "p1": E2EProfile1,
    "p2": E2EProfile2,
    "p11": E2EProfile11,
    "1": E2EProfile1,
    "2": E2EProfile2,
    "11": E2EProfile11,
}


def get_e2e_profile(profile_name: str) -> Optional[E2EProfileBase]:
    """
    根据 Profile 名称获取对应的实现实例。

    Args:
        profile_name: Profile 名称 (不区分大小写)，
                      如 "Profile1", "Profile2", "Profile11", "P1", "1"

    Returns:
        E2EProfileBase 实例，如果不支持则返回 None
    """
    key = profile_name.strip().lower().replace(" ", "").replace("_", "")
    cls = _PROFILE_REGISTRY.get(key)
    if cls:
        instance = cls()
        logger.debug(
            f"[E2EProfiles] 创建 Profile 实例: {instance.profile_name} "
            f"(Counter 范围: 0~{instance.counter_max})"
        )
        return instance

    logger.warning(f"[E2EProfiles] 不支持的 Profile: '{profile_name}'")
    return None


def get_default_profile() -> E2EProfileBase:
    """获取默认 Profile（Profile 1）"""
    return E2EProfile1()
