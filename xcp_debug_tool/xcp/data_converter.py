import struct
from logger.log_manager import logger

class DataConverter:
    """
    负责将从 ECU 读回来的 raw bytes (大端模式) 转换为上位机看得懂的 Python 数据。
    ECU 配置为: 大端 (Big-Endian)
    """

import struct
from logger.log_manager import logger

class DataConverter:
    """
    负责将从 ECU 读回来的 raw bytes 转换为上位机看得懂的格式。
    S32G399 Cortex-M 为小端架构 (Little-Endian)。
    """
    
    @classmethod
    def parse_raw_value(cls, raw_bytes: bytes, size: int, type_info: dict) -> tuple:
        """
        解析底层读回的 raw_bytes 为具体数值体系。
        返回 (解析后的数值列表/字典/字符串, hex字符串显示形式)
        """
        if not raw_bytes or len(raw_bytes) < size:
             return None, "数据不完整"

        data_to_parse = raw_bytes[:size]
        hex_str = data_to_parse.hex().upper()
        hex_str_fmt = ' '.join(hex_str[i:i+2] for i in range(0, len(hex_str), 2))
        
        parsed_val = cls._parse_type(data_to_parse, type_info)
        return parsed_val, hex_str_fmt

    @classmethod
    def _parse_type(cls, data: bytes, type_info: dict):
        if not type_info or type_info.get('class') == 'unknown':
            return cls._parse_generic(data)
            
        t_class = type_info.get('class')
        t_name = type_info.get('name', '').lower()
        size = type_info.get('size', len(data))

        if t_class in ('typedef', 'qualifier'):
            underlying = type_info.get('underlying')
            if underlying:
                return cls._parse_type(data, underlying)
            return cls._parse_generic(data)

        if t_class in ('base_type', 'pointer_type', 'enumeration_type'):
            if 'float' in t_name or 'real' in t_name:
                if len(data) >= 4 and size == 4:
                    return round(struct.unpack('<f', data[:4])[0], 4)
                elif len(data) >= 8 and size == 8:
                    return round(struct.unpack('<d', data[:8])[0], 6)
                return "UnkFloat"
                
            is_signed = False
            if 'unsigned' not in t_name and ('int' in t_name or 'char' in t_name):
                 is_signed = True
            if t_class in ('pointer_type', 'enumeration_type'):
                 is_signed = False
                 
            try:
                # 按照小端转换
                return int.from_bytes(data[:size], byteorder='little', signed=is_signed)
            except Exception as e:
                return f"Err:{e}"

        if cls.is_struct_type(type_info):
            result = []
            members = type_info.get('members', [])
            for m in members:
                m_offset = m.get('offset', 0)
                m_type = m.get('type_info', {})
                if not m_type:
                    continue
                m_size = m_type.get('size', 0)
                if m_size == 0 or m_offset + m_size > len(data):
                    continue
                
                m_data = data[m_offset : m_offset + m_size]
                m_val = cls._parse_type(m_data, m_type)
                result.append(f"{m.get('name')}: {m_val}")
            
            return "{\n  " + ",\n  ".join(result) + "\n}"

        if t_class == 'array_type':
            elem_type = type_info.get('element_type')
            if not elem_type or elem_type.get('size', 0) == 0:
                return f"Array [{size} bytes]"
                
            e_size = elem_type['size']
            count = min(size // e_size, 10) # 最多解析前10个防止界面卡死
            
            arr_vals = []
            for i in range(count):
                offset = i * e_size
                if offset + e_size > len(data): break
                e_data = data[offset : offset+e_size]
                arr_vals.append(str(cls._parse_type(e_data, elem_type)))
                
            connector = ",\n  " if len(arr_vals) > 1 else ", "
            rep = "[\n  " + connector.join(arr_vals)
            if size // e_size > 10:
                rep += ",\n  ..."
            rep += "\n]"
            return rep

        return cls._parse_generic(data)

    @classmethod
    def is_struct_type(cls, type_info: dict) -> bool:
        """判断是否为结构体类型（考虑 typedef 或 qualifier 嵌套）"""
        if not type_info: return False
        t_class = type_info.get('class')
        if t_class == 'structure_type':
            return True
        if t_class in ('typedef', 'qualifier'):
            return cls.is_struct_type(type_info.get('underlying', {}))
        return False

    @classmethod
    def _parse_generic(cls, data: bytes):
        if len(data) <= 8:
            return int.from_bytes(data, byteorder='little')
        return f"Raw[{len(data)}B]"
