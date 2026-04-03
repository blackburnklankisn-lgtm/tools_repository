import time
from logger.log_manager import logger

class CanFdTransport:
    """
    负责在 CANoe 中发送和接收 CANFD XCP 报文。
    
    v4.1 架构:
    - 发送: 通过 CAPL export 函数 XCP_SendCmd (不依赖返回值)
    - 接收: 通过 System Variables 读取响应数据 (@sysvar::XCP::RspB0~B7)
    - 抗竞态: SeqNo 机制，每次请求递增序列号，校验响应序列号匹配后才读取
    - 最大单次传输: 8 字节 (DLC=8)
    """
    SYSVAR_NS = "XCP"

    def __init__(self, canoe_manager):
        self.canoe_manager = canoe_manager
        self._seq_no = 0  # 请求序列号计数器

    def send_xcp_request(self, payload_bytes: bytes):
        """
        发送 XCP 请求并等待响应 (最多 8 字节)。
        使用 SeqNo 机制确保响应数据新鲜有效。
        """
        if not self.canoe_manager.is_running():
            logger.error("[CanFdTransport] CANoe Measurement 未启动。")
            return None

        send_func = self.canoe_manager.get_capl_function("XCP_SendCmd")
        if not send_func:
            logger.error("[CanFdTransport] 未找到 CAPL 函数 `XCP_SendCmd`。")
            return None

        padded = list(payload_bytes[:8]) + [0] * (8 - len(payload_bytes))
        data_len = min(len(payload_bytes), 8)

        # 递增序列号并写入系统变量 (Python 端管控)
        self._seq_no = (self._seq_no + 1) & 0xFFFF
        self.canoe_manager.write_sysvar(self.SYSVAR_NS, "ReqSeqNo", self._seq_no)
        # 主动复位 HasData，避免读到旧响应
        self.canoe_manager.write_sysvar(self.SYSVAR_NS, "HasData", 0)

        logger.debug(f"[CanFdTransport] 发送 {data_len} 字节 [Seq={self._seq_no}]: {[hex(b) for b in padded[:data_len]]}")

        try:
            send_func.Call(data_len, padded[0], padded[1], padded[2],
                           padded[3], padded[4], padded[5], padded[6], padded[7])
        except Exception as e:
            logger.error(f"[CanFdTransport] 调用 XCP_SendCmd 报错: {str(e)}")
            return None

        return self._wait_for_response()

    def _wait_for_response(self, timeout_ms=1000):
        """轮询系统变量 XCP::HasData，收到数据后校验 SeqNo 并读取 RspB0~B7。"""
        start_time = time.time() * 1000
        
        while (time.time() * 1000 - start_time) < timeout_ms:
            has_data = self.canoe_manager.read_sysvar(self.SYSVAR_NS, "HasData")

            if has_data is not None and int(has_data) == 1:
                # 校验序列号是否匹配
                rsp_seq = self.canoe_manager.read_sysvar(self.SYSVAR_NS, "RspSeqNo")
                rsp_seq = int(rsp_seq) if rsp_seq is not None else -1
                
                if rsp_seq != self._seq_no:
                    # 序列号不匹配，说明这是旧响应残留，继续等待
                    logger.debug(f"[CanFdTransport] SeqNo 不匹配 (期望={self._seq_no}, 收到={rsp_seq})，继续等待...")
                    time.sleep(0.005)
                    continue

                resp_len = self.canoe_manager.read_sysvar(self.SYSVAR_NS, "RspLen")
                resp_len = int(resp_len) if resp_len is not None else 8
                resp_len = min(max(resp_len, 1), 8)

                result = bytearray(resp_len)
                for i in range(resp_len):
                    val = self.canoe_manager.read_sysvar(self.SYSVAR_NS, f"RspB{i}")
                    result[i] = int(val) & 0xFF if val is not None else 0

                logger.info(f"[CanFdTransport] 收到 ECU 响应 ({resp_len} bytes) [Seq={rsp_seq}]: {result.hex()}")
                return bytes(result)

            time.sleep(0.010)

        logger.warning("[CanFdTransport] XCP 接收响应超时 (1000ms)。")
        return None
