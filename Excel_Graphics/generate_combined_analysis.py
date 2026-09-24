"""
汽车座椅加热标定 - 温度与电参数综合分析与图表生成工具
支持配对处理：
  - 中档: 996D主驾中档温度14801380.CSV + 996D主驾中档电流.csv
  - 低档: 996D主驾低档温度14801380.CSV + 996D主驾低档电流.csv
  - 高档: 996D主驾高档温度14801380.CSV + 996D主驾高档电流.csv

生成包含双XY轴图表（温度曲线 + 电压/电流/功率曲线）的 Excel 工作簿及双图联动交互式网页报表。
"""

import os
import sys
import glob
import json
import csv
import xlsxwriter

# 16通道工程配色
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
    '#469990',  # CH11: 蓝绿
    '#9A6324',  # CH12: 棕褐
    '#800000',  # CH13: 栗红
    '#808000',  # CH14: 橄榄绿
    '#000075',  # CH15: 藏青
    '#808080',  # CH16: 中灰
]

def read_csv_safe(file_path):
    for enc in ['utf-8', 'gbk', 'gb2312', 'gb18030']:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                return list(csv.reader(f))
        except Exception:
            continue
    raise ValueError(f"无法读取文件: {file_path}")

def process_combined_group(temp_csv: str, curr_csv: str, output_xlsx: str = None, output_html: str = None):
    group_name = os.path.basename(temp_csv).replace('.CSV', '').replace('.csv', '')
    data_dir = os.path.dirname(temp_csv)
    
    if output_xlsx is None:
        output_xlsx = os.path.join(data_dir, f"{group_name}.xlsx")
    if output_html is None:
        output_html = os.path.join(data_dir, f"{group_name}_交互图表.html")
        
    print(f"\n=======================================================")
    print(f"正在处理数据组: {group_name}")
    print(f"温度文件: {os.path.basename(temp_csv)}")
    print(f"电流文件: {os.path.basename(curr_csv)}")
    print(f"=======================================================")
    
    # 1. 读取温度数据
    r_temp = read_csv_safe(temp_csv)
    t_headers = r_temp[9]
    t_data = r_temp[10:]
    total_t_points = len(t_data)
    
    t_times = [r[1] for r in t_data if len(r) > 1]
    t_date_times = [r[2] for r in t_data if len(r) > 2]
    t_seqs = [int(r[0]) if r[0].isdigit() else i for i, r in enumerate(t_data)]
    
    # 解析 CH1 到 CH16
    t_channels = []
    t_stats = []
    for c_i in range(3, min(19, len(t_headers))):
        ch_name = t_headers[c_i] if t_headers[c_i] else f"CH{c_i-2}"
        vals = []
        for r in t_data:
            try:
                vals.append(round(float(r[c_i]), 2))
            except (ValueError, IndexError):
                vals.append(None)
        t_channels.append({'name': ch_name, 'col_idx': c_i, 'data': vals})
        
        valid_vals = [v for v in vals if v is not None]
        if valid_vals:
            t_stats.append({
                'name': ch_name,
                'init': valid_vals[0],
                'min': min(valid_vals),
                'max': max(valid_vals),
                'final': valid_vals[-1],
                'rise': round(max(valid_vals) - valid_vals[0], 2)
            })
            
    # 2. 读取电参数数据 (Id, Voltage, Current, Power, SaveTime)
    r_curr = read_csv_safe(curr_csv)
    c_headers = r_curr[0]
    c_data = r_curr[1:]
    total_c_points = len(c_data)
    
    c_seqs = []
    c_voltages = []
    c_currents = []
    c_powers = []
    c_times = []
    
    for r in c_data:
        if len(r) >= 4:
            try:
                seq = int(r[0])
                v = round(float(r[1]), 3)
                i = round(float(r[2]), 4)
                p = round(float(r[3]), 3)
                tm = r[4] if len(r) > 4 else ""
                c_seqs.append(seq)
                c_voltages.append(v)
                c_currents.append(i)
                c_powers.append(p)
                c_times.append(tm)
            except ValueError:
                continue
                
    # 计算电参数统计
    e_stats = {
        'v_min': min(c_voltages) if c_voltages else 0,
        'v_max': max(c_voltages) if c_voltages else 0,
        'v_avg': sum(c_voltages) / len(c_voltages) if c_voltages else 0,
        'i_min': min(c_currents) if c_currents else 0,
        'i_max': max(c_currents) if c_currents else 0,
        'i_avg': sum(c_currents) / len(c_currents) if c_currents else 0,
        'p_min': min(c_powers) if c_powers else 0,
        'p_max': max(c_powers) if c_powers else 0,
        'p_avg': sum(c_powers) / len(c_powers) if c_powers else 0,
    }
    
    # -------------------------------------------------------------------------
    # 生成 Excel 工作簿 (.xlsx)
    # -------------------------------------------------------------------------
    print(f"正在生成 Excel 文件: {output_xlsx}")
    wb = xlsxwriter.Workbook(output_xlsx)
    
    # 样式定义
    fmt_title = wb.add_format({
        'font_name': '微软雅黑', 'font_size': 15, 'bold': True, 'color': '#1F497D',
        'align': 'left', 'valign': 'vcenter'
    })
    fmt_sec_title = wb.add_format({
        'font_name': '微软雅黑', 'font_size': 11, 'bold': True, 'color': '#2F5597',
        'align': 'left', 'valign': 'vcenter', 'bottom': 2, 'bottom_color': '#2F5597'
    })
    fmt_meta_key = wb.add_format({
        'font_name': '微软雅黑', 'font_size': 9, 'bold': True, 'bg_color': '#D9E1F2',
        'border': 1, 'align': 'center', 'valign': 'vcenter'
    })
    fmt_meta_val = wb.add_format({
        'font_name': '微软雅黑', 'font_size': 9, 'border': 1, 'align': 'center', 'valign': 'vcenter'
    })
    fmt_tbl_header = wb.add_format({
        'font_name': '微软雅黑', 'font_size': 9, 'bold': True, 'bg_color': '#2F5597', 'font_color': '#FFFFFF',
        'border': 1, 'align': 'center', 'valign': 'vcenter'
    })
    fmt_tbl_cell = wb.add_format({
        'font_name': '微软雅黑', 'font_size': 9, 'border': 1, 'align': 'center', 'valign': 'vcenter'
    })
    fmt_tbl_num = wb.add_format({
        'font_name': '微软雅黑', 'font_size': 9, 'border': 1, 'align': 'right', 'valign': 'vcenter', 'num_format': '0.00'
    })
    fmt_tbl_max = wb.add_format({
        'font_name': '微软雅黑', 'font_size': 9, 'bold': True, 'font_color': '#C00000',
        'border': 1, 'align': 'right', 'valign': 'vcenter', 'num_format': '0.00'
    })
    fmt_raw_header = wb.add_format({
        'font_name': '微软雅黑', 'font_size': 9, 'bold': True, 'bg_color': '#1F4E78', 'font_color': '#FFFFFF',
        'border': 1, 'align': 'center', 'valign': 'vcenter'
    })
    fmt_raw_text = wb.add_format({
        'font_name': '微软雅黑', 'font_size': 9, 'align': 'center', 'valign': 'vcenter'
    })
    fmt_raw_num = wb.add_format({
        'font_name': '微软雅黑', 'font_size': 9, 'align': 'right', 'valign': 'vcenter', 'num_format': '0.00'
    })
    fmt_raw_num3 = wb.add_format({
        'font_name': '微软雅黑', 'font_size': 9, 'align': 'right', 'valign': 'vcenter', 'num_format': '0.000'
    })
    
    # ---------------- 写入 Sheet 1: 综合分析看板 ----------------
    ws_dash = wb.add_worksheet('温度与电参数综合看板')
    ws_dash.set_zoom(90)
    ws_dash.hide_gridlines(0)
    
    # 标题栏
    ws_dash.merge_range('A1:P1', f'汽车座椅加热标定 - 温度与电参数综合分析看板 ({group_name})', fmt_title)
    ws_dash.set_row(0, 30)
    
    # 测试概况信息卡片 (第 3、4 行)
    ws_dash.write('A3', '温度测试源', fmt_meta_key)
    ws_dash.merge_range('B3:D3', os.path.basename(temp_csv), fmt_meta_val)
    ws_dash.write('E3', '温度采样点', fmt_meta_key)
    ws_dash.write('F3', total_t_points, fmt_meta_val)
    ws_dash.write('G3', '试验时长', fmt_meta_key)
    ws_dash.write('H3', t_times[-1] if t_times else "", fmt_meta_val)
    ws_dash.write('I3', '峰值温度', fmt_meta_key)
    ws_dash.write('J3', f"{max(s['max'] for s in t_stats):.2f} ℃" if t_stats else "", fmt_meta_val)
    
    ws_dash.write('A4', '电流测试源', fmt_meta_key)
    ws_dash.merge_range('B4:D4', os.path.basename(curr_csv), fmt_meta_val)
    ws_dash.write('E4', '电参数点数', fmt_meta_key)
    ws_dash.write('F4', total_c_points, fmt_meta_val)
    ws_dash.write('G4', '平均电流', fmt_meta_key)
    ws_dash.write('H4', f"{e_stats['i_avg']:.2f} A", fmt_meta_val)
    ws_dash.write('I4', '平均功率', fmt_meta_key)
    ws_dash.write('J4', f"{e_stats['p_avg']:.2f} W", fmt_meta_val)
    
    # ---- 图表 1: 温度变化曲线 ----
    last_t_row = 10 + total_t_points - 1
    t_step = 300 if total_t_points > 1000 else (60 if total_t_points > 200 else 10)
    
    chart_temp = wb.add_chart({'type': 'line'})
    for i, ch in enumerate(t_channels):
        c_idx = ch['col_idx']
        color = CHANNEL_COLORS[i % len(CHANNEL_COLORS)]
        chart_temp.add_series({
            'name':       ['原始数据_温度', 9, c_idx],
            'categories': ['原始数据_温度', 10, 1, last_t_row, 1], # B列 时间
            'values':     ['原始数据_温度', 10, c_idx, last_t_row, c_idx],
            'line':       {'color': color, 'width': 1.6},
            'marker':     {'type': 'none'},
        })
    chart_temp.set_title({'name': f'图表 1: 汽车座椅各通道温度随时间变化曲线 ({group_name})', 'name_font': {'name': '微软雅黑', 'size': 11, 'bold': True}})
    chart_temp.set_x_axis({
        'name': '时间 (ELAPSED TIME)', 'interval_unit': t_step, 'interval_tick': t_step,
        'label_position': 'low', 'major_gridlines': {'visible': True, 'line': {'color': '#F0F0F0', 'dash_type': 'dot'}}
    })
    chart_temp.set_y_axis({
        'name': '温度 (℃)', 'crossing': 'min',
        'major_gridlines': {'visible': True, 'line': {'color': '#D9D9D9', 'dash_type': 'dash'}}
    })
    chart_temp.set_legend({'position': 'right', 'font': {'name': '微软雅黑', 'size': 9}})
    chart_temp.set_size({'width': 1180, 'height': 440})
    ws_dash.insert_chart('A6', chart_temp)
    
    # ---- 图表 2: 电压、电流、功率变化曲线 (双Y轴 XY图) ----
    last_c_row = total_c_points
    c_step = 300 if total_c_points > 1000 else (60 if total_c_points > 200 else 10)
    
    chart_elec = wb.add_chart({'type': 'line'})
    # 电压 (主Y轴)
    chart_elec.add_series({
        'name':       ['原始数据_电参数', 0, 1],
        'categories': ['原始数据_电参数', 1, 0, last_c_row, 0], # A列 采集序列号
        'values':     ['原始数据_电参数', 1, 1, last_c_row, 1],
        'line':       {'color': '#2B579A', 'width': 1.5},
        'marker':     {'type': 'none'},
    })
    # 电流 (主Y轴)
    chart_elec.add_series({
        'name':       ['原始数据_电参数', 0, 2],
        'categories': ['原始数据_电参数', 1, 0, last_c_row, 0], # A列 采集序列号
        'values':     ['原始数据_电参数', 1, 2, last_c_row, 2],
        'line':       {'color': '#107C41', 'width': 1.75},
        'marker':     {'type': 'none'},
    })
    # 功率 (次Y轴)
    chart_elec.add_series({
        'name':       ['原始数据_电参数', 0, 3],
        'categories': ['原始数据_电参数', 1, 0, last_c_row, 0], # A列 采集序列号
        'values':     ['原始数据_电参数', 1, 3, last_c_row, 3],
        'line':       {'color': '#D83B01', 'width': 1.75},
        'marker':     {'type': 'none'},
        'y2_axis':    True,
    })
    chart_elec.set_title({'name': f'图表 2: 电参数变化曲线 (电压、电流、功率 随采集序列号)', 'name_font': {'name': '微软雅黑', 'size': 11, 'bold': True}})
    chart_elec.set_x_axis({
        'name': '采集序列号 (Id / NO.)', 'interval_unit': c_step, 'interval_tick': c_step,
        'label_position': 'low', 'major_gridlines': {'visible': True, 'line': {'color': '#F0F0F0', 'dash_type': 'dot'}}
    })
    chart_elec.set_y_axis({
        'name': '电压 (V) / 电流 (A)',
        'major_gridlines': {'visible': True, 'line': {'color': '#D9D9D9', 'dash_type': 'dash'}}
    })
    chart_elec.set_y2_axis({
        'name': '功率 (W)',
    })
    chart_elec.set_legend({'position': 'right', 'font': {'name': '微软雅黑', 'size': 9}})
    chart_elec.set_size({'width': 1180, 'height': 440})
    ws_dash.insert_chart('A29', chart_elec)
    
    # ---- 统计表格区域 (第 53 行开始) ----
    tbl_start = 52
    ws_dash.merge_range(tbl_start, 0, tbl_start, 6, '一、各通道温度特征统计分析 (CH1~CH16)', fmt_tbl_header)
    t_sub_headers = ['通道名称', '初始温度 (℃)', '最低温度 (℃)', '最高温度 (℃)', '结束温度 (℃)', '最大温升 ΔT (℃)', '平均速率 (℃/min)']
    for c_i, sh in enumerate(t_sub_headers):
        ws_dash.write(tbl_start + 1, c_i, sh, fmt_tbl_header)
        
    duration_min = total_t_points / 60.0 or 1.0
    overall_max_t = max(s['max'] for s in t_stats) if t_stats else 0
    for r_i, s in enumerate(t_stats):
        cur_r = tbl_start + 2 + r_i
        rate = s['rise'] / duration_min
        ws_dash.write(cur_r, 0, s['name'], fmt_tbl_cell)
        ws_dash.write(cur_r, 1, s['init'], fmt_tbl_num)
        ws_dash.write(cur_r, 2, s['min'], fmt_tbl_num)
        if abs(s['max'] - overall_max_t) < 0.01:
            ws_dash.write(cur_r, 3, s['max'], fmt_tbl_max)
        else:
            ws_dash.write(cur_r, 3, s['max'], fmt_tbl_num)
        ws_dash.write(cur_r, 4, s['final'], fmt_tbl_num)
        ws_dash.write(cur_r, 5, s['rise'], fmt_tbl_num)
        ws_dash.write(cur_r, 6, rate, fmt_tbl_num)
        
    # 电参数统计表 (放置在右侧 H 列开始)
    ws_dash.merge_range(tbl_start, 8, tbl_start, 12, '二、电气参数统计特征分析 (B、C、D列)', fmt_tbl_header)
    e_sub_headers = ['参数名称', '单位', '最小值', '最大值 (峰值)', '平均值']
    for c_i, sh in enumerate(e_sub_headers):
        ws_dash.write(tbl_start + 1, 8 + c_i, sh, fmt_tbl_header)
        
    e_rows = [
        ('供电电压 (Voltage)', 'V', e_stats['v_min'], e_stats['v_max'], e_stats['v_avg']),
        ('加热工作电流 (Current)', 'A', e_stats['i_min'], e_stats['i_max'], e_stats['i_avg']),
        ('加热消耗功率 (Power)', 'W', e_stats['p_min'], e_stats['p_max'], e_stats['p_avg']),
    ]
    for r_i, (p_name, p_unit, p_min, p_max, p_avg) in enumerate(e_rows):
        cur_r = tbl_start + 2 + r_i
        ws_dash.write(cur_r, 8, p_name, fmt_tbl_cell)
        ws_dash.write(cur_r, 9, p_unit, fmt_tbl_cell)
        ws_dash.write(cur_r, 10, p_min, fmt_tbl_num)
        ws_dash.write(cur_r, 11, p_max, fmt_tbl_max)
        ws_dash.write(cur_r, 12, p_avg, fmt_tbl_num)
        
    ws_dash.set_column('A:A', 14)
    ws_dash.set_column('B:G', 15)
    ws_dash.set_column('H:H', 18)
    ws_dash.set_column('I:M', 15)
    
    # ---------------- 写入 Sheet 2: 电参数独立图表 ----------------
    cs_elec = wb.add_chartsheet('电参数曲线图')
    chart_elec_full = wb.add_chart({'type': 'line'})
    chart_elec_full.add_series({
        'name': ['原始数据_电参数', 0, 1], 'categories': ['原始数据_电参数', 1, 0, last_c_row, 0],
        'values': ['原始数据_电参数', 1, 1, last_c_row, 1], 'line': {'color': '#2B579A', 'width': 1.6}, 'marker': {'type': 'none'}
    })
    chart_elec_full.add_series({
        'name': ['原始数据_电参数', 0, 2], 'categories': ['原始数据_电参数', 1, 0, last_c_row, 0],
        'values': ['原始数据_电参数', 1, 2, last_c_row, 2], 'line': {'color': '#107C41', 'width': 1.8}, 'marker': {'type': 'none'}
    })
    chart_elec_full.add_series({
        'name': ['原始数据_电参数', 0, 3], 'categories': ['原始数据_电参数', 1, 0, last_c_row, 0],
        'values': ['原始数据_电参数', 1, 3, last_c_row, 3], 'line': {'color': '#D83B01', 'width': 1.8}, 'marker': {'type': 'none'},
        'y2_axis': True
    })
    chart_elec_full.set_title({'name': f'座椅加热电参数变化曲线 (电压、电流、功率) - {group_name}'})
    chart_elec_full.set_x_axis({'name': '采集序列号 (Id)'})
    chart_elec_full.set_y_axis({'name': '电压 (V) / 电流 (A)'})
    chart_elec_full.set_y2_axis({'name': '功率 (W)'})
    cs_elec.set_chart(chart_elec_full)
    
    # ---------------- 写入 Sheet 3: 原始数据_温度 ----------------
    ws_raw_t = wb.add_worksheet('原始数据_温度')
    ws_raw_t.freeze_panes(10, 0)
    for r_i in range(9):
        if r_i < len(r_temp):
            for c_i, val in enumerate(r_temp[r_i]):
                ws_raw_t.write(r_i, c_i, val, fmt_raw_text)
    for c_i, val in enumerate(t_headers):
        ws_raw_t.write(9, c_i, val, fmt_raw_header)
    for r_i, row in enumerate(t_data):
        e_r = 10 + r_i
        for c_i, val in enumerate(row):
            if c_i == 0:
                try: ws_raw_t.write_number(e_r, c_i, int(val), fmt_raw_text)
                except ValueError: ws_raw_t.write(e_r, c_i, val, fmt_raw_text)
            elif c_i in (1, 2):
                ws_raw_t.write(e_r, c_i, val, fmt_raw_text)
            else:
                try: ws_raw_t.write_number(e_r, c_i, float(val), fmt_raw_num)
                except ValueError: ws_raw_t.write(e_r, c_i, val, fmt_raw_text)
    ws_raw_t.set_column(0, 0, 8)
    ws_raw_t.set_column(1, 1, 14)
    ws_raw_t.set_column(2, 2, 18)
    ws_raw_t.set_column(3, len(t_headers) - 1, 10)
    
    # ---------------- 写入 Sheet 4: 原始数据_电参数 ----------------
    ws_raw_c = wb.add_worksheet('原始数据_电参数')
    ws_raw_c.freeze_panes(1, 0)
    for c_i, val in enumerate(c_headers):
        ws_raw_c.write(0, c_i, val, fmt_raw_header)
    for r_i, row in enumerate(c_data):
        e_r = 1 + r_i
        for c_i, val in enumerate(row):
            if c_i == 0:
                try: ws_raw_c.write_number(e_r, c_i, int(val), fmt_raw_text)
                except ValueError: ws_raw_c.write(e_r, c_i, val, fmt_raw_text)
            elif c_i in (1, 2, 3):
                try: ws_raw_c.write_number(e_r, c_i, float(val), fmt_raw_num3)
                except ValueError: ws_raw_c.write(e_r, c_i, val, fmt_raw_text)
            else:
                ws_raw_c.write(e_r, c_i, val, fmt_raw_text)
    ws_raw_c.set_column(0, 0, 10)
    ws_raw_c.set_column(1, 3, 16)
    ws_raw_c.set_column(4, 4, 20)
    
    ws_dash.activate()
    wb.close()
    print(f"成功输出综合分析 Excel: {output_xlsx}")
    
    # -------------------------------------------------------------------------
    # 生成双图联动交互式 HTML 可视化报告
    # -------------------------------------------------------------------------
    generate_dual_interactive_html(
        group_name=group_name,
        temp_csv=temp_csv,
        curr_csv=curr_csv,
        t_times=t_times,
        t_date_times=t_date_times,
        t_seqs=t_seqs,
        t_channels=t_channels,
        t_stats=t_stats,
        c_seqs=c_seqs,
        c_voltages=c_voltages,
        c_currents=c_currents,
        c_powers=c_powers,
        c_times=c_times,
        e_stats=e_stats,
        output_html=output_html
    )

def generate_dual_interactive_html(
    group_name, temp_csv, curr_csv,
    t_times, t_date_times, t_seqs, t_channels, t_stats,
    c_seqs, c_voltages, c_currents, c_powers, c_times, e_stats,
    output_html
):
    print(f"正在生成双图联动 HTML 交互报告: {output_html}")
    
    # 构造温度系列
    t_series = []
    for i, ch in enumerate(t_channels):
        t_series.append({
            'name': ch['name'],
            'type': 'line',
            'data': ch['data'],
            'smooth': True,
            'showSymbol': False,
            'lineStyle': {'width': 1.8, 'color': CHANNEL_COLORS[i % len(CHANNEL_COLORS)]},
            'itemStyle': {'color': CHANNEL_COLORS[i % len(CHANNEL_COLORS)]},
            'emphasis': {'focus': 'series', 'lineStyle': {'width': 3}}
        })
        
    overall_min_t = min(s['min'] for s in t_stats) if t_stats else 0
    overall_max_t = max(s['max'] for s in t_stats) if t_stats else 0
    max_rise_t = max(s['rise'] for s in t_stats) if t_stats else 0
    
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{group_name} - 座椅加热温度与电参数双图联动分析平台</title>
    <script src="echarts.min.js"></script>
    <script src="../echarts.min.js"></script>
    <script>
    if (!window.echarts) {{
        document.write('<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"><\\/script>');
    }}
    </script>
    <style>
        :root {{
            --bg-primary: #0b132b;
            --bg-secondary: #1c2541;
            --card-bg: rgba(28, 37, 65, 0.85);
            --card-border: rgba(255, 255, 255, 0.08);
            --accent-cyan: #48cae4;
            --accent-blue: #0077b6;
            --accent-orange: #f77f00;
            --accent-green: #06d6a0;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-main);
            min-height: 100vh;
            padding: 16px 20px;
            overflow-x: hidden;
        }}
        .header-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
            margin-bottom: 16px;
            padding: 14px 20px;
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border-radius: 14px;
            border: 1px solid var(--card-border);
            box-shadow: 0 8px 30px rgba(0,0,0,0.3);
        }}
        .header-title h1 {{
            font-size: 20px;
            font-weight: 700;
            background: linear-gradient(135deg, #48cae4, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .header-title p {{
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 3px;
        }}
        .kpi-container {{ display: flex; gap: 10px; flex-wrap: wrap; }}
        .kpi-card {{
            background: rgba(11, 19, 43, 0.7);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 6px 12px;
            min-width: 95px;
            text-align: center;
        }}
        .kpi-label {{ font-size: 11px; color: var(--text-muted); }}
        .kpi-value {{
            font-size: 15px; font-weight: 700; color: #48cae4; font-family: "Consolas", monospace;
        }}
        .kpi-value.hot {{ color: #f43f5e; }}
        .kpi-value.green {{ color: #06d6a0; }}
        .kpi-value.orange {{ color: #f77f00; }}

        .main-layout {{
            display: grid;
            grid-template-columns: 1fr 340px;
            gap: 16px;
            margin-bottom: 16px;
        }}
        @media (max-width: 1250px) {{
            .main-layout {{ grid-template-columns: 1fr; }}
        }}
        .charts-column {{
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}
        .chart-box {{
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border-radius: 14px;
            border: 1px solid var(--card-border);
            padding: 14px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.25);
        }}
        .chart-box-title {{
            font-size: 14px;
            font-weight: 600;
            color: #e2e8f0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            padding: 0 6px;
        }}
        .badge-hint {{
            font-size: 11px;
            padding: 3px 8px;
            background: rgba(72, 202, 228, 0.15);
            color: #48cae4;
            border-radius: 12px;
            border: 1px solid rgba(72, 202, 228, 0.3);
        }}
        #chart-temp {{ width: 100%; height: 380px; }}
        #chart-elec {{ width: 100%; height: 340px; }}

        /* 侧边实时联动读数 HUD */
        .sidebar-card {{
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border-radius: 14px;
            border: 1px solid var(--card-border);
            padding: 16px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.25);
            display: flex;
            flex-direction: column;
            gap: 14px;
        }}
        .sidebar-title {{
            font-size: 14px;
            font-weight: 600;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--card-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .sync-badge {{ font-size: 11px; color: #06d6a0; }}

        .hud-block {{
            background: rgba(11, 19, 43, 0.75);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            padding: 10px 12px;
        }}
        .hud-row {{
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            margin-bottom: 4px;
        }}
        .hud-row:last-child {{ margin-bottom: 0; }}
        .hud-val {{
            font-family: "Consolas", monospace;
            font-weight: 700;
            color: #48cae4;
        }}

        .state-tag {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
        }}
        .state-heating {{
            background: rgba(244, 63, 94, 0.2);
            color: #f43f5e;
            border: 1px solid rgba(244, 63, 94, 0.5);
        }}
        .state-standby {{
            background: rgba(72, 202, 228, 0.15);
            color: #48cae4;
            border: 1px solid rgba(72, 202, 228, 0.4);
        }}

        .channels-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 6px;
            max-height: 380px;
            overflow-y: auto;
            padding-right: 4px;
        }}
        .channels-grid::-webkit-scrollbar {{ width: 4px; }}
        .channels-grid::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.15); border-radius: 2px; }}
        .ch-box {{
            background: rgba(11, 19, 43, 0.6);
            border: 1px solid var(--card-border);
            border-radius: 6px;
            padding: 5px 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .ch-box.max {{
            background: rgba(244, 63, 94, 0.2);
            border-color: rgba(244, 63, 94, 0.6);
        }}
        .ch-title {{
            font-size: 11px;
            display: flex;
            align-items: center;
            gap: 4px;
            font-weight: 600;
        }}
        .ch-dot {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; }}
        .ch-temp {{ font-family: "Consolas", monospace; font-size: 12px; font-weight: 700; }}

        /* 底部汇总表格 */
        .bottom-tables {{
            display: grid;
            grid-template-columns: 1.5fr 1fr;
            gap: 16px;
        }}
        @media (max-width: 1100px) {{
            .bottom-tables {{ grid-template-columns: 1fr; }}
        }}
        .tbl-card {{
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border-radius: 14px;
            border: 1px solid var(--card-border);
            padding: 16px;
        }}
        .tbl-card h3 {{
            font-size: 14px; font-weight: 600; margin-bottom: 12px; color: #e2e8f0;
        }}
        table.flat-table {{
            width: 100%; border-collapse: collapse; font-size: 12px;
        }}
        table.flat-table th {{
            background: rgba(11, 19, 43, 0.7); color: var(--text-muted);
            font-weight: 600; padding: 8px 10px; text-align: right;
            border-bottom: 1px solid var(--card-border);
        }}
        table.flat-table th:first-child {{ text-align: left; }}
        table.flat-table td {{
            padding: 7px 10px; text-align: right; font-family: "Consolas", monospace;
            border-bottom: 1px solid rgba(255,255,255,0.04);
        }}
        table.flat-table td:first-child {{ text-align: left; font-family: inherit; font-weight: 600; }}
        .max-val {{ color: #fb7185; font-weight: 700; }}

        /* 自定义 ECharts Tooltip */
        .custom-tip {{
            background: rgba(11, 19, 43, 0.95) !important;
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255,255,255,0.15) !important;
            border-radius: 10px !important;
            padding: 10px 12px !important;
            color: #f8fafc !important;
            box-shadow: 0 16px 36px rgba(0,0,0,0.5) !important;
            min-width: 300px;
        }}
        .tip-head {{ font-size: 13px; font-weight: 700; color: #48cae4; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 6px; margin-bottom: 8px; }}
        .tip-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; }}
        .tip-cell {{ background: rgba(28, 37, 65, 0.7); border-radius: 4px; padding: 3px 5px; text-align: center; border: 1px solid rgba(255,255,255,0.05); }}
        .tip-cell.peak {{ border-color: #f43f5e; background: rgba(244, 63, 94, 0.25); }}
        .tip-cname {{ font-size: 10px; }}
        .tip-cval {{ font-size: 11px; font-weight: 700; font-family: "Consolas", monospace; }}
    </style>
</head>
<body>

    <!-- 顶部状态栏 -->
    <div class="header-bar">
        <div class="header-title">
            <h1>汽车座椅加热标定 - 温度与电参数综合交互看板</h1>
            <p>标定组合: {os.path.basename(temp_csv)} + {os.path.basename(curr_csv)}</p>
        </div>
        <div class="kpi-container">
            <div class="kpi-card">
                <div class="kpi-label">试验采样点</div>
                <div class="kpi-value">{len(t_times):,}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">总测试时长</div>
                <div class="kpi-value">{t_times[-1] if t_times else ""}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">最高温度 (CH8)</div>
                <div class="kpi-value hot">{overall_max_t:.2f} ℃</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">平均工作电流</div>
                <div class="kpi-value green">{e_stats['i_avg']:.2f} A</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">加热峰值电流</div>
                <div class="kpi-value hot">{e_stats['i_max']:.2f} A</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">平均加热功率</div>
                <div class="kpi-value orange">{e_stats['p_avg']:.1f} W</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">峰值加热功率</div>
                <div class="kpi-value hot">{e_stats['p_max']:.1f} W</div>
            </div>
        </div>
    </div>

    <!-- 主展示区：双图联动 + 侧边实时联动 HUD -->
    <div class="main-layout">
        <div class="charts-column">
            <!-- 图表 1: 温度曲线 -->
            <div class="chart-box">
                <div class="chart-box-title">
                    <span>📈 图表 1: 座椅各通道温度变化曲线 (CH1 ~ CH16)</span>
                    <span class="badge-hint">💡 鼠标在任意图表滑动，两图时间轴纵向准星同步对齐高亮</span>
                </div>
                <div id="chart-temp"></div>
            </div>

            <!-- 图表 2: 电压/电流/功率曲线 -->
            <div class="chart-box">
                <div class="chart-box-title">
                    <span>⚡ 图表 2: 电气参数随采集序列号变化曲线 (电压、电流、功率 双Y轴)</span>
                    <span class="badge-hint">🔌 左轴: 电压(V) / 电流(A) | 右轴: 功率(W)</span>
                </div>
                <div id="chart-elec"></div>
            </div>
        </div>

        <!-- 侧边实时读数联动面板 -->
        <div class="sidebar-card">
            <div class="sidebar-title">
                <span>🎯 双图时间线实时读数联动</span>
                <span class="sync-badge">● 双图准星同步中</span>
            </div>

            <!-- 状态与时间 -->
            <div class="hud-block">
                <div class="hud-row">
                    <span style="color: var(--text-muted);">采集序列号 (NO./Id):</span>
                    <span id="hud-seq" class="hud-val">0</span>
                </div>
                <div class="hud-row">
                    <span style="color: var(--text-muted);">测试时间 (Time):</span>
                    <span id="hud-time" class="hud-val">{t_times[0]}</span>
                </div>
                <div class="hud-row">
                    <span style="color: var(--text-muted);">系统工作状态:</span>
                    <span id="hud-state" class="state-tag state-heating">🔥 加热工作中</span>
                </div>
            </div>

            <!-- 电参数实时卡片 -->
            <div class="hud-block">
                <div style="font-size: 11px; font-weight: 600; color: var(--text-muted); margin-bottom: 6px;">⚡ 电气参数当前读数:</div>
                <div class="hud-row">
                    <span>供电电压:</span>
                    <span id="hud-v" class="hud-val" style="color: #48cae4;">14.500 V</span>
                </div>
                <div class="hud-row">
                    <span>工作电流:</span>
                    <span id="hud-i" class="hud-val" style="color: #06d6a0;">0.241 A</span>
                </div>
                <div class="hud-row">
                    <span>消耗功率:</span>
                    <span id="hud-p" class="hud-val" style="color: #f77f00;">3.50 W</span>
                </div>
            </div>

            <!-- 温度实时通道卡片 -->
            <div style="display: flex; justify-content: space-between; font-size: 11px; font-weight: 600; color: var(--text-muted);">
                <span>16通道实时温度读数:</span>
                <span id="hud-peak-name" style="color: #f43f5e;">最高: CH8</span>
            </div>
            <div class="channels-grid" id="hud-ch-grid">
                <!-- JS 动态注入 -->
            </div>
        </div>
    </div>

    <!-- 底部统计表格 -->
    <div class="bottom-tables">
        <div class="tbl-card">
            <h3>📊 各测温通道统计特征 (CH1 ~ CH16)</h3>
            <table class="flat-table">
                <thead>
                    <tr>
                        <th>通道编号</th>
                        <th>初始温度 (℃)</th>
                        <th>最低温度 (℃)</th>
                        <th>最高峰值 (℃)</th>
                        <th>结束温度 (℃)</th>
                        <th>温升 ΔT (℃)</th>
                    </tr>
                </thead>
                <tbody id="tbl-temp-tbody"></tbody>
            </table>
        </div>
        <div class="tbl-card">
            <h3>⚡ 电气参数标定统计分析</h3>
            <table class="flat-table">
                <thead>
                    <tr>
                        <th>参数名称</th>
                        <th>单位</th>
                        <th>最小值</th>
                        <th>最大峰值</th>
                        <th>全程平均值</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>供电电压 (Voltage)</td>
                        <td>V</td>
                        <td>{e_stats['v_min']:.3f}</td>
                        <td>{e_stats['v_max']:.3f}</td>
                        <td>{e_stats['v_avg']:.3f}</td>
                    </tr>
                    <tr>
                        <td>工作电流 (Current)</td>
                        <td>A</td>
                        <td>{e_stats['i_min']:.4f}</td>
                        <td class="max-val">{e_stats['i_max']:.4f}</td>
                        <td>{e_stats['i_avg']:.4f}</td>
                    </tr>
                    <tr>
                        <td>消耗功率 (Power)</td>
                        <td>W</td>
                        <td>{e_stats['p_min']:.2f}</td>
                        <td class="max-val">{e_stats['p_max']:.2f}</td>
                        <td>{e_stats['p_avg']:.2f}</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        // 数据注入
        const tTimes = {json.dumps(t_times)};
        const tDateTimes = {json.dumps(t_date_times)};
        const tSeqs = {json.dumps(t_seqs)};
        const tSeries = {json.dumps(t_series)};
        const tStats = {json.dumps(t_stats)};
        const channelColors = {json.dumps(CHANNEL_COLORS)};
        
        const cSeqs = {json.dumps(c_seqs)};
        const cVoltages = {json.dumps(c_voltages)};
        const cCurrents = {json.dumps(c_currents)};
        const cPowers = {json.dumps(c_powers)};

        // 填充温度表格
        const tbodyT = document.getElementById('tbl-temp-tbody');
        const maxOverallT = Math.max(...tStats.map(s => s.max));
        tStats.forEach((s, idx) => {{
            const tr = document.createElement('tr');
            const isMax = Math.abs(s.max - maxOverallT) < 0.01;
            tr.innerHTML = `
                <td><span style="color:${{channelColors[idx]}};">●</span> ${{s.name}}</td>
                <td>${{s.init.toFixed(2)}}</td>
                <td>${{s.min.toFixed(2)}}</td>
                <td class="${{isMax ? 'max-val' : ''}}">${{s.max.toFixed(2)}} ${{isMax ? '🔥' : ''}}</td>
                <td>${{s.final.toFixed(2)}}</td>
                <td>+${{s.rise.toFixed(2)}}</td>
            `;
            tbodyT.appendChild(tr);
        }});

        // 填充侧边 HUD 16通道网格
        const chGrid = document.getElementById('hud-ch-grid');
        tStats.forEach((s, idx) => {{
            const div = document.createElement('div');
            div.className = 'ch-box';
            div.id = `ch-box-${{idx}}`;
            div.innerHTML = `
                <span class="ch-title">
                    <span class="ch-dot" style="background:${{channelColors[idx]}};"></span>
                    <span>${{s.name}}</span>
                </span>
                <span class="ch-temp" id="ch-val-${{idx}}">--</span>
            `;
            chGrid.appendChild(div);
        }});

        // 1. 初始化温度图表
        const chartTemp = echarts.init(document.getElementById('chart-temp'), 'dark', {{ renderer: 'canvas' }});
        const optTemp = {{
            backgroundColor: 'transparent',
            animation: false,
            grid: {{ top: 35, left: 55, right: 35, bottom: 65, containLabel: true }},
            tooltip: {{
                trigger: 'axis',
                backgroundColor: 'transparent',
                borderWidth: 0,
                padding: 0,
                axisPointer: {{
                    type: 'cross',
                    lineStyle: {{ color: '#48cae4', width: 1.5, type: 'dashed' }}
                }},
                formatter: function(params) {{
                    if (!params || !params.length) return '';
                    const dIdx = params[0].dataIndex;
                    const tm = tTimes[dIdx] || '';
                    let maxV = -999, maxName = '';
                    params.forEach(p => {{
                        if (p.value !== null && p.value > maxV) {{ maxV = p.value; maxName = p.seriesName; }}
                    }});
                    let grid = '';
                    params.forEach((p, idx) => {{
                        const isPk = p.seriesName === maxName;
                        const v = p.value !== null ? p.value.toFixed(2) : '--';
                        grid += `
                            <div class="tip-cell ${{isPk ? 'peak' : ''}}">
                                <div class="tip-cname" style="color:${{channelColors[idx % channelColors.length]}};">● ${{p.seriesName}}</div>
                                <div class="tip-cval">${{v}}</div>
                            </div>
                        `;
                    }});
                    return `
                        <div class="custom-tip">
                            <div class="tip-head">⏱️ 时间: ${{tm}} (序列号: ${{tSeqs[dIdx]}})</div>
                            <div class="tip-grid">${{grid}}</div>
                        </div>
                    `;
                }}
            }},
            legend: {{
                type: 'scroll', top: 0,
                textStyle: {{ color: '#94a3b8', fontSize: 11 }},
                icon: 'roundRect', itemWidth: 12, itemHeight: 4
            }},
            xAxis: {{
                type: 'category',
                data: tTimes,
                boundaryGap: false,
                axisLine: {{ lineStyle: {{ color: 'rgba(255,255,255,0.15)' }} }},
                axisLabel: {{ color: '#94a3b8', fontSize: 10, interval: Math.floor(tTimes.length / 14) }},
                splitLine: {{ show: true, lineStyle: {{ color: 'rgba(255,255,255,0.05)', type: 'dashed' }} }}
            }},
            yAxis: {{
                type: 'value',
                name: '温度 (℃)',
                nameTextStyle: {{ color: '#94a3b8', fontSize: 11 }},
                axisLine: {{ lineStyle: {{ color: 'rgba(255,255,255,0.15)' }} }},
                axisLabel: {{ color: '#94a3b8', fontSize: 10, formatter: '{{value}} ℃' }},
                splitLine: {{ show: true, lineStyle: {{ color: 'rgba(255,255,255,0.06)', type: 'dashed' }} }}
            }},
            dataZoom: [
                {{ type: 'inside', start: 0, end: 100 }},
                {{
                    type: 'slider', start: 0, end: 100, height: 20, bottom: 8,
                    borderColor: 'rgba(255,255,255,0.1)', backgroundColor: 'rgba(11,19,43,0.5)',
                    fillerColor: 'rgba(72,202,228,0.2)', handleStyle: {{ color: '#48cae4' }},
                    textStyle: {{ color: '#94a3b8', fontSize: 9 }}
                }}
            ],
            series: tSeries
        }};
        chartTemp.setOption(optTemp);

        // 2. 初始化电参数图表
        const chartElec = echarts.init(document.getElementById('chart-elec'), 'dark', {{ renderer: 'canvas' }});
        const optElec = {{
            backgroundColor: 'transparent',
            animation: false,
            grid: {{ top: 35, left: 55, right: 45, bottom: 65, containLabel: true }},
            tooltip: {{
                trigger: 'axis',
                backgroundColor: 'rgba(11,19,43,0.9)',
                borderColor: 'rgba(255,255,255,0.15)',
                axisPointer: {{ type: 'cross', lineStyle: {{ color: '#48cae4', width: 1.5, type: 'dashed' }} }}
            }},
            legend: {{
                top: 0,
                data: ['供电电压 (V)', '加热电流 (A)', '加热功率 (W)'],
                textStyle: {{ color: '#94a3b8', fontSize: 11 }},
                icon: 'roundRect', itemWidth: 14, itemHeight: 4
            }},
            xAxis: {{
                type: 'category',
                data: cSeqs,
                boundaryGap: false,
                axisLine: {{ lineStyle: {{ color: 'rgba(255,255,255,0.15)' }} }},
                axisLabel: {{ color: '#94a3b8', fontSize: 10, interval: Math.floor(cSeqs.length / 14) }},
                splitLine: {{ show: true, lineStyle: {{ color: 'rgba(255,255,255,0.05)', type: 'dashed' }} }}
            }},
            yAxis: [
                {{
                    type: 'value',
                    name: '电压(V) / 电流(A)',
                    nameTextStyle: {{ color: '#94a3b8', fontSize: 11 }},
                    axisLabel: {{ color: '#94a3b8', fontSize: 10 }},
                    splitLine: {{ show: true, lineStyle: {{ color: 'rgba(255,255,255,0.06)', type: 'dashed' }} }}
                }},
                {{
                    type: 'value',
                    name: '功率 (W)',
                    nameTextStyle: {{ color: '#f77f00', fontSize: 11 }},
                    axisLabel: {{ color: '#f77f00', fontSize: 10, formatter: '{{value}} W' }},
                    splitLine: {{ show: false }}
                }}
            ],
            dataZoom: [
                {{ type: 'inside', start: 0, end: 100 }},
                {{
                    type: 'slider', start: 0, end: 100, height: 20, bottom: 8,
                    borderColor: 'rgba(255,255,255,0.1)', backgroundColor: 'rgba(11,19,43,0.5)',
                    fillerColor: 'rgba(247,127,0,0.2)', handleStyle: {{ color: '#f77f00' }},
                    textStyle: {{ color: '#94a3b8', fontSize: 9 }}
                }}
            ],
            series: [
                {{
                    name: '供电电压 (V)',
                    type: 'line',
                    data: cVoltages,
                    lineStyle: {{ color: '#48cae4', width: 1.5 }},
                    itemStyle: {{ color: '#48cae4' }},
                    showSymbol: false
                }},
                {{
                    name: '加热电流 (A)',
                    type: 'line',
                    data: cCurrents,
                    lineStyle: {{ color: '#06d6a0', width: 2 }},
                    itemStyle: {{ color: '#06d6a0' }},
                    showSymbol: false
                }},
                {{
                    name: '加热功率 (W)',
                    type: 'line',
                    yAxisIndex: 1,
                    data: cPowers,
                    lineStyle: {{ color: '#f77f00', width: 2 }},
                    itemStyle: {{ color: '#f77f00' }},
                    showSymbol: false
                }}
            ]
        }};
        chartElec.setOption(optElec);

        // 3. 核心：实现双图联动 (echarts.connect)
        echarts.connect([chartTemp, chartElec]);

        // 4. 实时更新侧边 HUD 读数
        chartTemp.on('updateAxisPointer', function(event) {{
            const info = event.axesInfo && event.axesInfo[0];
            if (info) {{
                const dIdx = info.value;
                if (dIdx >= 0 && dIdx < tTimes.length) {{
                    document.getElementById('hud-seq').innerText = tSeqs[dIdx] !== undefined ? tSeqs[dIdx] : dIdx;
                    document.getElementById('hud-time').innerText = tTimes[dIdx] || '';

                    // 映射电参数序列
                    const cIdx = Math.min(dIdx, cCurrents.length - 1);
                    if (cIdx >= 0) {{
                        const curI = cCurrents[cIdx];
                        const curV = cVoltages[cIdx];
                        const curP = cPowers[cIdx];
                        document.getElementById('hud-v').innerText = (curV !== undefined ? curV.toFixed(3) : '--') + ' V';
                        document.getElementById('hud-i').innerText = (curI !== undefined ? curI.toFixed(3) : '--') + ' A';
                        document.getElementById('hud-p').innerText = (curP !== undefined ? curP.toFixed(2) : '--') + ' W';

                        const stateEl = document.getElementById('hud-state');
                        if (curI > 1.0) {{
                            stateEl.className = 'state-tag state-heating';
                            stateEl.innerText = '🔥 加热工作中 (' + curP.toFixed(1) + 'W)';
                        }} else {{
                            stateEl.className = 'state-tag state-standby';
                            stateEl.innerText = '💤 待机/保温调节 (' + curI.toFixed(2) + 'A)';
                        }}
                    }}

                    // 更新 16 通道温度
                    let maxT = -999, maxCh = '';
                    tSeries.forEach((s, idx) => {{
                        const v = s.data[dIdx];
                        const valEl = document.getElementById(`ch-val-${{idx}}`);
                        const boxEl = document.getElementById(`ch-box-${{idx}}`);
                        if (v !== null && v !== undefined) {{
                            valEl.innerText = v.toFixed(2) + ' ℃';
                            if (v > maxT) {{ maxT = v; maxCh = s.name; }}
                        }} else {{
                            valEl.innerText = '--';
                        }}
                    }});

                    document.getElementById('hud-peak-name').innerText = `最高: ${{maxCh}} (${{maxT.toFixed(2)}} ℃)`;
                    tSeries.forEach((s, idx) => {{
                        const boxEl = document.getElementById(`ch-box-${{idx}}`);
                        boxEl.classList.remove('max');
                        if (s.name === maxCh) boxEl.classList.add('max');
                    }});
                }}
            }}
        }});

        window.addEventListener('resize', () => {{
            chartTemp.resize();
            chartElec.resize();
        }});
    </script>
</body>
</html>
"""
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"成功生成双图联动 HTML: {output_html}")

def auto_pair_folder(folder_path):
    all_files = os.listdir(folder_path)
    csv_files = [f for f in all_files if f.lower().endswith('.csv') or '.csv.' in f.lower()]
    temp_files = [f for f in csv_files if '温度' in f]
    curr_files = [f for f in csv_files if '电流' in f]
    
    pairs = []
    if len(temp_files) == 1 and len(curr_files) == 1:
        pairs.append((os.path.join(folder_path, temp_files[0]), os.path.join(folder_path, curr_files[0])))
    else:
        for t_f in temp_files:
            matched = None
            for c_f in curr_files:
                for kw in ['高档', '中档', '低档']:
                    if kw in t_f and kw in c_f:
                        matched = c_f
                        break
                if matched:
                    break
            if not matched and len(curr_files) == 1:
                matched = curr_files[0]
            if matched:
                pairs.append((os.path.join(folder_path, t_f), os.path.join(folder_path, matched)))
    return pairs

def main():
    import argparse
    parser = argparse.ArgumentParser(description="座椅加热温度与电参数综合分析图表生成工具")
    parser.add_argument('inputs', nargs='*', default=[], help="输入目录路径或一对 (温度CSV, 电流CSV) 文件")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    if len(args.inputs) == 2 and os.path.isfile(args.inputs[0]) and os.path.isfile(args.inputs[1]):
        # 处理传入的一对文件
        process_combined_group(args.inputs[0], args.inputs[1])
    elif len(args.inputs) == 1 and os.path.isdir(args.inputs[0]):
        # 处理传入的指定目录
        folder = os.path.abspath(args.inputs[0])
        pairs = auto_pair_folder(folder)
        if not pairs:
            print(f"在目录 {folder} 中未找到可自动配对的温度与电流 CSV 文件。")
        for p_temp, p_curr in pairs:
            process_combined_group(p_temp, p_curr)
    else:
        # 默认处理 20200921 和 996D_2 两个目录
        default_folders = [
            os.path.join(base_dir, '20200921_座椅加热测试数据'),
            os.path.join(base_dir, '996D_2'),
        ]
        for folder in default_folders:
            if os.path.exists(folder):
                pairs = auto_pair_folder(folder)
                for p_temp, p_curr in pairs:
                    process_combined_group(p_temp, p_curr)

if __name__ == '__main__':
    main()
