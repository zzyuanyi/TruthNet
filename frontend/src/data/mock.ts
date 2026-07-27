// 织网鉴真 TruthNet - Mock 数据
// 基于 V12 规范 §11-12

import type {
  Session,
  Message,
  PanelData,
  CompanyProfile,
  CompareData,
} from '@/types/truthnet';

// ============ 会话列表 ============

export const mockSessions: Session[] = [
  {
    id: 'session-001',
    title: '康美药业财务异常分析',
    company_code: '600518.SH',
    company_name: '康美药业',
    created_at: '2024-01-15T10:30:00Z',
    updated_at: '2024-01-15T11:45:00Z',
    message_count: 8,
    risk_level: 'red',
  },
  {
    id: 'session-002',
    title: '瑞幸咖啡舆情分析',
    company_code: 'LKNCY',
    company_name: '瑞幸咖啡',
    created_at: '2024-01-14T14:20:00Z',
    updated_at: '2024-01-14T15:30:00Z',
    message_count: 5,
    risk_level: 'orange',
  },
  {
    id: 'session-003',
    title: '乐视网股权穿透',
    company_code: '300104.SZ',
    company_name: '乐视网',
    created_at: '2024-01-13T09:15:00Z',
    updated_at: '2024-01-13T10:00:00Z',
    message_count: 3,
    risk_level: 'red',
  },
];

// ============ 对话消息 ============

export const mockMessages: Message[] = [
  {
    id: 'msg-001',
    session_id: 'session-001',
    role: 'user',
    content: '帮我分析一下康美药业的财务异常情况',
    created_at: '2024-01-15T10:30:00Z',
  },
  {
    id: 'msg-002',
    session_id: 'session-001',
    role: 'assistant',
    content: `## 康美药业财务异常分析

经过对康美药业（600518.SH）的财报数据进行多维度分析，发现以下重大异常：

### 1. 货币资金异常
- **账面货币资金**：399.6 亿元
- **实际可用资金**：仅 2.7 亿元
- **差异**：396.9 亿元资金去向不明

### 2. 应收账款异常
- **应收账款增速**：47.2%
- **营收增速**：-12.3%
- **异常**：应收增速远超营收增速，行业前 8%

### 3. 存货异常
- **存货周转天数**：189 天
- **行业平均**：67 天
- **异常**：周转效率远低于行业水平

### 结论
综合以上分析，康美药业存在**重大财务造假嫌疑**，建议高度警惕。`,
    created_at: '2024-01-15T10:31:00Z',
    thinking: '正在获取康美药业财报数据...正在执行财务勾稽规则检查...正在对比行业基准数据...',
    structured_data: {
      risk_level: 'red',
      triggered_rules: [
        {
          id: 'rule-001',
          name: '货币资金差异',
          current_value: '396.9 亿',
          threshold: '> 10 亿',
          industry_percentile: 99,
          severity: 'high',
        },
        {
          id: 'rule-002',
          name: '应收增速/营收增速',
          current_value: '47.2% / -12.3%',
          threshold: '差异 > 20%',
          industry_percentile: 92,
          severity: 'high',
        },
        {
          id: 'rule-003',
          name: '存货周转异常',
          current_value: '189 天',
          threshold: '> 行业均值 2 倍',
          industry_percentile: 95,
          severity: 'high',
        },
      ],
      key_metrics: [
        {
          name: '应收增速',
          value: '47.2%',
          change: '+59.5pp',
          risk_indicator: 'red',
          industry_benchmark: '12.3%',
        },
        {
          name: '存货周转',
          value: '189 天',
          change: '+122 天',
          risk_indicator: 'red',
          industry_benchmark: '67 天',
        },
        {
          name: '资金差异',
          value: '396.9 亿',
          risk_indicator: 'red',
          industry_benchmark: '< 10 亿',
        },
      ],
    },
    follow_ups: [
      '查看股权穿透图',
      '分析关联交易情况',
      '对比同行业其他公司',
    ],
    sources: [
      {
        id: 'src-001',
        title: '康美药业 2018 年年报',
        source: '上交所公告',
        date: '2019-04-30',
        snippet: '货币资金 399.6 亿元，应收账款 65.4 亿元...',
      },
      {
        id: 'src-002',
        title: '证监会行政处罚决定书',
        source: '证监会',
        date: '2020-05-15',
        snippet: '经查，康美药业 2016-2018 年财务报告存在重大虚假...',
      },
    ],
  },
];

// ============ 分析面板数据 ============

export const mockPanelData: PanelData = {
  risk_level: 'red',
  triggered_rules: [
    {
      id: 'rule-001',
      name: '货币资金差异',
      current_value: '396.9 亿',
      threshold: '> 10 亿',
      industry_percentile: 99,
      severity: 'high',
    },
    {
      id: 'rule-002',
      name: '应收增速/营收增速',
      current_value: '47.2% / -12.3%',
      threshold: '差异 > 20%',
      industry_percentile: 92,
      severity: 'high',
    },
    {
      id: 'rule-003',
      name: '存货周转异常',
      current_value: '189 天',
      threshold: '> 行业均值 2 倍',
      industry_percentile: 95,
      severity: 'high',
    },
  ],
  key_metrics: [
    {
      name: '应收增速',
      value: '47.2%',
      change: '+59.5pp',
      risk_indicator: 'red',
      industry_benchmark: '12.3%',
    },
    {
      name: '存货周转',
      value: '189 天',
      change: '+122 天',
      risk_indicator: 'red',
      industry_benchmark: '67 天',
    },
    {
      name: '资金差异',
      value: '396.9 亿',
      risk_indicator: 'red',
      industry_benchmark: '< 10 亿',
    },
  ],
};

// ============ 企业画像 ============

export const mockCompanyProfile: CompanyProfile = {
  code: '600518.SH',
  name: '康美药业',
  industry: '中药',
  market: '上交所',
  risk_overview: {
    risk_level: 'red',
    triggered_rules_count: 7,
    negative_announcement_ratio: 0.68,
    summary: '该公司存在重大财务造假嫌疑，多项财务指标严重异常，已被证监会行政处罚。',
  },
  financial_anomalies: [
    {
      rule_id: 'rule-001',
      rule_name: '货币资金差异',
      triggered: true,
      current_value: '396.9 亿',
      expected_value: '< 10 亿',
      deviation: '+3969%',
      industry_percentile: 99,
      explanation: '账面货币资金与实际可用资金存在巨大差异，396.9 亿元资金去向不明。',
    },
    {
      rule_id: 'rule-002',
      rule_name: '应收增速/营收增速',
      triggered: true,
      current_value: '47.2% / -12.3%',
      expected_value: '差异 < 20%',
      deviation: '+59.5pp',
      industry_percentile: 92,
      explanation: '应收账款增速远超营收增速，可能存在虚增收入或回收困难。',
    },
    {
      rule_id: 'rule-003',
      rule_name: '存货周转异常',
      triggered: true,
      current_value: '189 天',
      expected_value: '< 134 天',
      deviation: '+122 天',
      industry_percentile: 95,
      explanation: '存货周转天数远高于行业平均水平，可能存在存货积压或虚增。',
    },
    {
      rule_id: 'rule-004',
      rule_name: '经营现金流/净利润',
      triggered: true,
      current_value: '-0.23',
      expected_value: '> 0.7',
      deviation: '-133%',
      industry_percentile: 88,
      explanation: '经营现金流与净利润严重不匹配，盈利质量堪忧。',
    },
    {
      rule_id: 'rule-005',
      rule_name: '关联交易占比',
      triggered: true,
      current_value: '42.3%',
      expected_value: '< 20%',
      deviation: '+22.3pp',
      industry_percentile: 91,
      explanation: '关联交易占比过高，存在利益输送风险。',
    },
    {
      rule_id: 'rule-006',
      rule_name: '商誉减值风险',
      triggered: false,
      current_value: '0',
      expected_value: '-',
      deviation: '-',
      industry_percentile: 0,
      explanation: '无商誉，不存在减值风险。',
    },
    {
      rule_id: 'rule-007',
      rule_name: '研发费用异常',
      triggered: true,
      current_value: '0.3%',
      expected_value: '> 2%',
      deviation: '-1.7pp',
      industry_percentile: 15,
      explanation: '研发费用率远低于行业平均水平，与"中药创新"定位不符。',
    },
  ],
  equity_chain: {
    target_company: '康美药业',
    nodes: [
      { id: 'n1', name: '康美药业', type: 'company', is_target: true, share_ratio: 100 },
      { id: 'n2', name: '康美实业投资', type: 'company', share_ratio: 38.7 },
      { id: 'n3', name: '马兴田', type: 'person', share_ratio: 99.9 },
      { id: 'n4', name: '许冬瑾', type: 'person', share_ratio: 60.5 },
      { id: 'n5', name: '中国平安', type: 'fund', share_ratio: 5.2 },
      { id: 'n6', name: '中国人寿', type: 'fund', share_ratio: 3.1 },
      { id: 'n7', name: '康美（成都）', type: 'company', share_ratio: 100 },
      { id: 'n8', name: '康美（北京）', type: 'company', share_ratio: 100 },
    ],
    edges: [
      { source: 'n2', target: 'n1', relation: '控股', ratio: 38.7 },
      { source: 'n3', target: 'n2', relation: '实控人', ratio: 99.9 },
      { source: 'n4', target: 'n2', relation: '股东', ratio: 60.5 },
      { source: 'n5', target: 'n1', relation: '投资', ratio: 5.2 },
      { source: 'n6', target: 'n1', relation: '投资', ratio: 3.1 },
      { source: 'n1', target: 'n7', relation: '全资子公司', ratio: 100 },
      { source: 'n1', target: 'n8', relation: '全资子公司', ratio: 100 },
    ],
  },
  sentiment_events: [
    {
      id: 'evt-001',
      date: '2018-12-28',
      title: '康美药业被证监会立案调查',
      type: 'negative',
      source: '证监会官网',
      impact_score: 95,
      summary: '因公司涉嫌信息披露违法违规，证监会决定对公司进行立案调查。',
    },
    {
      id: 'evt-002',
      date: '2019-05-27',
      title: '康美药业承认财务造假',
      type: 'negative',
      source: '公司公告',
      impact_score: 100,
      summary: '公司发布更正公告，承认 2017 年货币资金多计 299 亿元。',
    },
    {
      id: 'evt-003',
      date: '2020-05-15',
      title: '证监会行政处罚',
      type: 'negative',
      source: '证监会',
      impact_score: 98,
      summary: '证监会对康美药业及相关责任人作出行政处罚，罚款合计 230 万元。',
    },
    {
      id: 'evt-004',
      date: '2021-11-17',
      title: '特别代表人诉讼判决',
      type: 'negative',
      source: '广州中院',
      impact_score: 96,
      summary: '法院判决康美药业赔偿 5.2 万余名投资者 24.59 亿元。',
    },
  ],
  evidence: [
    {
      category: '财务报告',
      items: [
        {
          id: 'ev-001',
          title: '2018 年年度报告',
          source: '上交所公告',
          date: '2019-04-30',
          content: '货币资金 399.6 亿元，应收账款 65.4 亿元，存货 112.3 亿元。',
          relevance_score: 98,
        },
        {
          id: 'ev-002',
          title: '2018 年年报更正公告',
          source: '公司公告',
          date: '2019-05-27',
          content: '更正后货币资金为 2.7 亿元，调减 396.9 亿元。',
          relevance_score: 100,
        },
      ],
    },
    {
      category: '监管文件',
      items: [
        {
          id: 'ev-003',
          title: '证监会行政处罚决定书',
          source: '证监会',
          date: '2020-05-15',
          content: '康美药业 2016-2018 年财务报告存在重大虚假，涉嫌财务造假。',
          relevance_score: 99,
        },
      ],
    },
    {
      category: '舆情报道',
      items: [
        {
          id: 'ev-004',
          title: '康美药业 300 亿货币资金"蒸发"',
          source: '财新网',
          date: '2019-05-28',
          content: '康美药业承认财务造假，近 300 亿货币资金不翼而飞。',
          relevance_score: 95,
        },
      ],
    },
  ],
};

// ============ 跨公司对比 ============

export const mockCompareData: CompareData = {
  companies: [
    { code: '600518.SH', name: '康美药业', industry: '中药', market: '上交所' },
    { code: '000963.SZ', name: '华东医药', industry: '中药', market: '深交所' },
    { code: '600252.SH', name: '中恒集团', industry: '中药', market: '上交所' },
  ],
  metrics: [
    {
      name: '应收增速',
      values: {
        '600518.SH': '47.2%',
        '000963.SZ': '15.3%',
        '600252.SH': '8.7%',
      },
      risk_indicators: {
        '600518.SH': 'red',
        '000963.SZ': 'blue',
        '600252.SH': 'green',
      },
    },
    {
      name: '存货周转天数',
      values: {
        '600518.SH': '189 天',
        '000963.SZ': '72 天',
        '600252.SH': '65 天',
      },
      risk_indicators: {
        '600518.SH': 'red',
        '000963.SZ': 'green',
        '600252.SH': 'green',
      },
    },
    {
      name: '经营现金流/净利润',
      values: {
        '600518.SH': '-0.23',
        '000963.SZ': '0.85',
        '600252.SH': '0.92',
      },
      risk_indicators: {
        '600518.SH': 'red',
        '000963.SZ': 'green',
        '600252.SH': 'green',
      },
    },
    {
      name: '关联交易占比',
      values: {
        '600518.SH': '42.3%',
        '000963.SZ': '12.1%',
        '600252.SH': '8.5%',
      },
      risk_indicators: {
        '600518.SH': 'red',
        '000963.SZ': 'blue',
        '600252.SH': 'green',
      },
    },
    {
      name: '风险等级',
      values: {
        '600518.SH': '高危',
        '000963.SZ': '低风险',
        '600252.SH': '正常',
      },
      risk_indicators: {
        '600518.SH': 'red',
        '000963.SZ': 'blue',
        '600252.SH': 'green',
      },
    },
  ],
};
