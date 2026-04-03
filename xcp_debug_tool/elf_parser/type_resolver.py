from typing import Dict, Any

class TypeResolver:
    """
    负责解析 DWARF 的 DIE (Debugging Information Entry) 中的类型结构。
    特别是解析结构体、数组、联合体等复杂类型。
    """
    def __init__(self, dwarf_info):
        self.dwarf_info = dwarf_info
        # 缓存已经解析过的类型 {offset: type_info_dict}
        self.type_cache = {}

    def resolve_type(self, type_die) -> Dict[str, Any]:
        """
        递归解析给定的 DW_TAG_xxx_type DIE，返回类型的标准化字典描述。
        返回格式例如：
        {
            'name': 'uint32_t',
            'size': 4,
            'class': 'base_type',
            'members': [] # for struct/union
        }
        """
        if not type_die:
            return {'name': 'void', 'size': 0, 'class': 'base_type'}

        offset = type_die.offset
        if offset in self.type_cache:
            return self.type_cache[offset]
            
        # 防止递归死循环（例如指向自身的指针结构体）
        self.type_cache[offset] = {'name': 'incomplete_type', 'size': 0, 'class': 'pending'}

        tag = type_die.tag
        type_info = {
            'name': type_die.attributes['DW_AT_name'].value.decode('utf-8') if 'DW_AT_name' in type_die.attributes else '<anon>',
            'size': type_die.attributes.get('DW_AT_byte_size').value if 'DW_AT_byte_size' in type_die.attributes else 0,
            'class': 'unknown',
            'members': []
        }

        if tag == 'DW_TAG_base_type':
            type_info['class'] = 'base_type'
            
        elif tag in ('DW_TAG_typedef', 'DW_TAG_const_type', 'DW_TAG_volatile_type', 'DW_TAG_restrict_type'):
            type_info['class'] = 'typedef' if tag == 'DW_TAG_typedef' else 'qualifier'
            # 追溯底层的 type
            if 'DW_AT_type' in type_die.attributes:
                underlying_die = type_die.get_DIE_from_attribute('DW_AT_type')
                underlying_info = self.resolve_type(underlying_die)
                type_info['size'] = underlying_info['size']
                type_info['underlying'] = underlying_info
                # 继承成员信息以便穿透访问
                if 'members' in underlying_info:
                    type_info['members'] = underlying_info['members']
            else:
                # void* 或类似的基础类型指针的底层可能是空
                type_info['size'] = 0
                
        elif tag in ('DW_TAG_structure_type', 'DW_TAG_union_type'):
            type_info['class'] = 'structure_type' if tag == 'DW_TAG_structure_type' else 'union_type'
            # 解析结构体成员 (DW_TAG_member)
            members = []
            for child in type_die.iter_children():
                if child.tag == 'DW_TAG_member':
                    member_name = child.attributes['DW_AT_name'].value.decode('utf-8') if 'DW_AT_name' in child.attributes else '<anon>'
                    
                    # 提取相对 offset
                    member_offset = 0
                    if 'DW_AT_data_member_location' in child.attributes:
                        loc_attr = child.attributes['DW_AT_data_member_location']
                        if loc_attr.form == 'DW_FORM_data1' or loc_attr.form.startswith('DW_FORM_data'):
                             member_offset = loc_attr.value
                        elif hasattr(loc_attr.value, '__iter__'):
                             # 简单支持 block 形式的常数偏移 (常见为 DW_OP_plus_uconst)
                             if len(loc_attr.value) > 1 and loc_attr.value[0] == 0x23: # DW_OP_plus_uconst
                                 # 简化处理，严格应解析 LEB128
                                 member_offset = loc_attr.value[1] 

                    # 提取成员的 type
                    member_type_info = None
                    if 'DW_AT_type' in child.attributes:
                        mem_type_die = child.get_DIE_from_attribute('DW_AT_type')
                        member_type_info = self.resolve_type(mem_type_die)
                        
                    members.append({
                        'name': member_name,
                        'offset': member_offset,
                        'type_info': member_type_info
                    })
            type_info['members'] = members
            
        elif tag == 'DW_TAG_array_type':
            type_info['class'] = 'array_type'
            # 元素类型
            element_type_info = None
            if 'DW_AT_type' in type_die.attributes:
                elem_die = type_die.get_DIE_from_attribute('DW_AT_type')
                element_type_info = self.resolve_type(elem_die)
            type_info['element_type'] = element_type_info
            
            # 如果没有直接给 byte_size，通过 subrange 计算
            if type_info['size'] == 0 and element_type_info:
                total_count = 1
                has_subrange = False
                for child in type_die.iter_children():
                    if child.tag == 'DW_TAG_subrange_type':
                        has_subrange = True
                        if 'DW_AT_upper_bound' in child.attributes:
                            ub = child.attributes['DW_AT_upper_bound'].value
                            # upper_bound 通常是索引最大值，所以数量是 ub + 1
                            total_count *= (ub + 1)
                        elif 'DW_AT_count' in child.attributes:
                            total_count *= child.attributes['DW_AT_count'].value
                if has_subrange:
                    type_info['size'] = element_type_info['size'] * total_count
            
        elif tag == 'DW_TAG_pointer_type':
            type_info['class'] = 'pointer_type'
            type_info['size'] = type_info['size'] or 4 # 默认 32 位指针

        elif tag == 'DW_TAG_enumeration_type':
            type_info['class'] = 'enumeration_type'
            if type_info['size'] == 0:
                 type_info['size'] = 4 # 有时枚举不写大小，默认 4

        self.type_cache[offset] = type_info
        return type_info
