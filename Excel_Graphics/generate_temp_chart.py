"""
汽车座椅加热标定数据温度曲线生成工具
针对 Applent Temperature Logger 采集的数据 (CSV格式) 生成包含专业温度曲线图及统计分析的 Excel (.xlsx) 表格。
"""

import os
import sys
import glob
import csv
import xlsxwriter

# 16通道高对比度工程配色 (Kelly's / Glasbey 经典对比色系)
CHANNEL_COLORS = [
    '#E6194B',  # CH1: 鲜红
    '#3CB44B',  # CH2: 翠绿
    '#FFE119',  # CH3: 亮黄
    '#4363D8',  # CH4: 皇家蓝
    '#F58231',  # CH5: 鲜橙
    '#911EB4',  # CH6: 紫色
    '#42D4F4',  # CH7: 青色
    '#F032E6',  # CH8: 洋红
    '#BFEF45',  # CH9: 黄绿
    '#FABEBE',  # CH10: 浅粉
    '#469990',  # CH11: 蓝绿/青灰
    '#9A6324',  # CH12: 棕褐
    '#800000',  # CH13: 栗红
    '#808000',  # CH14: 橄榄绿
    '#000075',  # CH15: 藏青
    '#808080',  # CH16: 中灰
]

def parse_csv_data(csv_path: str):
    """读取并解析 Applent 记录仪导出的 CSV 文件"""
    raw_rows = []
    for enc in ['utf-8', 'gbk', 'gb2312', 'gb18030']:
        try:
            with open(csv_path, 'r', encoding=enc) as f:
                raw_rows = list(csv.reader(f))
            print(f"[{os.path.basename(csv_path)}] 成功使用编码 {enc} 读取文件，共 {len(raw_rows)} 行。")
            break
        except Exception:
            continue
            
    if not raw_rows:
        raise ValueError(f"无法读取 CSV 文件: {csv_path}")
        
    header_row_idx = 9   # 第10行 (0-based: 9)
    data_start_idx = 10  # 第11行 (0-based: 10)
    
    if len(raw_rows) <= data_start_idx:
        raise ValueError(f"文件 {csv_path} 数据行不足，无法生成图表。")
        
    headers = raw_rows[header_row_idx]
    data_rows = raw_rows[data_start_idx:]
    total_data_points = len(data_rows)
    
    # 提取时间与通道统计
    times = [row[1] for row in data_rows if len(row) > 1]
    start_time = times[0] if times else "0:00:00"
    end_time = times[-1] if times else "0:00:00"
    
    # 查找 CH1 到 CH16 的列索引
    channel_stats = []
    for ch_idx in range(3, min(19, len(headers))):
        ch_name = headers[ch_idx] if headers[ch_idx] else f"CH{ch_idx-2}"
        vals = []
        for r in data_rows:
            if ch_idx < len(r) and r[ch_idx] != '':
                try:
                    vals.append(float(r[ch_idx]))
                except ValueError:
                    pass
        if vals:
            c_init = vals[0]
            c_min = min(vals)
            c_max = max(vals)
            c_final = vals[-1]
            c_rise = c_max - c_init
            channel_stats.append({
                'channel': ch_name,
                'col_idx': ch_idx,
                'init': c_init,
                'min': c_min,
                'max': c_max,
                'final': c_final,
                'rise': c_rise
            })
            
    return raw_rows, headers, data_rows, header_row_idx, data_start_idx, total_data_points, start_time, end_time, channel_stats

def convert_csv_to_excel_with_chart(csv_path: str, output_xlsx: str = None) -> str:
    if output_xlsx is None:
        output_xlsx = os.path.splitext(csv_path)[0] + '.xlsx'
        
    raw_rows, headers, data_rows, header_row_idx, data_start_idx, total_data_points, start_time, end_time, channel_stats = parse_csv_data(csv_path)
    
    file_display_name = os.path.basename(csv_path)
    print(f"正在创建 Excel 工作簿: {output_xlsx}")
    wb = xlsxwriter.Workbook(output_xlsx)
    
    # ---------------- 样式定义 ----------------
    fmt_title = wb.add_format({
        'font_name': '微软雅黑', 'font_size': 16, 'bold': True, 'color': '#1F497D',
        'align': 'left', 'valign': 'vcenter'
    })
    fmt_meta_key = wb.add_format({
        'font_name': '微软雅黑', 'font_size': 10, 'bold': True, 'bg_color': '#D9E1F2',
        'border': 1, 'align': 'center', 'valign': 'vcenter'
    })
    fmt_meta_val = wb.add_format({
        'font_name': '微软雅黑', 'font_size': 10, 'border': 1, 'align': 'center', 'valign': 'vcenter'
    })
    fmt_tbl_header = wb.add_format({
        'font_name': '微软雅黑', 'font_size': 10, 'bold': True, 'bg_color': '#2F5597', 'font_color': '#FFFFFF',
        'border': 1, 'align': 'center', 'valign': 'vcenter'
    })
    fmt_tbl_cell = wb.add_format({
        'font_name': '微软雅黑', 'font_size': 10, 'border': 1, 'align': 'center', 'valign': 'vcenter'
    })
    fmt_tbl_num = wb.add_format({
        'font_name': '微软雅黑', 'font_size': 10, 'border': 1, 'align': 'right', 'valign': 'vcenter', 'num_format': '0.00'
    })
    fmt_tbl_max = wb.add_format({
        'font_name': '微软雅黑', 'font_size': 10, 'bold': True, 'font_color': '#C00000',
        'border': 1, 'align': 'right', 'valign': 'vcenter', 'num_format': '0.00'
    })
    fmt_raw_header = wb.add_format({
        'font_name': '微软雅黑', 'font_size': 10, 'bold': True, 'bg_color': '#1F4E78', 'font_color': '#FFFFFF',
        'border': 1, 'align': 'center', 'valign': 'vcenter'
    })
    fmt_raw_num = wb.add_format({
        'font_name': '微软雅黑', 'font_size': 9, 'align': 'right', 'valign': 'vcenter', 'num_format': '0.00'
    })
    fmt_raw_text = wb.add_format({
        'font_name': '微软雅黑', 'font_size': 9, 'align': 'center', 'valign': 'vcenter'
    })
    
    last_row_excel = data_start_idx + total_data_points - 1
    step = 300 if total_data_points > 1000 else (60 if total_data_points > 200 else 10)
    
    # -------------------------------------------------------------
    # Sheet 1: 温度变化曲线 (主分析工作表)
    # -------------------------------------------------------------
    ws_chart = wb.add_worksheet('温度变化曲线')
    ws_chart.set_zoom(90)
    ws_chart.hide_gridlines(0)
    
    # 标题
    test_title_name = os.path.splitext(file_display_name)[0]
    ws_chart.merge_range('A1:O1', f'汽车座椅加热标定测试 - 温度变化分析曲线 ({test_title_name})', fmt_title)
    ws_chart.set_row(0, 32)
    
    # 基本测试信息卡片
    ws_chart.write('A3', '测试文件', fmt_meta_key)
    ws_chart.merge_range('B3:D3', file_display_name, fmt_meta_val)
    ws_chart.write('E3', '采样点数', fmt_meta_key)
    ws_chart.write('F3', total_data_points, fmt_meta_val)
    ws_chart.write('G3', '测试时长', fmt_meta_key)
    ws_chart.write('H3', end_time, fmt_meta_val)
    
    # 统计指标概览
    overall_min = min(s['min'] for s in channel_stats) if channel_stats else 0
    overall_max = max(s['max'] for s in channel_stats) if channel_stats else 0
    max_rise = max(s['rise'] for s in channel_stats) if channel_stats else 0
    
    ws_chart.write('A4', '初始最低温', fmt_meta_key)
    ws_chart.write('B4', f"{overall_min:.2f} ℃", fmt_meta_val)
    ws_chart.write('C4', '最高峰值温', fmt_meta_key)
    ws_chart.write('D4', f"{overall_max:.2f} ℃", fmt_meta_val)
    ws_chart.write('E4', '最大温升 ΔT', fmt_meta_key)
    ws_chart.write('F4', f"{max_rise:.2f} ℃", fmt_meta_val)
    ws_chart.write('G4', '采集通道', fmt_meta_key)
    ws_chart.write('H4', f"CH1 - CH{len(channel_stats)} ({len(channel_stats)}点)", fmt_meta_val)
    
    def create_configured_chart():
        chart = wb.add_chart({'type': 'line'})
        for i, s in enumerate(channel_stats):
            col_i = s['col_idx']
            color = CHANNEL_COLORS[i % len(CHANNEL_COLORS)]
            chart.add_series({
                'name':       ['原始数据', header_row_idx, col_i],
                'categories': ['原始数据', data_start_idx, 1, last_row_excel, 1],
                'values':     ['原始数据', data_start_idx, col_i, last_row_excel, col_i],
                'line':       {'color': color, 'width': 1.75},
                'marker':     {'type': 'none'},
            })
        chart.set_title({
            'name': f'座椅加热通道温度变化曲线 ({test_title_name})',
            'name_font': {'name': '微软雅黑', 'size': 13, 'bold': True, 'color': '#262626'},
        })
        chart.set_x_axis({
            'name': '时间 (ELAPSED TIME)',
            'name_font': {'name': '微软雅黑', 'size': 10, 'bold': True},
            'num_font':  {'name': 'Calibri', 'size': 9, 'rotation': -45},
            'interval_unit': step,
            'interval_tick': step,
            'label_position': 'low',  # 标签放置在底部，避免与负温数据交叉
            'major_gridlines': {'visible': True, 'line': {'color': '#F0F0F0', 'dash_type': 'dot'}},
        })
        chart.set_y_axis({
            'name': '温度 (℃)',
            'name_font': {'name': '微软雅黑', 'size': 10, 'bold': True},
            'num_font':  {'name': 'Calibri', 'size': 9},
            'crossing':  'min',       # X轴横轴线交叉在最低温刻度处，保持整体界面清爽
            'major_gridlines': {'visible': True, 'line': {'color': '#D9D9D9', 'dash_type': 'dash'}},
        })
        chart.set_legend({
            'position': 'right',
            'font': {'name': '微软雅黑', 'size': 9}
        })
        return chart

    chart_embed = create_configured_chart()
    chart_embed.set_size({'width': 1180, 'height': 580})
    ws_chart.insert_chart('A6', chart_embed)
    
    # 统计汇总表格 (第37行开始)
    stats_start_row = 36
    ws_chart.merge_range(stats_start_row, 0, stats_start_row, 6, '各通道温度特征统计分析 (CH1~CH16)', fmt_tbl_header)
    sub_headers = ['通道名称', '初始温度 (℃)', '最低温度 (℃)', '最高温度 (℃)', '结束温度 (℃)', '最大温升 ΔT (℃)', '平均升温速率 (℃/min)']
    for c_i, sh in enumerate(sub_headers):
        ws_chart.write(stats_start_row + 1, c_i, sh, fmt_tbl_header)
        
    duration_minutes = total_data_points / 60.0 if total_data_points > 0 else 1.0
    for r_i, s in enumerate(channel_stats):
        cur_r = stats_start_row + 2 + r_i
        rate = s['rise'] / duration_minutes
        ws_chart.write(cur_r, 0, s['channel'], fmt_tbl_cell)
        ws_chart.write(cur_r, 1, s['init'], fmt_tbl_num)
        ws_chart.write(cur_r, 2, s['min'], fmt_tbl_num)
        if abs(s['max'] - overall_max) < 0.01:
            ws_chart.write(cur_r, 3, s['max'], fmt_tbl_max)
        else:
            ws_chart.write(cur_r, 3, s['max'], fmt_tbl_num)
        ws_chart.write(cur_r, 4, s['final'], fmt_tbl_num)
        ws_chart.write(cur_r, 5, s['rise'], fmt_tbl_num)
        ws_chart.write(cur_r, 6, rate, fmt_tbl_num)
        
    ws_chart.set_column('A:A', 14)
    ws_chart.set_column('B:G', 16)
    ws_chart.set_column('H:H', 18)
    
    # -------------------------------------------------------------
    # Sheet 2: 全屏独立图表 (ChartSheet)
    # -------------------------------------------------------------
    cs = wb.add_chartsheet('全屏图表')
    chart_fullscreen = create_configured_chart()
    cs.set_chart(chart_fullscreen)
    
    # -------------------------------------------------------------
    # Sheet 3: 原始数据
    # -------------------------------------------------------------
    ws_raw = wb.add_worksheet('原始数据')
    ws_raw.freeze_panes(data_start_idx, 0)
    
    # 写入元数据
    for r_i in range(header_row_idx):
        if r_i < len(raw_rows):
            for c_i, val in enumerate(raw_rows[r_i]):
                ws_raw.write(r_i, c_i, val, fmt_raw_text)
                
    # 写入第 10 行表头
    for c_i, val in enumerate(headers):
        ws_raw.write(header_row_idx, c_i, val, fmt_raw_header)
        
    # 写入数据
    print(f"[{file_display_name}] 正在写入原始数据表格 ({len(data_rows)} 行)...")
    for r_i, row in enumerate(data_rows):
        excel_r = data_start_idx + r_i
        for c_i, val in enumerate(row):
            if c_i == 0:
                try:
                    ws_raw.write_number(excel_r, c_i, int(val), fmt_raw_text)
                except ValueError:
                    ws_raw.write(excel_r, c_i, val, fmt_raw_text)
            elif c_i in (1, 2):
                ws_raw.write(excel_r, c_i, val, fmt_raw_text)
            else:
                try:
                    num_val = float(val)
                    ws_raw.write_number(excel_r, c_i, num_val, fmt_raw_num)
                except ValueError:
                    ws_raw.write(excel_r, c_i, val, fmt_raw_text)
                    
    ws_raw.set_column(0, 0, 8)
    ws_raw.set_column(1, 1, 14)
    ws_raw.set_column(2, 2, 18)
    ws_raw.set_column(3, len(headers) - 1, 10)
    
    # 设置打开时默认激活第一张工作表
    ws_chart.activate()
    
    wb.close()
    print(f"[{file_display_name}] 成功生成 Excel 文件: {output_xlsx}")
    return output_xlsx

def main():
    import argparse
    parser = argparse.ArgumentParser(description="座椅加热温度曲线 Excel 生成工具")
    parser.add_argument('input', nargs='?', default=None, help="输入的 CSV 文件路径")
    parser.add_argument('--all', action='store_true', help="批量转换 996D_2 目录下所有温度 CSV 文件")
    args = parser.parse_args()
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, '996D_2')
    
    if args.all:
        temp_csvs = [f for f in glob.glob(os.path.join(data_dir, '*温度*.csv')) + glob.glob(os.path.join(data_dir, '*温度*.CSV'))]
        print(f"找到 {len(temp_csvs)} 个温度 CSV 文件，开始批量处理...")
        for csv_f in temp_csvs:
            convert_csv_to_excel_with_chart(csv_f)
        print("所有文件批量处理完成！")
    else:
        target = args.input
        if not target:
            target = os.path.join(data_dir, '996D主驾高档温度14801380.CSV')
        convert_csv_to_excel_with_chart(target)

if __name__ == '__main__':
    main()
