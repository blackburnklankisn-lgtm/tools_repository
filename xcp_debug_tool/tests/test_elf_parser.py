import os
import sys

# 将工程根目录加入 PATH 以便直接运行
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from elf_parser.elf_loader import ELFLoader
from elf_parser.dwarf_analyzer import DwarfAnalyzer

def test_elf_parsing(elf_path, var_to_test):
    print(f"=== 开始测试 {elf_path} ===")
    loader = ELFLoader()
    loader.load_file(elf_path)
    
    analyzer = DwarfAnalyzer(loader.dwarf_info)
    analyzer.scan_all_global_variables()
    
    result = analyzer.find_variable(var_to_test)
    if result:
        print(f"✅ 找到变量: {result['query_name']}")
        print(f"   地址: {hex(result['address'])}")
        print(f"   大小: {result['size']} bytes")
        print(f"   类型: {result['type_name']}")
        
        # 打印结构体深入信息
        if result['type_info'] and result['type_info'].get('class') in ('structure_type', 'union_type'):
            print(f"   成员:")
            for member in result['type_info'].get('members', []):
                mem_type = member['type_info']['name'] if member['type_info'] else 'unknown'
                print(f"      + {member['offset']:>4} | {member['name']:<20} | {mem_type}")
    else:
        print(f"❌ 未找到变量: {var_to_test}")

if __name__ == "__main__":
    print("本脚本用于脱离 UI 单独测试 DWARF 解析逻辑。")
    print("请修下面的路径进行本地测试。")
    # test_elf_parsing(r"C:\path\to\your.elf", "global_struct_var.field")
