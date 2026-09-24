"""
生成汽车座椅加热多通道温度交互式可视化网页 (HTML + ECharts)
支持鼠标悬停在时间线上时，高亮显示各个通道的实际温度值、时间、极值通道与实时特征。
"""

import os
import sys
import json
import csv

CHANNEL_COLORS = [
    '#FF3B30',  # CH1: 鲜红
    '#34C759',  # CH2: 翠绿
    '#FFCC00',  # CH3: 琥珀金
    '#007AFF',  # CH4: 亮蓝
    '#FF9500',  # CH5: 活力橙
    '#AF52DE',  # CH6: 优雅紫
    '#5856D6',  # CH7: 靛青
    '#FF2D55',  # CH8: 玫红
    '#00C7BE',  # CH9: 青绿
    '#30B0C7',  # CH10: 浅海蓝
    '#A2845E',  # CH11: 暖棕
    '#FF6482',  # CH12: 珊瑚粉
    '#32ADE6',  # CH13: 天空蓝
    '#8E8E93',  # CH14: 冷灰
    '#5AC8FA',  # CH15: 冰蓝
    '#E056FD',  # CH16: 霓虹紫
]

def generate_interactive_html(csv_path: str, output_html: str = None) -> str:
    if output_html is None:
        output_html = os.path.splitext(csv_path)[0] + '_交互图表.html'
        
    print(f"正在读取 CSV 数据: {csv_path}")
    raw_rows = []
    for enc in ['utf-8', 'gbk', 'gb2312', 'gb18030']:
        try:
            with open(csv_path, 'r', encoding=enc) as f:
                raw_rows = list(csv.reader(f))
            break
        except Exception:
            continue
            
    headers = raw_rows[9]
    data_rows = raw_rows[10:]
    
    times = [r[1] for r in data_rows if len(r) > 1]
    date_times = [r[2] for r in data_rows if len(r) > 2]
    
    # 提取通道数据 (CH1 到 CH16)
    channels_data = []
    ch_names = []
    stats_list = []
    
    for ch_idx in range(3, min(19, len(headers))):
        name = headers[ch_idx] if headers[ch_idx] else f"CH{ch_idx-2}"
        ch_names.append(name)
        vals = []
        for r in data_rows:
            try:
                vals.append(round(float(r[ch_idx]), 2))
            except (ValueError, IndexError):
                vals.append(None)
        channels_data.append(vals)
        
        valid_vals = [v for v in vals if v is not None]
        if valid_vals:
            c_min = min(valid_vals)
            c_max = max(valid_vals)
            c_init = valid_vals[0]
            c_final = valid_vals[-1]
            stats_list.append({
                'name': name,
                'init': c_init,
                'min': c_min,
                'max': c_max,
                'final': c_final,
                'rise': round(c_max - c_init, 2)
            })
            
    file_title = os.path.splitext(os.path.basename(csv_path))[0]
    overall_min = min(s['min'] for s in stats_list) if stats_list else 0
    overall_max = max(s['max'] for s in stats_list) if stats_list else 0
    max_rise = max(s['rise'] for s in stats_list) if stats_list else 0
    
    # 构造系列数据
    series_configs = []
    for i, name in enumerate(ch_names):
        series_configs.append({
            'name': name,
            'type': 'line',
            'data': channels_data[i],
            'smooth': True,
            'showSymbol': False,
            'symbol': 'circle',
            'symbolSize': 6,
            'lineStyle': {
                'width': 2,
                'color': CHANNEL_COLORS[i % len(CHANNEL_COLORS)]
            },
            'itemStyle': {
                'color': CHANNEL_COLORS[i % len(CHANNEL_COLORS)]
            },
            'emphasis': {
                'focus': 'series',
                'lineStyle': {'width': 3.5}
            }
        })
        
    times_json = json.dumps(times)
    date_times_json = json.dumps(date_times)
    series_json = json.dumps(series_configs)
    colors_json = json.dumps(CHANNEL_COLORS)
    ch_names_json = json.dumps(ch_names)
    stats_json = json.dumps(stats_list)
    
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{file_title} - 座椅加热温度高精度交互分析</title>
    <!-- 引入 ECharts -->
    <script src="../echarts.min.js"></script>
    <script>
    if (!window.echarts) {{
        document.write('<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"><\\/script>');
    }}
    </script>
    <style>
        :root {{
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --card-bg: rgba(30, 41, 59, 0.85);
            --card-border: rgba(255, 255, 255, 0.08);
            --accent-cyan: #38bdf8;
            --accent-blue: #3b82f6;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }}
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-main);
            min-height: 100vh;
            padding: 20px 24px;
            overflow-x: hidden;
        }}
        
        /* 顶部标题栏与卡片 */
        .header-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
            margin-bottom: 20px;
            padding: 16px 24px;
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border-radius: 16px;
            border: 1px solid var(--card-border);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
        }}
        
        .header-title h1 {{
            font-size: 22px;
            font-weight: 700;
            background: linear-gradient(135deg, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 4px;
        }}
        
        .header-title p {{
            font-size: 13px;
            color: var(--text-muted);
        }}
        
        .kpi-container {{
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }}
        
        .kpi-card {{
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            padding: 8px 14px;
            min-width: 105px;
            text-align: center;
        }}
        
        .kpi-label {{
            font-size: 11px;
            color: var(--text-muted);
            margin-bottom: 2px;
        }}
        
        .kpi-value {{
            font-size: 16px;
            font-weight: 700;
            color: #38bdf8;
            font-family: "Consolas", monospace;
        }}
        
        .kpi-value.hot {{
            color: #f43f5e;
        }}
        
        .kpi-value.cold {{
            color: #38bdf8;
        }}
        
        /* 主图表与实时读数区域 */
        .main-layout {{
            display: grid;
            grid-template-columns: 1fr 340px;
            gap: 20px;
            margin-bottom: 20px;
        }}
        
        @media (max-width: 1200px) {{
            .main-layout {{
                grid-template-columns: 1fr;
            }}
        }}
        
        .chart-card {{
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border-radius: 16px;
            border: 1px solid var(--card-border);
            padding: 16px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
            display: flex;
            flex-direction: column;
        }}
        
        .chart-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            padding: 0 8px;
        }}
        
        .chart-header h2 {{
            font-size: 15px;
            font-weight: 600;
            color: #e2e8f0;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .hint-badge {{
            font-size: 12px;
            padding: 4px 10px;
            background: rgba(56, 189, 248, 0.15);
            color: #38bdf8;
            border-radius: 20px;
            border: 1px solid rgba(56, 189, 248, 0.3);
        }}
        
        #chart-container {{
            width: 100%;
            height: 600px;
        }}
        
        /* 侧边实时读数与高亮卡片 */
        .sidebar-card {{
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border-radius: 16px;
            border: 1px solid var(--card-border);
            padding: 16px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
            display: flex;
            flex-direction: column;
            gap: 14px;
        }}
        
        .sidebar-title {{
            font-size: 15px;
            font-weight: 600;
            color: #e2e8f0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--card-border);
        }}
        
        .live-time-box {{
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 10px 14px;
        }}
        
        .live-time-row {{
            display: flex;
            justify-content: space-between;
            font-size: 13px;
            margin-bottom: 4px;
        }}
        
        .live-time-row:last-child {{
            margin-bottom: 0;
        }}
        
        .live-time-val {{
            font-family: "Consolas", monospace;
            font-weight: 700;
            color: #38bdf8;
        }}
        
        .channel-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            max-height: 480px;
            overflow-y: auto;
            padding-right: 4px;
        }}
        
        .channel-grid::-webkit-scrollbar {{
            width: 4px;
        }}
        .channel-grid::-webkit-scrollbar-thumb {{
            background: rgba(255, 255, 255, 0.15);
            border-radius: 2px;
        }}
        
        .channel-item {{
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 6px 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.2s ease;
        }}
        
        .channel-item.highest {{
            background: rgba(244, 63, 94, 0.18);
            border-color: rgba(244, 63, 94, 0.6);
            box-shadow: 0 0 10px rgba(244, 63, 94, 0.2);
        }}
        
        .channel-item.lowest {{
            background: rgba(56, 189, 248, 0.15);
            border-color: rgba(56, 189, 248, 0.5);
        }}
        
        .ch-name-group {{
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
            font-weight: 600;
        }}
        
        .ch-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
        }}
        
        .ch-val {{
            font-family: "Consolas", monospace;
            font-size: 13px;
            font-weight: 700;
            color: #f1f5f9;
        }}
        
        /* 底部汇总表格 */
        .table-card {{
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border-radius: 16px;
            border: 1px solid var(--card-border);
            padding: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
        }}
        
        .table-card h3 {{
            font-size: 15px;
            font-weight: 600;
            margin-bottom: 14px;
            color: #e2e8f0;
        }}
        
        .stats-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        
        .stats-table th {{
            background: rgba(15, 23, 42, 0.7);
            color: var(--text-muted);
            font-weight: 600;
            padding: 10px 12px;
            text-align: right;
            border-bottom: 1px solid var(--card-border);
        }}
        
        .stats-table th:first-child {{
            text-align: left;
        }}
        
        .stats-table td {{
            padding: 9px 12px;
            text-align: right;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            font-family: "Consolas", monospace;
        }}
        
        .stats-table td:first-child {{
            text-align: left;
            font-family: inherit;
            font-weight: 600;
        }}
        
        .stats-table tr:hover td {{
            background: rgba(255, 255, 255, 0.03);
        }}
        
        .max-val-tag {{
            color: #fb7185;
            font-weight: 700;
        }}
        
        /* 自定义 ECharts Tooltip 样式 */
        .custom-tooltip {{
            background: rgba(15, 23, 42, 0.94) !important;
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.15) !important;
            border-radius: 12px !important;
            box-shadow: 0 16px 36px rgba(0, 0, 0, 0.5) !important;
            padding: 12px 14px !important;
            color: #f8fafc !important;
            min-width: 320px;
        }}
        
        .tip-header {{
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            padding-bottom: 8px;
            margin-bottom: 10px;
        }}
        
        .tip-time {{
            font-size: 14px;
            font-weight: 700;
            color: #38bdf8;
            font-family: "Consolas", monospace;
        }}
        
        .tip-datetime {{
            font-size: 11px;
            color: #94a3b8;
            margin-top: 2px;
        }}
        
        .tip-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 6px;
        }}
        
        .tip-item {{
            background: rgba(30, 41, 59, 0.7);
            border-radius: 6px;
            padding: 4px 6px;
            display: flex;
            flex-direction: column;
            align-items: center;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}
        
        .tip-item.max-ch {{
            border-color: #f43f5e;
            background: rgba(244, 63, 94, 0.2);
        }}
        
        .tip-ch-name {{
            font-size: 10px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 3px;
        }}
        
        .tip-ch-val {{
            font-size: 12px;
            font-family: "Consolas", monospace;
            font-weight: 700;
            margin-top: 2px;
        }}
    </style>
</head>
<body>

    <!-- 顶部状态栏 -->
    <div class="header-bar">
        <div class="header-title">
            <h1>汽车座椅加热标定多通道温度实时分析平台</h1>
            <p>标定数据源: {file_title}.CSV | Applent 16通道温度巡检仪</p>
        </div>
        <div class="kpi-container">
            <div class="kpi-card">
                <div class="kpi-label">采样总点数</div>
                <div class="kpi-value">{len(times):,}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">试验总时长</div>
                <div class="kpi-value">{times[-1] if times else "0:00:00"}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">初始最低温</div>
                <div class="kpi-value cold">{overall_min:.2f} ℃</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">最高峰值温</div>
                <div class="kpi-value hot">{overall_max:.2f} ℃</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">最大温升 ΔT</div>
                <div class="kpi-value hot">+{max_rise:.2f} ℃</div>
            </div>
        </div>
    </div>

    <!-- 主展示区域：图表 + 实时光标读数联动卡片 -->
    <div class="main-layout">
        <div class="chart-card">
            <div class="chart-header">
                <h2>
                    <span>📈</span> 温度随时间动态变化曲线 (CH1 ~ CH16)
                </h2>
                <div class="hint-badge">💡 鼠标在图表中移动即可联动高亮对应时间线上全部通道数值，滚轮支持缩放</div>
            </div>
            <div id="chart-container"></div>
        </div>
        
        <!-- 侧边实时联动面板 -->
        <div class="sidebar-card">
            <div class="sidebar-title">
                <span>🎯 时间线实时读数联动</span>
                <span id="sync-status" style="font-size: 11px; color: #10b981;">● 实时同步中</span>
            </div>
            
            <div class="live-time-box">
                <div class="live-time-row">
                    <span style="color: var(--text-muted);">当前测试时间:</span>
                    <span id="hud-time" class="live-time-val">{times[0]}</span>
                </div>
                <div class="live-time-row">
                    <span style="color: var(--text-muted);">采集钟点:</span>
                    <span id="hud-datetime" style="font-size: 12px; color: #94a3b8;">{date_times[0]}</span>
                </div>
                <div class="live-time-row">
                    <span style="color: var(--text-muted);">当前峰值通道:</span>
                    <span id="hud-max-ch" style="color: #f43f5e; font-weight: 700;">CH8</span>
                </div>
                <div class="live-time-row">
                    <span style="color: var(--text-muted);">当前极差 (ΔT):</span>
                    <span id="hud-range" style="font-weight: 700; color: #f59e0b;">0.00 ℃</span>
                </div>
            </div>
            
            <div style="font-size: 12px; font-weight: 600; color: var(--text-muted);">16通道实时温度读数:</div>
            <div class="channel-grid" id="hud-channels-grid">
                <!-- 动态填充 16 通道读数 -->
            </div>
        </div>
    </div>

    <!-- 底部特征统计表格 -->
    <div class="table-card">
        <h3>📊 各通道温度标定统计与升温速率特征 (CH1 ~ CH16)</h3>
        <table class="stats-table">
            <thead>
                <tr>
                    <th>通道编号</th>
                    <th>初始温度 (℃)</th>
                    <th>最低温度 (℃)</th>
                    <th>最高峰值 (℃)</th>
                    <th>结束温度 (℃)</th>
                    <th>最大温升 ΔT (℃)</th>
                    <th>平均升温速率 (℃/min)</th>
                </tr>
            </thead>
            <tbody id="stats-tbody">
            </tbody>
        </table>
    </div>

    <script>
        // 数据源注入
        const times = {times_json};
        const dateTimes = {date_times_json};
        const channelColors = {colors_json};
        const chNames = {ch_names_json};
        const statsList = {stats_json};
        const seriesData = {series_json};
        
        // 初始化统计表格
        const tbody = document.getElementById('stats-tbody');
        const durationMin = times.length / 60.0 || 1;
        const maxValOverall = Math.max(...statsList.map(s => s.max));
        
        statsList.forEach((s, idx) => {{
            const tr = document.createElement('tr');
            const isMax = Math.abs(s.max - maxValOverall) < 0.01;
            const rate = (s.rise / durationMin).toFixed(2);
            tr.innerHTML = `
                <td><span style="color: ${{channelColors[idx]}}; font-weight: bold;">●</span> ${{s.name}}</td>
                <td>${{s.init.toFixed(2)}}</td>
                <td>${{s.min.toFixed(2)}}</td>
                <td class="${{isMax ? 'max-val-tag' : ''}}">${{s.max.toFixed(2)}} ${{isMax ? '🔥' : ''}}</td>
                <td>${{s.final.toFixed(2)}}</td>
                <td>+${{s.rise.toFixed(2)}}</td>
                <td>${{rate}}</td>
            `;
            tbody.appendChild(tr);
        }});

        // 初始化侧边 HUD 读数面板
        const hudGrid = document.getElementById('hud-channels-grid');
        chNames.forEach((ch, idx) => {{
            const item = document.createElement('div');
            item.className = 'channel-item';
            item.id = `hud-item-${{idx}}`;
            item.innerHTML = `
                <div class="ch-name-group">
                    <span class="ch-dot" style="background-color: ${{channelColors[idx]}};"></span>
                    <span>${{ch}}</span>
                </div>
                <div class="ch-val" id="hud-val-${{idx}}">--</div>
            `;
            hudGrid.appendChild(item);
        }});

        // 初始化 ECharts 实例
        const chartDom = document.getElementById('chart-container');
        const myChart = echarts.init(chartDom, 'dark', {{ renderer: 'canvas' }});
        
        const option = {{
            backgroundColor: 'transparent',
            animation: false, // 5500点大数据量关闭初次加载动画，保证极速渲染
            grid: {{
                top: 45,
                left: 55,
                right: 40,
                bottom: 85,
                containLabel: true
            }},
            tooltip: {{
                trigger: 'axis',
                backgroundColor: 'transparent',
                borderWidth: 0,
                padding: 0,
                extraCssText: 'box-shadow: none;',
                axisPointer: {{
                    type: 'cross',
                    lineStyle: {{
                        color: '#38bdf8',
                        width: 1.5,
                        type: 'dashed'
                    }},
                    crossStyle: {{
                        color: '#38bdf8'
                    }},
                    label: {{
                        backgroundColor: '#1e293b',
                        borderColor: '#38bdf8',
                        borderWidth: 1,
                        fontSize: 11,
                        color: '#38bdf8'
                    }}
                }},
                formatter: function (params) {{
                    if (!params || !params.length) return '';
                    const dataIndex = params[0].dataIndex;
                    const curTime = times[dataIndex] || '';
                    const curDate = dateTimes[dataIndex] || '';
                    
                    // 计算当前极值
                    let maxVal = -999, minVal = 999;
                    let maxCh = '', minCh = '';
                    params.forEach(p => {{
                        const v = p.value;
                        if (v !== null && v !== undefined) {{
                            if (v > maxVal) {{ maxVal = v; maxCh = p.seriesName; }}
                            if (v < minVal) {{ minVal = v; minCh = p.seriesName; }}
                        }}
                    }});
                    
                    // 构造 4 列紧凑悬浮卡片
                    let gridHtml = '';
                    params.forEach((p, idx) => {{
                        const v = p.value !== null && p.value !== undefined ? p.value.toFixed(2) : '--';
                        const isMax = p.seriesName === maxCh;
                        const isMin = p.seriesName === minCh;
                        const color = channelColors[idx % channelColors.length];
                        gridHtml += `
                            <div class="tip-item ${{isMax ? 'max-ch' : ''}}">
                                <div class="tip-ch-name" style="color: ${{color}};">
                                    <span>●</span> ${{p.seriesName}} ${{isMax ? '🔥' : ''}}
                                </div>
                                <div class="tip-ch-val">${{v}} ℃</div>
                            </div>
                        `;
                    }});
                    
                    return `
                        <div class="custom-tooltip">
                            <div class="tip-header">
                                <div class="tip-time">⏱️ 时间线: ${{curTime}} (第 ${{dataIndex}} 秒)</div>
                                <div class="tip-datetime">📅 标定记录: ${{curDate}} | 极差 ΔT: ${{(maxVal - minVal).toFixed(2)}} ℃</div>
                            </div>
                            <div class="tip-grid">
                                ${{gridHtml}}
                            </div>
                        </div>
                    `;
                }}
            }},
            legend: {{
                type: 'scroll',
                top: 5,
                textStyle: {{
                    color: '#94a3b8',
                    fontSize: 11
                }},
                icon: 'roundRect',
                itemWidth: 14,
                itemHeight: 4,
                pageTextStyle: {{ color: '#94a3b8' }}
            }},
            xAxis: {{
                type: 'category',
                data: times,
                boundaryGap: false,
                axisLine: {{ lineStyle: {{ color: 'rgba(255, 255, 255, 0.15)' }} }},
                axisLabel: {{
                    color: '#94a3b8',
                    fontSize: 11,
                    interval: Math.floor(times.length / 15),
                    rotate: 0
                }},
                splitLine: {{
                    show: true,
                    lineStyle: {{ color: 'rgba(255, 255, 255, 0.05)', type: 'dashed' }}
                }}
            }},
            yAxis: {{
                type: 'value',
                name: '温度 (℃)',
                nameTextStyle: {{ color: '#94a3b8', fontSize: 12, padding: [0, 0, 0, 20] }},
                axisLine: {{ lineStyle: {{ color: 'rgba(255, 255, 255, 0.15)' }} }},
                axisLabel: {{
                    color: '#94a3b8',
                    fontSize: 11,
                    formatter: '{{value}} ℃'
                }},
                splitLine: {{
                    show: true,
                    lineStyle: {{ color: 'rgba(255, 255, 255, 0.06)', type: 'dashed' }}
                }}
            }},
            dataZoom: [
                {{
                    type: 'inside', // 鼠标滚轮缩放与拖拽
                    start: 0,
                    end: 100
                }},
                {{
                    type: 'slider', // 底部时间轴滑块
                    start: 0,
                    end: 100,
                    height: 24,
                    bottom: 12,
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    backgroundColor: 'rgba(15, 23, 42, 0.6)',
                    fillerColor: 'rgba(56, 189, 248, 0.2)',
                    handleStyle: {{
                        color: '#38bdf8',
                        borderColor: '#ffffff',
                        borderWidth: 1
                    }},
                    textStyle: {{ color: '#94a3b8', fontSize: 10 }}
                }}
            ],
            series: seriesData
        }};
        
        myChart.setOption(option);
        
        // 联动侧边 HUD 读数面板
        myChart.on('updateAxisPointer', function (event) {{
            const xAxisInfo = event.axesInfo[0];
            if (xAxisInfo) {{
                const dataIndex = xAxisInfo.value;
                if (dataIndex >= 0 && dataIndex < times.length) {{
                    document.getElementById('hud-time').innerText = times[dataIndex];
                    document.getElementById('hud-datetime').innerText = dateTimes[dataIndex] || '';
                    
                    let maxVal = -999, minVal = 999;
                    let maxCh = '';
                    
                    seriesData.forEach((s, idx) => {{
                        const v = s.data[dataIndex];
                        const valEl = document.getElementById(`hud-val-${{idx}}`);
                        const itemEl = document.getElementById(`hud-item-${{idx}}`);
                        
                        if (v !== null && v !== undefined) {{
                            valEl.innerText = v.toFixed(2) + ' ℃';
                            if (v > maxVal) {{ maxVal = v; maxCh = s.name; }}
                            if (v < minVal) {{ minVal = v; }}
                        }} else {{
                            valEl.innerText = '--';
                        }}
                    }});
                    
                    document.getElementById('hud-max-ch').innerText = `${{maxCh}} (${{maxVal.toFixed(2)}} ℃)`;
                    document.getElementById('hud-range').innerText = (maxVal - minVal).toFixed(2) + ' ℃';
                    
                    // 高亮最高与最低通道卡片
                    seriesData.forEach((s, idx) => {{
                        const v = s.data[dataIndex];
                        const itemEl = document.getElementById(`hud-item-${{idx}}`);
                        itemEl.classList.remove('highest', 'lowest');
                        if (s.name === maxCh) {{
                            itemEl.classList.add('highest');
                        }} else if (v === minVal) {{
                            itemEl.classList.add('lowest');
                        }}
                    }});
                }}
            }}
        }});
        
        // 默认显示第 0 个点
        if (times.length > 0) {{
            myChart.dispatchAction({{
                type: 'showTip',
                seriesIndex: 0,
                dataIndex: 0
            }});
        }}
        
        // 窗口响应缩放
        window.addEventListener('resize', () => {{
            myChart.resize();
        }});
    </script>
</body>
</html>
"""
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html_content)
        
    print(f"成功生成交互式 HTML 可视化报告: {output_html}")
    return output_html

def main():
    import argparse
    parser = argparse.ArgumentParser(description="座椅加热温度交互式网页生成工具")
    parser.add_argument('input', nargs='?', default=None, help="输入的 CSV 文件路径")
    parser.add_argument('--all', action='store_true', help="批量转换 996D_2 目录下所有温度 CSV 文件")
    args = parser.parse_args()
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, '996D_2')
    
    if args.all:
        import glob
        temp_csvs = [f for f in glob.glob(os.path.join(data_dir, '*温度*.csv')) + glob.glob(os.path.join(data_dir, '*温度*.CSV'))]
        print(f"找到 {len(temp_csvs)} 个温度 CSV 文件，开始批量生成交互式 HTML...")
        for csv_f in temp_csvs:
            generate_interactive_html(csv_f)
        print("所有交互式 HTML 文件批量生成完成！")
    else:
        target = args.input
        if not target:
            target = os.path.join(data_dir, '996D主驾高档温度14801380.CSV')
        generate_interactive_html(target)

if __name__ == '__main__':
    main()
