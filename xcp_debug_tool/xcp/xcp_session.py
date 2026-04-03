from xcp.xcp_protocol import XcpProtocol
from canoe.canfd_transport import CanFdTransport
from logger.log_manager import logger

class XcpSession:
    """
    管理与 ECU 之间的 XCP 通信生命周期 (Connect, Query)。
    
    大变量（>4 字节）通过多次 SHORT_UPLOAD 分块读取，
    确保每次 ECU 响应都在 DLC=8 以内（已验证的可靠通道）。
    """
    # 每次 SHORT_UPLOAD 请求的最大数据字节数。
    # ECU 响应格式: FF [data...] ，为保证响应 <= 8 字节，data 最多 7 字节。
    # 保守使用 4 字节，兼容性最好。
    MAX_CHUNK_SIZE = 4

    def __init__(self, transport: CanFdTransport):
        self.transport = transport
        self.is_connected = False
        
    def connect(self):
        """
        发起 XCP CONNECT 命令。
        发送: FF 00
        成功判据: 响应首字节 == 0xFF
        """
        logger.info("[XcpSession] -> XCP CONNECT (发送: FF 00)")
        req = XcpProtocol.build_connect()
        res = self.transport.send_xcp_request(req)
        
        if res and len(res) > 0:
            if res[0] == 0xFF:
                self.is_connected = True
                logger.info(f"[XcpSession] <- CONNECT 成功！ECU 响应: {res.hex()}")
                return True
            else:
                logger.error(f"[XcpSession] <- CONNECT 失败，ECU 响应: {res.hex()} (首字节非 0xFF)")
                return False
        else:
            logger.error("[XcpSession] <- CONNECT 失败，未收到 ECU 响应 (超时)")
            return False

    def disconnect(self):
        """发起 XCP DISCONNECT 命令"""
        if not self.is_connected:
            return
        logger.info("[XcpSession] -> XCP DISCONNECT")
        req = XcpProtocol.build_disconnect()
        self.transport.send_xcp_request(req)
        self.is_connected = False
        logger.info("[XcpSession] 断开连接成功。")

    def read_memory(self, address: int, size: int):
        """
        通过 SHORT_UPLOAD 读取 ECU 内存。
        
        如果 size > MAX_CHUNK_SIZE，自动拆分为多次请求，
        每次请求最多读 MAX_CHUNK_SIZE 字节，然后拼接。
        
        协议:
          发送: F4 [Size] 00 00 [Addr_LE]
          响应: FF [data...]  (首字节 PID，后续为数据)
        """
        if not self.is_connected:
            logger.warning("[XcpSession] XCP 尚未 Connect!")
            return None

        all_data = b''
        remaining = size
        current_addr = address

        logger.info(f"[XcpSession] 开始读取: Addr={hex(address)} TotalSize={size}, 分块大小={self.MAX_CHUNK_SIZE}")

        while remaining > 0:
            chunk_size = min(remaining, self.MAX_CHUNK_SIZE)
            req = XcpProtocol.build_short_upload(current_addr, chunk_size)

            logger.debug(f"[XcpSession]   -> SHORT_UPLOAD Addr={hex(current_addr)} Size={chunk_size} 报文: {req.hex()}")

            res = self.transport.send_xcp_request(req)

            if res and len(res) > 0:
                is_success, payload = XcpProtocol.parse_response(res)
                if is_success and len(payload) >= chunk_size:
                    chunk_data = payload[:chunk_size]
                    all_data += chunk_data
                    logger.debug(f"[XcpSession]   <- 成功获取 {chunk_size} 字节: {chunk_data.hex()}")
                    current_addr += chunk_size
                    remaining -= chunk_size
                else:
                    logger.error(f"[XcpSession]   <- SHORT_UPLOAD 失败或数据不足, 响应: {res.hex()}")
                    return None
            else:
                logger.error(f"[XcpSession]   <- SHORT_UPLOAD 超时, Addr={hex(current_addr)}")
                return None

        logger.info(f"[XcpSession] 读取完成: {len(all_data)} 字节 -> {all_data.hex()}")
        return all_data
