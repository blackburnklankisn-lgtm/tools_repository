from logger.log_manager import logger
from elf_parser.type_resolver import TypeResolver

class DwarfAnalyzer:
    def __init__(self, dwarf_info):
        self.dwarf_info = dwarf_info
        self.type_resolver = TypeResolver(dwarf_info)
        # 缓存找到的变量名 -> {address, type_info, size}
        self.variable_cache = {}
        # 是否已经完整扫描过一遍全局变量
        self.scanned = False

    def scan_all_global_variables(self):
        """扫描所有的 CU，提取全部全局变量的 DW_TAG_variable, 建立缓存"""
        if self.scanned:
            return
            
        logger.info("[DwarfAnalyzer] 开始全局字典预扫描 (大小写不敏感模式)...")
        count = 0
        for CU in self.dwarf_info.iter_CUs():
            # 记录地址大小 (4 为 32位, 8 为 64位)
            addr_size = CU.structs.address_size
            top_DIE = CU.get_top_DIE()
            for die in top_DIE.iter_children():
                if die.tag == 'DW_TAG_variable':
                    if 'DW_AT_name' in die.attributes and 'DW_AT_location' in die.attributes:
                        name = die.attributes['DW_AT_name'].value.decode('utf-8')
                        
                        # 提炼物理地址 (处理常用的 DW_OP_addr)
                        loc_attr = die.attributes['DW_AT_location']
                        address = None
                        
                        # location 属性可能是位置列表，也可能是直接的块 (DW_OP_addr ...)
                        if hasattr(loc_attr.value, '__iter__'):
                            loc_data = loc_attr.value
                            if len(loc_data) > 0 and loc_data[0] == 0x03:  # DW_OP_addr opcode
                                address = int.from_bytes(loc_data[1:1+addr_size], byteorder='little')
                                
                        if address is not None:
                            # 使用小写作为键以支持不区分大小写查询，同时保留原始名称供显示
                            self.variable_cache[name.lower()] = {
                                'original_name': name,
                                'die': die,
                                'address': address,
                                'type_info': None # 懒加载类型
                            }
                            count += 1
                            
        self.scanned = True
        logger.info(f"[DwarfAnalyzer] 预扫描完成，共索引了 {count} 个全局变量。")

    def find_variable(self, var_name: str) -> dict:
        """
        查找变量，支持基于 '.' 的结构体子成员解析。
        """
        parts = var_name.split('.')
        base_name_input = parts[0]
        base_name_lower = base_name_input.lower()
        
        if not self.scanned:
             self.scan_all_global_variables()

        if base_name_lower not in self.variable_cache:
            logger.warning(f"[DwarfAnalyzer] 未在 DWARF 中找到变量/根节点: {base_name_input}")
            return None

        var_entry = self.variable_cache[base_name_lower]
        
        # 懒加载根节点的类型系统解析
        if var_entry['type_info'] is None:
             if 'DW_AT_type' in var_entry['die'].attributes:
                 type_die = var_entry['die'].get_DIE_from_attribute('DW_AT_type')
                 var_entry['type_info'] = self.type_resolver.resolve_type(type_die)

        current_info = var_entry['type_info']
        current_address = var_entry['address']
        
        # 计算偏移量与嵌套类型
        for sub_name in parts[1:]:
            if not current_info or current_info.get('class') not in ('structure_type', 'union_type'):
                logger.error(f"[DwarfAnalyzer] {sub_name} 不是一个结构体或联合体。")
                return None
                
            found = False
            for member in current_info.get('members', []):
                if member['name'] == sub_name:
                    current_address += member['offset']
                    current_info = member['type_info']
                    found = True
                    break
                    
            if not found:
                logger.error(f"[DwarfAnalyzer] 在结构体中未找到成员: {sub_name}")
                return None

        return {
            'query_name': var_name,
            'address': current_address,
            'size': current_info['size'] if current_info else 0,
            'type_name': current_info['name'] if current_info else 'unknown',
            'type_info': current_info
        }
