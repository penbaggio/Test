"""
【昭融汇利】投资管理系统 — Dash + feffery Antd Menu

说明与约定：
- 顶部 4 个一级菜单：总览、投资策略、投资指令、产品分析
- 末级（投资策略下的所有末级）右侧展示页面与“净值及对比”一致（上传/图表/表格/策略信息）
- 其余末级先渲染占位卡片（后续可接入具体页面）
- 参考“【昭融汇利】产品分析系统打包.py”的实现风格，保留打包路径工具与笔记本地化存储

运行：
python 3.9+；Dash 3.x；feffery-antd-components；pandas；plotly
"""

import dash
from dash import html, dcc
from dash.dependencies import Input, Output, State, ALL, MATCH
import feffery_antd_components as fac
import pandas as pd
import io
import base64
import os
import sys
import json

# ========== 打包/路径辅助函数 ==========
def resource_path(*paths: str) -> str:
    """获取资源文件路径，兼容 PyInstaller(onefile) 解包目录。"""
    try:
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(__file__))
    except Exception:
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, *paths)


def _user_data_dir() -> str:
    """返回用户数据目录：优先 LOCALAPPDATA，其次 APPDATA，最后用户主目录。"""
    base = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or os.path.expanduser('~')
    app_dir = os.path.join(base, 'ZRHuiLi', 'InvestmentSystem')
    try:
        os.makedirs(app_dir, exist_ok=True)
    except Exception:
        app_dir = os.path.join(os.path.expanduser('~'), 'ZRHuiLi', 'InvestmentSystem')
        os.makedirs(app_dir, exist_ok=True)
    return app_dir


def user_data_file(filename: str) -> str:
    """组合用户数据文件完整路径。"""
    return os.path.join(_user_data_dir(), filename)


# ========== 菜单结构 ==========
# key 命名规则：L{层级}-{路径...}

LEAF_KEYS = [
    # 总览
    'L3-总览-市场总览-市场估值',
    'L3-总览-市场总览-宏观数据',
    'L3-总览-市场总览-盈利分析',
    'L2-总览-策略总览',
    # 投资策略
    'L3-投资策略-可转债-高YTM',
    'L3-投资策略-可转债-双低策略',
    'L2-投资策略-红利',
    'L2-投资策略-周内择时',
    'L2-投资策略-价值修复',
    'L2-投资策略-小微盘策略',
    'L2-投资策略-港股量化',
    # 投资指令
    'L1-投资指令',
    # 产品分析
    'L2-产品分析-产品总览',
    'L2-产品分析-对比分析',
]

# 需要渲染“净值及对比”模板的末级（仅投资策略域）
STRATEGY_LEAF_KEYS = [
    'L3-投资策略-可转债-高YTM',
    'L3-投资策略-可转债-双低策略',
    'L2-投资策略-红利',
    'L2-投资策略-周内择时',
    'L2-投资策略-价值修复',
    'L2-投资策略-小微盘策略',
    'L2-投资策略-港股量化',
]


def build_menu_items():
    def item(key, title):
        return {'component': 'Item', 'props': {'key': key, 'title': title}}

    def submenu(key, title, children):
        return {'component': 'SubMenu', 'props': {'key': key, 'title': title}, 'children': children}

    # 总览
    l3_market = [
        item('L3-总览-市场总览-市场估值', '市场估值'),
        item('L3-总览-市场总览-宏观数据', '宏观数据'),
        item('L3-总览-市场总览-盈利分析', '盈利分析'),
    ]
    l2_overview = [
        submenu('L2-总览-市场总览', '市场总览', l3_market),
        item('L2-总览-策略总览', '策略总览')
    ]

    # 投资策略
    l3_bond = [
        item('L3-投资策略-可转债-高YTM', '高YTM'),
        item('L3-投资策略-可转债-双低策略', '双低策略'),
    ]
    l2_strategy = [
        submenu('L2-投资策略-可转债', '可转债', l3_bond),
        item('L2-投资策略-红利', '红利'),
        item('L2-投资策略-周内择时', '周内择时'),
        item('L2-投资策略-价值修复', '价值修复'),
        item('L2-投资策略-小微盘策略', '小微盘策略'),
        item('L2-投资策略-港股量化', '港股量化'),
    ]

    # 投资指令（暂作末级页）
    l1_command = item('L1-投资指令', '投资指令')

    # 产品分析
    l2_product_analysis = [
        item('L2-产品分析-产品总览', '产品总览'),
        item('L2-产品分析-对比分析', '对比分析'),
    ]

    # 4 个一级
    return [
        submenu('L1-总览', '总览', l2_overview),
        submenu('L1-投资策略', '投资策略', l2_strategy),
        l1_command,
        submenu('L1-产品分析', '产品分析', l2_product_analysis),
    ]


MENU_ITEMS = build_menu_items()
DEFAULT_SELECTED_KEY = 'L1-总览'
DEFAULT_OPEN_KEYS = ['L1-总览', 'L2-总览-市场总览', 'L1-投资策略', 'L2-投资策略-可转债', 'L1-产品分析']

# ========== 产品周报：可弹出曲线的“指标”白名单（与原系统一致，可后续拓展） ==========
WEEKLY_ALLOWED_METRICS = {
    'Value（价格+溢价率）',
    'Value（价格＋溢价率）',
    '转债均价',
    '转股溢价率均值',
    'YTM中位数（%）'
}


# ========== 工具函数 ==========
def sanitize_strategy_key(raw: str) -> str:
    """将策略 key 转为文件友好形式。"""
    if not raw:
        return 'unknown'
    # 替换不适合作为文件名的字符
    for ch in ['\\', '/', ':', '*', '?', '"', '<', '>', '|', ' ', '，', '。']:
        raw = raw.replace(ch, '_')
    return raw.strip('_')


def strategy_notes_path(strategy_key: str) -> str:
    """针对策略 key 返回对应的策略描述与逻辑存储路径。"""
    return user_data_file(f"strategy_notes_{sanitize_strategy_key(strategy_key)}.json")


def netvalue_data_path(strategy_key: str) -> str:
    """针对策略 key 返回上次上传的净值数据持久化路径。"""
    return user_data_file(f"netvalue_{sanitize_strategy_key(strategy_key)}.csv")


def weekly_data_path(strategy_key: str) -> str:
    """针对策略 key 返回产品周报数据持久化路径。"""
    return user_data_file(f"weekly_{sanitize_strategy_key(strategy_key)}.csv")


def build_weekly_table(df: pd.DataFrame):
    """根据周报 DataFrame 构造 columns/data/clickableCols。"""
    if df.shape[1] >= 1:
        first_col = df.columns[0]
        df = df.rename(columns={first_col: '指标'})
    if '指标' in df.columns:
        df['指标'] = df['指标'].astype(str).map(lambda x: x.strip())
        df['指标'] = df['指标'].map(lambda s: (f"{s} 📈") if s in WEEKLY_ALLOWED_METRICS else s)
    week_cols = [c for c in df.columns if c != '指标']
    columns = (
        [{'title': '指标', 'dataIndex': '指标', 'width': 260, 'align': 'left', 'fixed': 'left'}] +
        [{'title': c, 'dataIndex': c, 'align': 'center', 'width': 110} for c in week_cols]
    )
    data = df.to_dict('records')
    click_cols = ['指标'] + week_cols
    return columns, data, click_cols


# ========== 实例化 dash ==========
app = dash.Dash(__name__, suppress_callback_exceptions=True)


# ========== 布局 ==========
app.layout = html.Div(
    [
        html.Div(
            fac.AntdMenu(
                id='main-menu',
                menuItems=MENU_ITEMS,
                defaultSelectedKey=DEFAULT_SELECTED_KEY,
                defaultOpenKeys=DEFAULT_OPEN_KEYS,
                mode='inline',
                style={'height': '100%'}
            ),
            style={
                'position': 'fixed',
                'left': 0,
                'top': 0,
                'bottom': 0,
                'width': '240px',
                'padding': '12px 8px',
                'borderRight': '1px solid #f0f0f0',
                'background': '#fff',
                'overflowY': 'auto'
            }
        ),
        html.Div(
            [
                dcc.Store(id='netvalue-data-store'),
                html.Div(id='main-content', style={'minHeight': 'calc(100vh - 80px)'}),
            ],
            style={'marginLeft': '240px', 'padding': '16px'}
        )
    ]
)


# ========== 右侧主内容渲染 ==========
@app.callback(
    Output('main-content', 'children'),
    Input('main-menu', 'currentKey'),
    State('main-menu', 'defaultSelectedKey'),
    State('main-menu', 'menuItemKeyToTitle')
)
def render_main_content(current_key, default_selected_key, key_to_title):
    key = current_key or default_selected_key or DEFAULT_SELECTED_KEY
    title = (key_to_title or {}).get(key) or key.split('-')[-1]

    # 投资策略域：末级渲染 Tabs（净值及对比 + 产品周报）
    if key in STRATEGY_LEAF_KEYS:
        # 读取当前策略专属描述/逻辑（若不存在则兼容旧全局文件）
        desc_value, logic_value = '', ''
        try:
            per_strategy_path = strategy_notes_path(key)
            if os.path.exists(per_strategy_path):
                with open(per_strategy_path, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    desc_value = saved.get('desc', '')
                    logic_value = saved.get('logic', '')
            else:
                # 旧版本兼容：读取全局文件
                legacy_global = user_data_file('strategy_notes.json')
                legacy_local = os.path.join(os.path.dirname(__file__), 'strategy_notes.json')
                for lp in (legacy_global, legacy_local):
                    if os.path.exists(lp):
                        with open(lp, 'r', encoding='utf-8') as f:
                            saved = json.load(f)
                            desc_value = saved.get('desc', '')
                            logic_value = saved.get('logic', '')
                            break
        except Exception:
            pass

        # 尝试加载当前策略的周报本地缓存
        weekly_path = weekly_data_path(key)
        weekly_table = None
        weekly_filename_default = ''
        if os.path.exists(weekly_path):
            try:
                df_weekly = pd.read_csv(weekly_path)
                cols, data, click_cols = build_weekly_table(df_weekly)
                weekly_table = fac.AntdTable(
                    id={'role': 'weekly', 'strategy': key, 'part': 'table'},
                    columns=cols,
                    data=data,
                    enableCellClickListenColumns=click_cols,
                    bordered=True,
                    size='small',
                    pagination={'pageSize': 200},
                    sticky=True,
                    style={'background': '#fff'}
                )
                weekly_filename_default = fac.AntdText('已自动恢复上次数据', type='secondary')
            except Exception:
                pass
        if weekly_table is None:
            weekly_table = fac.AntdTable(
                id={'role': 'weekly', 'strategy': key, 'part': 'table'},
                columns=[{'title': '指标', 'dataIndex': '指标'}],
                data=[],
                bordered=True,
                size='small',
                pagination={'pageSize': 200},
                style={'background': '#fff'}
            )

        netvalue_title = f'净值及对比 · {title}'
        return html.Div([
            # 当前策略 key + 标记是否需要尝试恢复净值数据
            dcc.Store(id='current-strategy-key', data=key),
            dcc.Store(id='netvalue-restored-flag', data=False),
            fac.AntdTitle(netvalue_title, level=3),
            fac.AntdTabs(
                items=[
                    {
                        'key': 'netvalue',
                        'label': '净值及对比',
                        'children': html.Div([
                            # 上传
                            fac.AntdCard([
                                fac.AntdSpace([
                                    html.Div(
                                        id='netvalue-upload-wrapper',
                                        children=dcc.Upload(
                                            id={'role': 'netvalue', 'part': 'upload', 'uid': 0},
                                            children=html.Div(['拖拽 CSV 到此区域，或点击选择文件']),
                                            multiple=False,
                                            accept='.csv',
                                            style={
                                                'width': '100%', 'padding': '24px', 'textAlign': 'center',
                                                'border': '1px dashed #d9d9d9', 'borderRadius': '6px', 'background': '#fafafa'
                                            }
                                        )
                                    ),
                                    fac.AntdButton(
                                        '清空数据',
                                        id='netvalue-clear-btn',
                                        danger=True,
                                        icon=fac.AntdIcon(icon='DeleteOutlined')
                                    )
                                ], direction='vertical', style={'width': '100%'}),
                                html.Div(id='netvalue-upload-filename', style={'marginTop': '8px', 'color': '#666'})
                            ], title='数据上传', style={'marginBottom': '16px'}),
                            # 图表与表格
                            fac.AntdCard([
                                fac.AntdRow([
                                    fac.AntdCol([
                                        fac.AntdSpace([
                                            fac.AntdSelect(
                                                id='netvalue-date-col-select',
                                                placeholder='选择日期列（可选）',
                                                allowClear=True,
                                                options=[],
                                                style={'minWidth': '220px'}
                                            ),
                                            fac.AntdSelect(
                                                id='netvalue-num-cols-select',
                                                mode='multiple',
                                                placeholder='选择要展示的数值列（可多选）',
                                                options=[],
                                                style={'minWidth': '320px'}
                                            )
                                        ], style={'marginBottom': '12px'}),
                                        dcc.Graph(id='netvalue-graph', style={'height': '360px'})
                                    ], span=16),
                                    fac.AntdCol([
                                        fac.AntdTable(
                                            id='netvalue-table',
                                            columns=[],
                                            data=[],
                                            pagination={'pageSize': 10},
                                            bordered=True,
                                            size='small',
                                            style={'marginTop': '12px'}
                                        )
                                    ], span=8)
                                ], gutter=12, style={'width': '1200px', 'margin': '0 auto'})
                            ], title='数据可视化与明细', style={'marginBottom': '16px'}),
                            # 策略信息
                            fac.AntdCard([
                                html.Div(id='netvalue-strategy-status', style={'color': '#666', 'marginBottom': '8px'}),
                                fac.AntdTitle('策略描述', level=5),
                                dcc.Textarea(
                                    id='netvalue-strategy-desc',
                                    placeholder='请输入策略描述...',
                                    value=desc_value,
                                    disabled=True,
                                    style={'width': '100%', 'height': '100px'}
                                ),
                                fac.AntdTitle('策略逻辑', level=5, style={'marginTop': '12px'}),
                                dcc.Textarea(
                                    id='netvalue-strategy-logic',
                                    placeholder='请输入策略逻辑...',
                                    value=logic_value,
                                    disabled=True,
                                    style={'width': '100%', 'height': '140px'}
                                )
                            ], title='策略信息', extra=fac.AntdSpace([
                                fac.AntdButton('修改', id='strategy-edit-btn', icon=fac.AntdIcon(icon='EditOutlined')),
                                fac.AntdButton('保存', id='strategy-save-btn', type='primary', icon=fac.AntdIcon(icon='SaveOutlined'))
                            ]))
                        ])
                    },
                    {
                        'key': 'weekly',
                        'label': '产品周报',
                        'children': html.Div([
                            fac.AntdCard([
                                fac.AntdSpace([
                                    html.Div(
                                        id={'role': 'weekly', 'strategy': key, 'part': 'upload-wrapper'},
                                        children=dcc.Upload(
                                            id={'role': 'weekly', 'strategy': key, 'part': 'upload', 'uid': 0},
                                            children=html.Div(['拖拽 CSV 到此区域，或点击选择文件']),
                                            multiple=False,
                                            accept='.csv',
                                            style={
                                                'width': '100%', 'padding': '24px', 'textAlign': 'center',
                                                'border': '1px dashed #d9d9d9', 'borderRadius': '6px', 'background': '#fafafa'
                                            }
                                        )
                                    ),
                                    fac.AntdButton(
                                        '清空数据',
                                        id={'role': 'weekly', 'strategy': key, 'part': 'clear'},
                                        danger=True,
                                        icon=fac.AntdIcon(icon='DeleteOutlined')
                                    )
                                ], direction='vertical', style={'width': '100%'}),
                                html.Div(
                                    weekly_filename_default,
                                    id={'role': 'weekly', 'strategy': key, 'part': 'filename'},
                                    style={'marginTop': '8px', 'color': '#666'}
                                )
                            ], title='数据上传', style={'marginBottom': '16px'}),
                            fac.AntdModal(
                                id={'role': 'weekly', 'strategy': key, 'part': 'modal'},
                                title='',
                                visible=False,
                                centered=True,
                                width=900,
                                closable=False,
                                maskClosable=False,
                                renderFooter=False,
                                children=[
                                    html.Div(
                                        fac.AntdButton(
                                            '关闭',
                                            id={'role': 'weekly', 'strategy': key, 'part': 'modal-close'},
                                            type='primary',
                                            danger=True,
                                            icon=fac.AntdIcon(icon='CloseOutlined')
                                        ),
                                        style={'textAlign': 'right', 'marginBottom': '8px'}
                                    ),
                                    dcc.Graph(id={'role': 'weekly', 'strategy': key, 'part': 'graph'}, style={'height': '420px'})
                                ]
                            ),
                            html.Div(
                                weekly_table,
                                style={'padding': '8px 0', 'width': '1710px', 'overflowX': 'auto'}
                            )
                        ])
                    }
                ],
                size='small'
            )
        ])

    # 其他叶子：占位卡片
    if key in LEAF_KEYS:
        return fac.AntdCard([
            fac.AntdTitle(title, level=3),
            fac.AntdText('页面开发中：后续将接入相应图表与数据。', type='secondary')
        ], style={'background': '#fff'})

    # 非末级：提示继续选择
    return fac.AntdCard([
        fac.AntdTitle(title, level=3),
        fac.AntdText('请选择左侧菜单中最后一级条目以展示页面。')
    ], style={'background': '#fff'})


# ========== 上传/清空 CSV，选项更新 ==========
@app.callback(
    [
        Output('netvalue-data-store', 'data'),
        Output('netvalue-upload-filename', 'children'),
        Output('netvalue-date-col-select', 'options'),
        Output('netvalue-date-col-select', 'value'),
        Output('netvalue-num-cols-select', 'options'),
        Output('netvalue-num-cols-select', 'value'),
    ],
    [
        Input({'role': 'netvalue', 'part': 'upload', 'uid': ALL}, 'contents'),
        Input('netvalue-clear-btn', 'nClicks'),
    ],
    [
        State({'role': 'netvalue', 'part': 'upload', 'uid': ALL}, 'filename'),
        State('current-strategy-key', 'data'),
    ],
    prevent_initial_call=True
)
def handle_upload_or_clear(contents_list, clear_clicks, filename_list, strategy_key):
    try:
        trigger_id = dash.ctx.triggered_id
    except Exception:
        trigger_id = dash.callback_context.triggered[0]['prop_id'].split('.')[0] if dash.callback_context.triggered else None

    # 清空
    if trigger_id == 'netvalue-clear-btn':
        # 删除持久化文件
        try:
            path = netvalue_data_path(strategy_key or 'unknown')
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
        return None, '', [], None, [], []

    # 上传
    if isinstance(trigger_id, dict) and trigger_id.get('part') == 'upload':
        if not isinstance(contents_list, list) or len(contents_list) == 0:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
        try:
            # 选择最后一个非空 contents
            sel_idx = None
            for i in range(len(contents_list) - 1, -1, -1):
                if contents_list[i]:
                    sel_idx = i
                    break
            if sel_idx is None:
                return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
            content = contents_list[sel_idx]
            filename = filename_list[sel_idx] if isinstance(filename_list, list) and sel_idx < len(filename_list) else None

            content_type, content_string = content.split(',')
            decoded = base64.b64decode(content_string)
            # 优先 utf-8-sig 解析
            text = None
            for enc in ('utf-8-sig', 'utf-8', 'gbk'):
                try:
                    text = decoded.decode(enc)
                    break
                except Exception:
                    continue
            if text is None:
                raise ValueError('无法以常见编码解析该文件')
            df = pd.read_csv(io.StringIO(text))
        except Exception as e:
            return dash.no_update, fac.AntdText(f'读取失败：{e}', type='danger'), [], None, [], []

        max_rows = 5000
        if len(df) > max_rows:
            df = df.head(max_rows)

        date_cols = [c for c in df.columns if 'date' in c.lower() or 'time' in c.lower() or '日期' in c or '时间' in c]
        num_cols = df.select_dtypes(include=['number']).columns.tolist()

        date_options = [{'label': c, 'value': c} for c in date_cols]
        num_options = [{'label': c, 'value': c} for c in num_cols]

        default_date = date_cols[0] if date_cols else None
        default_nums = num_cols[:2] if len(num_cols) >= 2 else (num_cols if num_cols else [])

        # 持久化保存（原始解析后的前 max_rows 行）
        try:
            persist_path = netvalue_data_path(strategy_key or 'unknown')
            df.to_csv(persist_path, index=False, encoding='utf-8-sig')
        except Exception:
            pass

        return (
            df.to_dict('records'),
            fac.AntdText(f'已上传：{filename}', type='secondary'),
            date_options,
            default_date,
            num_options,
            default_nums,
        )

    return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update


# ========== 净值及对比：进入页面自动尝试恢复上次持久化数据（仅一次） ==========
@app.callback(
    [
        Output('netvalue-data-store', 'data', allow_duplicate=True),
        Output('netvalue-upload-filename', 'children', allow_duplicate=True),
        Output('netvalue-date-col-select', 'options', allow_duplicate=True),
        Output('netvalue-date-col-select', 'value', allow_duplicate=True),
        Output('netvalue-num-cols-select', 'options', allow_duplicate=True),
        Output('netvalue-num-cols-select', 'value', allow_duplicate=True),
        Output('netvalue-restored-flag', 'data'),
    ],
    [
        Input('current-strategy-key', 'data'),
    ],
    [
        State('netvalue-restored-flag', 'data'),
    ],
    prevent_initial_call=True
)
def restore_last_netvalue(strategy_key, restored_flag):
    if restored_flag:
        # 已恢复过则不再重复
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    path = netvalue_data_path(strategy_key or 'unknown')
    if not os.path.exists(path):
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, True
    try:
        df = pd.read_csv(path)
    except Exception:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, True

    max_rows = 5000
    if len(df) > max_rows:
        df = df.head(max_rows)

    date_cols = [c for c in df.columns if 'date' in c.lower() or 'time' in c.lower() or '日期' in c or '时间' in c]
    num_cols = df.select_dtypes(include=['number']).columns.tolist()
    date_options = [{'label': c, 'value': c} for c in date_cols]
    num_options = [{'label': c, 'value': c} for c in num_cols]
    default_date = date_cols[0] if date_cols else None
    default_nums = num_cols[:2] if len(num_cols) >= 2 else (num_cols if num_cols else [])

    return (
        df.to_dict('records'),
        fac.AntdText('已自动恢复上次数据', type='secondary'),
        date_options,
        default_date,
        num_options,
        default_nums,
        True
    )


# ========== 净值及对比：清空时重置上传组件（解决同名文件二次上传不触发的问题） ==========
@app.callback(
    Output('netvalue-upload-wrapper', 'children'),
    Input('netvalue-clear-btn', 'nClicks'),
    prevent_initial_call=True
)
def reset_netvalue_upload(clear_clicks):
    uid = (clear_clicks or 0)
    return dcc.Upload(
        id={'role': 'netvalue', 'part': 'upload', 'uid': uid},
        children=html.Div(['拖拽 CSV 到此区域，或点击选择文件']),
        multiple=False,
        accept='.csv',
        style={
            'width': '100%', 'padding': '24px', 'textAlign': 'center',
            'border': '1px dashed #d9d9d9', 'borderRadius': '6px', 'background': '#fafafa'
        }
    )


# ========== 图表与表格联动 ==========
@app.callback(
    [
        Output('netvalue-graph', 'figure'),
        Output('netvalue-table', 'columns'),
        Output('netvalue-table', 'data'),
    ],
    [
        Input('netvalue-data-store', 'data'),
        Input('netvalue-date-col-select', 'value'),
        Input('netvalue-num-cols-select', 'value'),
    ]
)
def update_graph_table(data_records, date_col_value, num_cols_value):
    try:
        import plotly.express as px
    except Exception:
        # 依赖缺失时返回最小化占位图
        return {'data': [], 'layout': {'title': '请上传CSV数据'}}, [], []
    if not data_records:
        return px.scatter(title='请上传CSV数据'), [], []

    df = pd.DataFrame(data_records)
    numeric_all = df.select_dtypes(include=['number']).columns.tolist()
    selected_nums = num_cols_value if isinstance(num_cols_value, list) and len(num_cols_value) > 0 else (numeric_all[:2] if len(numeric_all) >= 2 else numeric_all)
    x_col = date_col_value if date_col_value in df.columns else None

    if selected_nums:
        if x_col:
            fig = px.line(df, x=x_col, y=selected_nums)
        else:
            fig = px.line(df, y=selected_nums)
    else:
        fig = px.scatter(title='未检测到数值列，无法绘制曲线')

    columns = [{'title': c, 'dataIndex': c} for c in df.columns]
    data_source = df.to_dict('records')
    return fig, columns, data_source


# ========== 周报页：上传/清空 CSV，动态更新表格（按策略作用域） ==========
@app.callback(
    [
        Output({'role': 'weekly', 'strategy': MATCH, 'part': 'filename'}, 'children'),
        Output({'role': 'weekly', 'strategy': MATCH, 'part': 'table'}, 'columns'),
        Output({'role': 'weekly', 'strategy': MATCH, 'part': 'table'}, 'data'),
        Output({'role': 'weekly', 'strategy': MATCH, 'part': 'table'}, 'enableCellClickListenColumns'),
    ],
    [
        Input({'role': 'weekly', 'strategy': MATCH, 'part': 'upload', 'uid': ALL}, 'contents'),
        Input({'role': 'weekly', 'strategy': MATCH, 'part': 'clear'}, 'nClicks'),
    ],
    [
        State({'role': 'weekly', 'strategy': MATCH, 'part': 'upload', 'uid': ALL}, 'filename'),
        State({'role': 'weekly', 'strategy': MATCH, 'part': 'table'}, 'data'),
    ],
    prevent_initial_call=True
)
def weekly_handle_upload_or_clear(contents_list, clear_clicks, filename_list, current_table_data):
    # 识别触发源
    try:
        trigger_id = dash.ctx.triggered_id
    except Exception:
        trigger_id = dash.callback_context.triggered[0]['prop_id'].split('.')[0] if dash.callback_context.triggered else None

    # 获取策略 key（来自任一 pattern id）
    strategy_key = None
    if isinstance(trigger_id, dict):
        strategy_key = trigger_id.get('strategy')

    # 清空：保存空表并重置为只含“指标”列
    if isinstance(trigger_id, dict) and trigger_id.get('part') == 'clear':
        try:
            # 删除持久化文件
            if strategy_key:
                save_path = weekly_data_path(strategy_key)
                if os.path.exists(save_path):
                    os.remove(save_path)
            # 返回空表（仅指标列）
            df_empty = pd.DataFrame({'指标': []})
            cols, data, click_cols = build_weekly_table(df_empty)
            return '', cols, data, click_cols
        except Exception as e:
            return fac.AntdText(f'清空失败：{e}', type='danger'), dash.no_update, dash.no_update, dash.no_update

    # 上传（pattern-matching）：从 ALL 列表中选择最后一个非空 contents
    if isinstance(trigger_id, dict) and trigger_id.get('part') == 'upload':
        if not isinstance(contents_list, list) or len(contents_list) == 0:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update
        sel_idx = None
        for i in range(len(contents_list) - 1, -1, -1):
            if contents_list[i]:
                sel_idx = i
                break
        if sel_idx is None:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update
        content = contents_list[sel_idx]
        filename = filename_list[sel_idx] if isinstance(filename_list, list) and sel_idx < len(filename_list) else None
        try:
            content_type, content_string = content.split(',')
            decoded = base64.b64decode(content_string)
            text = None
            for enc in ('utf-8-sig', 'utf-8', 'gbk'):
                try:
                    text = decoded.decode(enc)
                    break
                except Exception:
                    continue
            if text is None:
                raise ValueError('无法以常见编码解析该文件')
            df = pd.read_csv(io.StringIO(text))
            if len(df) > 5000:
                df = df.head(5000)
            # 持久化保存到用户目录（按策略分文件）
            if strategy_key:
                save_path = weekly_data_path(strategy_key)
                try:
                    df.to_csv(save_path, index=False, encoding='utf-8-sig')
                except Exception:
                    pass
            cols, data, click_cols = build_weekly_table(df)
            return fac.AntdText(f'已上传：{filename}', type='secondary'), cols, data, click_cols
        except Exception as e:
            return fac.AntdText(f'读取失败：{e}', type='danger'), dash.no_update, dash.no_update, dash.no_update

    return dash.no_update, dash.no_update, dash.no_update, dash.no_update


# ========== 周报页：清空时重置上传组件（解决同名文件二次上传不触发的问题） ==========
@app.callback(
    Output({'role': 'weekly', 'strategy': MATCH, 'part': 'upload-wrapper'}, 'children'),
    Input({'role': 'weekly', 'strategy': MATCH, 'part': 'clear'}, 'nClicks'),
    prevent_initial_call=True
)
def weekly_reset_upload(clear_clicks):
    uid = (clear_clicks or 0)
    # 取出当前触发 id 获取 strategy
    try:
        trig = dash.ctx.triggered_id
    except Exception:
        trig = None
    strategy_key = trig.get('strategy') if isinstance(trig, dict) else None
    return dcc.Upload(
        id={'role': 'weekly', 'strategy': strategy_key, 'part': 'upload', 'uid': uid},
        children=html.Div(['拖拽 CSV 到此区域，或点击选择文件']),
        multiple=False,
        accept='.csv',
        style={
            'width': '100%', 'padding': '24px', 'textAlign': 'center',
            'border': '1px dashed #d9d9d9', 'borderRadius': '6px', 'background': '#fafafa'
        }
    )


# ========== 周报：表格点击弹出曲线（按策略作用域） ==========
@app.callback(
    [
        Output({'role': 'weekly', 'strategy': MATCH, 'part': 'modal'}, 'visible'),
        Output({'role': 'weekly', 'strategy': MATCH, 'part': 'modal'}, 'title'),
        Output({'role': 'weekly', 'strategy': MATCH, 'part': 'graph'}, 'figure'),
    ],
    [
        Input({'role': 'weekly', 'strategy': MATCH, 'part': 'table'}, 'recentlyCellClickRecord'),
        Input({'role': 'weekly', 'strategy': MATCH, 'part': 'modal-close'}, 'nClicks'),
    ],
    State({'role': 'weekly', 'strategy': MATCH, 'part': 'table'}, 'data'),
    prevent_initial_call=True
)
def weekly_update_metric_modal(clicked_record, close_clicks, table_data):
    try:
        import plotly.express as px
    except Exception:
        px = None

    # 识别触发源
    try:
        trigger_id = dash.ctx.triggered_id
    except Exception:
        trigger_id = dash.callback_context.triggered[0]['prop_id'].split('.')[0] if dash.callback_context.triggered else None

    if isinstance(trigger_id, dict) and trigger_id.get('part') == 'modal-close':
        return False, dash.no_update, dash.no_update

    if isinstance(trigger_id, dict) and trigger_id.get('part') == 'table':
        if not clicked_record or not table_data:
            return False, dash.no_update, dash.no_update

        metric = clicked_record.get('指标') if isinstance(clicked_record, dict) else None
        raw_metric = (metric or '').strip()
        metric_key = raw_metric.replace(' 📈', '')
        if metric_key not in WEEKLY_ALLOWED_METRICS:
            return False, dash.no_update, dash.no_update

        # 获取对应行
        row = clicked_record if isinstance(clicked_record, dict) else None
        if not row:
            return False, dash.no_update, dash.no_update

        # 表头顺序
        header_order = [k for k in table_data[0].keys() if k != '指标'] if isinstance(table_data, list) and table_data else []
        x_cols = header_order if header_order else [k for k in row.keys() if k != '指标']

        def parse_value(raw_str: str):
            s = (raw_str or '').strip()
            if s == '':
                return None
            if s in {'—', '–', '-', '— —'}:
                return None
            neg = False
            if s.startswith('(') and s.endswith(')'):
                neg = True
                s = s[1:-1]
            s = s.replace('%', '').replace('％', '')
            s = s.replace(',', '').replace('，', '')
            s = s.replace('+', '').replace('＋', '')
            s = s.replace(' ', '')
            s = s.replace('－', '-')
            try:
                val = float(s)
                if neg:
                    val = -val
                return val
            except Exception:
                return None

        x_vals, y_vals = [], []
        for c in x_cols:
            val = parse_value(row.get(c))
            if val is None:
                continue
            x_vals.append(c)
            y_vals.append(val)

        if not x_vals:
            return False, dash.no_update, dash.no_update

        if px is not None:
            fig = px.line(x=x_vals, y=y_vals, markers=True)
            if ('%' in metric_key) or ('率' in metric_key):
                fig.update_layout(yaxis_ticksuffix='%')
            fig.update_layout(title=metric_key, xaxis_title='周次', yaxis_title='数值')
        else:
            fig = {'data': [], 'layout': {'title': metric_key}}
        return True, metric_key, fig

    return dash.no_update, dash.no_update, dash.no_update


# ========== 策略描述/逻辑：保存 与 修改 ==========
@app.callback(
    [
        Output('netvalue-strategy-desc', 'disabled'),
        Output('netvalue-strategy-logic', 'disabled'),
        Output('netvalue-strategy-status', 'children'),
    ],
    [
        Input('strategy-edit-btn', 'nClicks'),
        Input('strategy-save-btn', 'nClicks'),
    ],
    [
        State('netvalue-strategy-desc', 'value'),
        State('netvalue-strategy-logic', 'value'),
        State('current-strategy-key', 'data'),
    ],
    prevent_initial_call=True
)
def strategy_save_edit(edit_clicks, save_clicks, desc, logic, strategy_key):
    try:
        trigger_id = dash.ctx.triggered_id
    except Exception:
        trigger_id = dash.callback_context.triggered[0]['prop_id'].split('.')[0] if dash.callback_context.triggered else None

    if trigger_id == 'strategy-edit-btn':
        return False, False, fac.AntdText('已进入编辑模式', type='warning')

    if trigger_id == 'strategy-save-btn':
        try:
            # 每策略独立存储
            save_path = strategy_notes_path(strategy_key or 'unknown')
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump({'desc': desc or '', 'logic': logic or ''}, f, ensure_ascii=False, indent=2)
            return True, True, ''
        except Exception as e:
            return dash.no_update, dash.no_update, fac.AntdText(f'保存失败：{e}', type='danger')

    return dash.no_update, dash.no_update, dash.no_update


# ========== 启动 ==========
if __name__ == '__main__':
    # 尝试自动打开浏览器
    try:
        import webbrowser
        webbrowser.open('http://127.0.0.1:8061')
    except Exception:
        pass
    app.run(host='127.0.0.1', port=8061, debug=True)
