import struct

# XCP 协议常用宏与命令代码
XCP_CMD_CONNECT = 0xFF
XCP_CMD_DISCONNECT = 0xFE
XCP_CMD_SET_MTA = 0xF6
XCP_CMD_DOWNLOAD = 0xF0
XCP_CMD_SHORT_UPLOAD = 0xF4
XCP_CMD_UPLOAD = 0xF5

class XcpProtocol:
    """
    负责构建 XCP 协议层的 Request 报文 (Payload)
    """
    
    @staticmethod
    def build_connect(mode=0x00):
        """
        CONNECT: FF [Mode]
        """
        return struct.pack('<BB', XCP_CMD_CONNECT, mode)

    @staticmethod
    def build_disconnect():
        """
        DISCONNECT: FE
        """
        return struct.pack('<B', XCP_CMD_DISCONNECT)

    @staticmethod
    def build_short_upload(address, size, ext=0x00):
        """
        SHORT_UPLOAD: F4 [Size] [Reserved=0x00] [Extension=0x00] [Address 32-bit 小端]
        """
        return struct.pack('<BBBB', XCP_CMD_SHORT_UPLOAD, size, 0x00, ext) + struct.pack('<I', address)

    @staticmethod
    def build_set_mta(address, ext=0x00):
        """
        SET_MTA: F6 00 00 [Extension] [Address 32-bit 小端]
        """
        return struct.pack('<BBBB', XCP_CMD_SET_MTA, 0x00, 0x00, ext) + struct.pack('<I', address)

    @staticmethod
    def build_download(size, data_bytes):
        """
        DOWNLOAD: F0 [Size] [Data...]
        注意：单帧最多 6 字节数据 (对 DLC=8 的限制)
        """
        header = struct.pack('<BB', XCP_CMD_DOWNLOAD, size)
        return header + data_bytes[:size]

    @staticmethod
    def parse_response(response_bytes):
        """
        解析 XCP Response。
        首字节 FF 表示成功，FE 表示 ERR。
        返回 (is_success, payload_bytes)
        """
        if not response_bytes:
            return False, b''
            
        pid = response_bytes[0]
        if pid == 0xFF:
             return True, response_bytes[1:]
        elif pid == 0xFE:
             return False, response_bytes[1:]
        else:
             return True, response_bytes
