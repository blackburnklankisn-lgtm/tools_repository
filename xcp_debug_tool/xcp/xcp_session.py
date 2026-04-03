import time
from xcp.xcp_protocol import XcpProtocol
from canoe.canfd_transport import CanFdTransport
from logger.log_manager import logger

class XcpSession:
    """
    管理与 ECU 之间的 XCP 通信生命周期 (Connect, Query)。
    
    大变量（>4 字节）通过多次 SHORT_UPLOAD 分块读取，
    确保每次 ECU 响应都在 DLC=8 以内（已验证的可靠通道）。
    
    v4.1: 增加 chunk 级重试机制和 chunk 间微延迟，提升多变量连续查询稳定性。
    """
    # 每次 SHORT_UPLOAD 请求的最大数据字节数
    MAX_CHUNK_SIZE = 4
    # 单个 chunk 最大重试次数
    MAX_RETRY = 3
    # chunk 间微延迟 (秒)，降低竞态概率
    INTER_CHUNK_DELAY = 0.005

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
        try:
            req = XcpProtocol.build_connect()
            res = self.transport.send_xcp_request(req)
            
            if res and len(res) > 0 and res[0] == 0xFF:
                self.is_connected = True
                logger.info(f"[XcpSession] <- CONNECT 成功！ECU 响应: {res.hex()}")
                return True
        except Exception as e:
            logger.error(f"[XcpSession] CONNECT 指令执行异常: {e}")
            
        self.is_connected = False
        logger.warning("[XcpSession] XCP CONNECT 失败！")
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
        
        新增: 单个 chunk 失败自动重试，chunk 间增加微延迟。
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
            chunk_data = self._read_chunk_with_retry(current_addr, chunk_size)
            
            if chunk_data is None:
                logger.error(f"[XcpSession] 分块读取失败 (重试耗尽): Addr={hex(current_addr)}, 已读取 {len(all_data)}/{size} 字节")
                self.is_connected = False # 标记连接可能已断开
                return None
            
            all_data += chunk_data
            current_addr += chunk_size
            remaining -= chunk_size
            
            # chunk 间微延迟，降低竞态概率
            if remaining > 0:
                time.sleep(self.INTER_CHUNK_DELAY)

        logger.info(f"[XcpSession] 读取完成: {len(all_data)} 字节 -> {all_data.hex()}")
        return all_data

    def write_memory(self, address: int, data_bytes: bytes):
        """
        通过 SET_MTA + DOWNLOAD 写入 ECU 内存。
        
        由于 DLC=8 的限制，每个 DOWNLOAD 最多携带 6 字节数据。
        本函数自动分块并执行重试。
        """
        if not self.is_connected:
            logger.warning("[XcpSession] XCP 尚未 Connect!")
            return False

        size = len(data_bytes)
        remaining = size
        current_addr = address
        offset = 0

        logger.info(f"[XcpSession] 开始写入: Addr={hex(address)} TotalSize={size}, 数据={data_bytes.hex()}")

        while remaining > 0:
            # DOWNLOAD 每次最多 6 字节 (1B CMD + 1B Size + 6B Data = 8B)
            chunk_size = min(remaining, 6)
            chunk_data = data_bytes[offset:offset+chunk_size]
            
            success = self._write_chunk_with_retry(current_addr, chunk_size, chunk_data)
            if not success:
                logger.error(f"[XcpSession] 分块写入失败 (重试耗尽): Addr={hex(current_addr)}")
                self.is_connected = False
                return False
            
            current_addr += chunk_size
            offset += chunk_size
            remaining -= chunk_size
            
            if remaining > 0:
                time.sleep(self.INTER_CHUNK_DELAY)

        logger.info(f"[XcpSession] 写入完成: {size} 字节。")
        return True

    def _write_chunk_with_retry(self, addr: int, chunk_size: int, data_bytes: bytes):
        """
        带重试的单 chunk 写入 (SET_MTA + DOWNLOAD)。
        """
        for attempt in range(1, self.MAX_RETRY + 1):
            try:
                # 1. SET_MTA
                set_mta_req = XcpProtocol.build_set_mta(addr)
                res_mta = self.transport.send_xcp_request(set_mta_req)
                if not (res_mta and res_mta[0] == 0xFF):
                    logger.warning(f"[XcpSession]   SET_MTA 失败: Addr={hex(addr)} (尝试 {attempt})")
                    time.sleep(0.010)
                    continue

                # 2. DOWNLOAD
                download_req = XcpProtocol.build_download(chunk_size, data_bytes)
                res_down = self.transport.send_xcp_request(download_req)
                
                if res_down and res_down[0] == 0xFF:
                    logger.debug(f"[XcpSession]   <- 块写入成功: Addr={hex(addr)} Size={chunk_size}")
                    return True
                else:
                    logger.warning(f"[XcpSession]   DOWNLOAD 失败: Addr={hex(addr)} (尝试 {attempt})")
            except Exception as e:
                logger.error(f"[XcpSession]   写入异常 (尝试 {attempt}): {e}")
            
            time.sleep(0.020) # 失败后微等待
            
        return False

    def _read_chunk_with_retry(self, addr: int, chunk_size: int):
        """
        带重试的单 chunk 读取。
        失败时自动重试，最多 MAX_RETRY 次。
        """
        for attempt in range(1, self.MAX_RETRY + 1):
            req = XcpProtocol.build_short_upload(addr, chunk_size)

            if attempt > 1:
                logger.warning(f"[XcpSession]   重试 #{attempt}: Addr={hex(addr)} Size={chunk_size}")
                time.sleep(0.020)  # 重试前等待 20ms，让通道恢复

            logger.debug(f"[XcpSession]   -> SHORT_UPLOAD Addr={hex(addr)} Size={chunk_size} 报文: {req.hex()}")
            res = self.transport.send_xcp_request(req)

            if res and len(res) > 0:
                is_success, payload = XcpProtocol.parse_response(res)
                if is_success and len(payload) >= chunk_size:
                    chunk_data = payload[:chunk_size]
                    logger.debug(f"[XcpSession]   <- 成功获取 {chunk_size} 字节: {chunk_data.hex()}")
                    return chunk_data
                else:
                    logger.warning(f"[XcpSession]   <- 响应异常: 期望 {chunk_size} 字节 payload, 实际 {len(payload)} 字节, 原始: {res.hex()}")
            else:
                logger.warning(f"[XcpSession]   <- SHORT_UPLOAD 超时: Addr={hex(addr)} (第 {attempt} 次)")

        return None
