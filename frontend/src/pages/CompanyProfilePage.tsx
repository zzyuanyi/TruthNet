// 织网鉴真 TruthNet - 企业画像页
// T3: 5 区块（概览/财务/股权/舆情/证据），使用新组件

import {
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
  lazy,
  Suspense,
} from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { cn } from "@/lib/utils";
const sourceTypeIcons: Record<string, string> = {
  announcement: "公告",
  news: "新闻",
  research_report: "研报",
  regulation: "监管",
  web_search: "联网检索",
};
// 8/23 可读性：规则状态中文 + 参数单位中文映射（规则配置区）
const RULE_STATUS_LABELS: Record<string, string> = {
  triggered: "已触发",
  not_triggered: "未触发",
  insufficient_data: "数据不足",
  not_applicable: "不适用",
  unknown: "未知",
};

// 规则严重度是内部枚举；页面统一使用面向分析人员的预警名称。
const RISK_SEVERITY_LABELS: Record<string, string> = {
  red: "高危预警",
  orange: "中高危预警",
  yellow: "中等预警",
  blue: "低风险提示",
  green: "正常",
  unknown: "数据不足",
};

// 后端色彩词表（red/orange/yellow/blue/green/unknown）→ 信封卡皮肤等级
const chainSeveritySkin = (
  level: string | undefined,
): "critical" | "high" | "medium" | "low" | "info" =>
  ({
    red: "critical",
    orange: "high",
    yellow: "medium",
    blue: "low",
    green: "info",
    unknown: "info",
  } as Record<string, "critical" | "high" | "medium" | "low" | "info">)[
    level ?? ""
  ] ?? "info";
const RULE_UNIT_LABELS: Record<string, string> = {
  percent: "%",
  percentage_point: "个百分点",
  pp: "个百分点",
  quarters: "个季度",
  ratio: "比率",
  yuan: "元",
  CNY: "元",
  days: "天",
  times: "倍",
};
function formatChainPct(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "比例缺失";
  if (value === 0) return "0%";
  if (value >= 0.01) return `${value.toFixed(2)}%`;
  if (value >= 0.0001) return `${value.toFixed(4)}%`;
  return `${value.toExponential(2)}%`;
}

const EVIDENCE_FIELD_LABELS: Record<string, string> = {
  acct_rcv: "应收账款",
  admin_exp: "管理费用",
  fin_exp: "财务费用",
  less_oper_cost: "营业成本",
  less_selling_dist_exp: "销售费用",
  less_gerl_admin_exp: "管理费用",
  net_cash_flows_oper_act: "经营活动现金流量净额",
  oper_rev: "营业收入",
  selling_exp: "销售费用",
};

const EVIDENCE_SOURCE_LABELS: Record<string, string> = {
  financial_statement: "财务报表",
  neo4j_relationship: "股权关系",
  announcement: "公告",
  news: "新闻",
  research_report: "研报",
};

const IMPACT_TEMPLATE_NOTICE =
  "智能解读暂时不可用，当前展示为基于规则与可回查证据生成的核查摘要。";

function formatImpactAdviceWarnings(
  method: string,
  warnings: string[],
): string[] {
  const displayWarnings = warnings.map((warning) =>
    warning.includes("LLM 建议降级") ? IMPACT_TEMPLATE_NOTICE : warning,
  );
  if (method === "template") displayWarnings.unshift(IMPACT_TEMPLATE_NOTICE);
  return [...new Set(displayWarnings)];
}

function formatEvidencePeriod(period: unknown): string {
  const value = String(period || "");
  const match = /^(\d{4})(\d{2})(\d{2})$/.exec(value);
  if (!match) return value || "期次未标注";
  const [, year, month] = match;
  const labels: Record<string, string> = {
    "03": "一季度",
    "06": "二季度",
    "09": "三季度",
    "12": "年报",
  };
  return `${year}年${labels[month] || `${Number(month)}月`}`;
}

function formatEvidenceField(fieldPath: unknown): string {
  const value = String(fieldPath || "");
  const field = value.split(".").at(-1) || value;
  return EVIDENCE_FIELD_LABELS[field] || field || "报表字段";
}

function uniqueEvidenceClaims(
  claims: Array<Record<string, unknown>>,
): Array<Record<string, unknown>> {
  const seen = new Set<string>();
  return claims.filter((claim) => {
    const key = String(claim.text || claim.claim_id || "");
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  ArrowLeft,
  AlertTriangle,
  FileText,
  ChevronDown,
  ChevronRight,
  Shield,
  Loader2,
  SlidersHorizontal,
  Sparkles,
} from "lucide-react";
import "@phosphor-icons/web/duotone";
import {
  truthnetAPI,
  type EvidenceLookupData,
  type RuleDefinition,
} from "@/lib/api-client";
import { RelatedPartyTable } from "@/components/truthnet/RelatedPartyTable";
import { EquityGraph } from "@/components/truthnet/EquityGraph";
import type {
  EquityGraphData,
  EquityGraphNode,
} from "@/components/truthnet/EquityGraph";
import {
  RuleCard,
  type RuleEvidenceSummary,
} from "@/components/truthnet/RuleCard";
import { UpstreamDownstream } from "@/components/truthnet/UpstreamDownstream";
import { EquityInsight } from "@/components/truthnet/EquityInsight";
import { RiskTimeline } from "@/components/truthnet/RiskTimeline";
import { EvidenceChain } from "@/components/truthnet/EvidenceChain";
import { FinanceTrendOverview } from "@/components/truthnet/FinanceTrendOverview";
import { ExportSnapshotButton } from "@/components/ExportSnapshotButton";
import { Reveal } from "@/components/reveal";
import { CountUpNumber } from "@/components/truthnet/CountUpNumber";
import { InsightDisclosure } from "@/components/truthnet/InsightDisclosure";

import { Skeleton } from "@/components/ui/skeleton";
import { MarkdownRenderer } from "@/components/markdown-renderer";
import type {
  FinanceResponseData,
  EventsResponseData,
  EquityResponseData,
  RiskResponseData,
  RiskLevel,
  FinanceRuleItem,
  TimelineEvent,
  EventCluster,
  RiskEvidence,
  EvidenceCategory,
  Company,
  DerivationChain,
  ImpactAdviceData,
  DataQuality,
} from "@/types/truthnet";

// 证据按来源分组工具函数
function groupEvidenceBySource(evidences: RiskEvidence[]): EvidenceCategory[] {
  const sourceToCategory: Record<string, string> = {
    finance: "finance",
    financial_statement: "finance",
    equity: "equity",
    neo4j_relationship: "equity",
    event: "event",
    announcement: "event",
    news: "event",
    audit: "audit",
    regulation: "regulatory",
    regulatory: "regulatory",
    // 8/23 联网线索独立分组（外链卡片，不参与本地证据回查）
    web_search: "web",
  };
  const categoryLabels: Record<string, string> = {
    finance: "财务证据",
    equity: "股权证据",
    event: "舆情证据",
    audit: "审计证据",
    regulatory: "监管证据",
    web: "联网线索",
  };

  const groups = new Map<string, RiskEvidence[]>();
  for (const e of evidences) {
    const cat = sourceToCategory[e.source_type] || e.source_type;
    if (!groups.has(cat)) groups.set(cat, []);
    groups.get(cat)!.push(e);
  }

  return Array.from(groups.entries()).map(([cat, items]) => ({
    category: cat,
    label: categoryLabels[cat] || cat,
    items,
  }));
}

// 风险等级配置
const riskLevelConfig: Record<RiskLevel, { label: string; color: string }> = {
  red: { label: "高危", color: "bg-red-500 text-white" },
  orange: { label: "中高危", color: "bg-orange-500 text-white" },
  yellow: { label: "中等", color: "bg-yellow-500 text-white" },
  blue: { label: "低风险", color: "bg-blue-500 text-white" },
  green: { label: "正常", color: "bg-green-500 text-white" },
  unknown: { label: "未知", color: "bg-gray-500 text-white" },
};

// 区块标题：mono 编号 + 主色方块 + Phosphor 双色图标 + 扫光标题，对齐主界面设计语言
function SectionHeading({
  index,
  ph,
  title,
  hint,
}: {
  index: string;
  ph: string;
  title: string;
  hint?: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="font-mono text-[11px] tracking-[0.25em] text-primary/80">
        {index}
      </span>
      <span
        className="size-1.5 bg-primary shadow-[0_0_8px_var(--color-primary)]"
        aria-hidden
      />
      <h2 className="tn-sweep relative flex items-center gap-2 overflow-hidden text-xl font-bold tracking-tight">
        <i className={`ph ph-duotone ${ph} text-[22px] leading-none text-primary`} />
        {title}
      </h2>
      {hint ? (
        <span className="hidden md:block text-xs text-muted-foreground font-mono tracking-wider">
          {hint}
        </span>
      ) : null}
      <span
        className="ml-auto hidden sm:block h-px flex-1 max-w-40 bg-gradient-to-r from-border to-transparent"
        aria-hidden
      />
    </div>
  );
}

// 锚点导航项
const navItems = [
  { id: "overview", label: "概览", ph: "ph-gauge" },
  { id: "conclusions", label: "核心结论", ph: "ph-file-text" },
  { id: "impact", label: "影响与建议", ph: "ph-shield-star" },
  { id: "financial", label: "财务异常", ph: "ph-chart-bar-up" },
  { id: "equity", label: "股权穿透", ph: "ph-tree-structure" },
  { id: "sentiment", label: "舆情时间线", ph: "ph-newspaper" },
  { id: "evidence", label: "证据引用", ph: "ph-files" },
];

export default function CompanyProfilePage() {
  // 契约修复：路由 param 是 :companyCode（App.tsx:39），旧代码读 code 恒为
  // undefined → loadData 永不执行、页面永远卡骨架屏。
  const { companyCode } = useParams<{ companyCode: string }>();
  const code = companyCode;
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [profile, setProfile] = useState<Company | null>(null);
  useDocumentTitle(profile?.sec_name || "企业画像");
  const [financialAnomalies, setFinancialAnomalies] = useState<
    FinanceRuleItem[]
  >([]);
  const [equityData, setEquityData] = useState<EquityResponseData | null>(null);
  const [sentimentEvents, setSentimentEvents] = useState<TimelineEvent[]>([]);
  const [eventClusters, setEventClusters] = useState<EventCluster[]>([]);
  const [riskData, setRiskData] = useState<RiskResponseData | null>(null);
  const [impactAdvice, setImpactAdvice] = useState<ImpactAdviceData | null>(
    null,
  );
  const [impactAdviceLoading, setImpactAdviceLoading] = useState(false);
  const [derivationChains, setDerivationChains] = useState<DerivationChain[]>(
    [],
  );
  // 2026-08-16 口径整改：覆盖判定用真实数据存在性信号
  const [financeQuality, setFinanceQuality] = useState<DataQuality | null>(
    null,
  );
  const [announcementsAvailable, setAnnouncementsAvailable] = useState<
    boolean | null
  >(null);
  // 会7：规则配置参数（GET /rules/definitions），画像页呈现参数与触发规则对应关系
  const [ruleDefinitions, setRuleDefinitions] = useState<RuleDefinition[]>([]);
  // 8/23 会7 深化：阈值编辑草稿 + 保存/重置状态
  const [draftThresholds, setDraftThresholds] = useState<
    Record<string, Record<string, string>>
  >({});
  const [configSaving, setConfigSaving] = useState(false);
  const [configResetting, setConfigResetting] = useState(false);
  const [configError, setConfigError] = useState<string | null>(null);
  const [ruleDefsOverridden, setRuleDefsOverridden] = useState(false);
  // 8/23 分步渲染：区分「未加载」与「无数据」（区块级骨架 vs 暂无）
  const [financeLoaded, setFinanceLoaded] = useState(false);
  const [eventsLoaded, setEventsLoaded] = useState(false);
  const [orbitDetail, setOrbitDetail] = useState<EquityNodeDTO | null>(null);

  const getRiskColor = (level: string) => {
    const colors: Record<string, string> = {
      red: "#ef4444",
      orange: "#f97316",
      yellow: "#eab308",
      blue: "#3b82f6",
      unknown: "#6b7280",
    };
    return colors[level] || "#6b7280";
  };
  const getRiskBadgeStyle = (level: string) => {
    const styles: Record<string, string> = {
      red: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
      orange:
        "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400",
      yellow:
        "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
      blue: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
      unknown: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
    };
    return styles[level] || styles.unknown;
  };
  const getVerificationCardStyle = (level: string) => {
    const styles: Record<string, string> = {
      red: "border-l-4 border-l-red-500 border-red-200 bg-red-50/60 dark:border-red-900/60 dark:bg-red-950/20",
      orange:
        "border-l-4 border-l-orange-500 border-orange-200 bg-orange-50/60 dark:border-orange-900/60 dark:bg-orange-950/20",
      yellow:
        "border-l-4 border-l-yellow-500 border-yellow-200 bg-yellow-50/60 dark:border-yellow-900/60 dark:bg-yellow-950/20",
    };
    return (
      styles[level] ||
      "border-l-4 border-l-muted-foreground/40 border-border/70 bg-background"
    );
  };
  // B2 舆情影响结论（后端 events.impact_conclusions，需 include_impacts=true）
  // A2（8/9 老师要求）：触发规则关联证据的摘要（evidenceId → 平铺摘要）
  const [ruleEvidenceSummary, setRuleEvidenceSummary] = useState<
    Record<string, RuleEvidenceSummary>
  >({});
  // A2：批量拉取触发规则的证据摘要用于平铺（去重 + 上限 30）。
  // 注意：本 effect 必须在 early return 之前注册（Rules of Hooks）；
  // 依赖稳定字符串键（避免数组身份变化导致无限重跑）。
  const triggeredEvidenceKey = financialAnomalies
    .filter((r) => r.status === "triggered")
    .flatMap((r) => r.evidence_ids || [])
    .join(",");
  useEffect(() => {
    const ids = [
      ...new Set(triggeredEvidenceKey.split(",").filter(Boolean)),
    ].slice(0, 30);
    if (ids.length === 0) return;
    let cancelled = false;
    void (async () => {
      const settled = await Promise.allSettled(
        ids.map((id) => truthnetAPI.getEvidence(id)),
      );
      if (cancelled) return;
      const map: Record<string, RuleEvidenceSummary> = {};
      settled.forEach((res, i) => {
        if (res.status === "fulfilled") {
          const ev = (res.value.data?.evidence || {}) as Record<
            string,
            unknown
          >;
          map[ids[i]] = {
            evidenceId: ids[i],
            title: String(ev.source_title || ev.field_path || ids[i]),
            sourceType: String(ev.source_type || ""),
            period: String(ev.period || ""),
          };
        }
      });
      setRuleEvidenceSummary(map);
    })();
    return () => {
      cancelled = true;
    };
  }, [code, triggeredEvidenceKey]); // eslint-disable-line react-hooks/exhaustive-deps
  const [activeSection, setActiveSection] = useState("overview");
  const [evidenceDialogOpen, setEvidenceDialogOpen] = useState(false);
  const [evidenceDialogTitle, setEvidenceDialogTitle] = useState("证据详情");
  const [evidenceDialogItems, setEvidenceDialogItems] = useState<
    Array<{
      evidenceId: string;
      data?: EvidenceLookupData;
      error?: string;
      isGenerated?: boolean;
    }>
  >([]);
  const [evidenceDialogLoading, setEvidenceDialogLoading] = useState(false);
  // 报告生成（P1：画像页入口 → 创建任务 → 跳报告页，状态轮询由 ReportPage 接管）
  const [reportCreating, setReportCreating] = useState(false);

  // 生成报告：POST /reports（必填 company_code）→ 跳 /reports/{id}
  const handleGenerateReport = async () => {
    if (!profile || reportCreating) return;
    setReportCreating(true);
    try {
      const res = await truthnetAPI.createReport(profile.wind_code);
      navigate(`/reports/${res.data.report_id}`);
    } catch (err) {
      console.error("创建报告失败:", err);
      setReportCreating(false);
    }
  };

  // 8/23 会7 深化：definitions 首次加载后填充编辑草稿（已有编辑不覆盖）
  useEffect(() => {
    if (ruleDefinitions.length === 0) return;
    setDraftThresholds((prev) => {
      if (Object.keys(prev).length > 0) return prev;
      const next: Record<string, Record<string, string>> = {};
      for (const def of ruleDefinitions) {
        next[def.rule_id] = {};
        for (const [k, v] of Object.entries(def.thresholds)) {
          next[def.rule_id][k] = String(v);
        }
      }
      return next;
    });
  }, [ruleDefinitions]);

  // 8/23 会7 深化：保存并刷新（PUT /rules/config → 重拉全部数据按新阈值重算）
  const handleSaveRuleConfig = async () => {
    if (configSaving || ruleDefinitions.length === 0) return;
    const rulesBody: Record<string, unknown> = {};
    for (const def of ruleDefinitions) {
      const thresholds: Record<string, number> = {};
      for (const [k] of Object.entries(def.thresholds)) {
        const raw = draftThresholds[def.rule_id]?.[k];
        if (
          raw === undefined ||
          raw.trim() === "" ||
          Number.isNaN(Number(raw))
        ) {
          setConfigError(`${def.rule_id}.${k} 不是有效数字`);
          return;
        }
        thresholds[k] = Number(raw);
      }
      rulesBody[def.rule_id] = { enabled: def.enabled, thresholds };
    }
    setConfigError(null);
    setConfigSaving(true);
    try {
      await truthnetAPI.updateRuleConfig(rulesBody);
      await loadData();
    } catch (err) {
      setConfigError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setConfigSaving(false);
    }
  };

  // 8/23 会7 深化：重置恢复默认（DELETE /rules/config → 重拉）
  const handleResetRuleConfig = async () => {
    if (configResetting) return;
    setConfigError(null);
    setConfigResetting(true);
    try {
      await truthnetAPI.resetRuleConfig();
      await loadData();
    } catch (err) {
      setConfigError(err instanceof Error ? err.message : "重置失败");
    } finally {
      setConfigResetting(false);
    }
  };

  const sectionRefs = {
    overview: useRef<HTMLDivElement>(null),
    conclusions: useRef<HTMLDivElement>(null),
    evidence: useRef<HTMLDivElement>(null),
    impact: useRef<HTMLDivElement>(null),
    financial: useRef<HTMLDivElement>(null),
    equity: useRef<HTMLDivElement>(null),
    sentiment: useRef<HTMLDivElement>(null),
  };
  // 8/23 scrollspy：右侧滚动容器引用 + 滚动联动左侧导航高亮
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const handleScrollSync = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const scrollTop = container.scrollTop;
    const offset = 140;
    let current = navItems[0].id;
    for (const item of navItems) {
      const ref = sectionRefs[item.id as keyof typeof sectionRefs];
      if (ref.current && ref.current.offsetTop <= scrollTop + offset) {
        current = item.id;
      }
    }
    // 底部兜底：滚到底选中最后一项
    if (container.scrollHeight - scrollTop - container.clientHeight < 40) {
      current = navItems[navItems.length - 1].id;
    }
    setActiveSection(current);
  }, []);

  // 8/23 StrictMode 防重：dev 下 effect 双执行会发起两套请求（LLM 并发
  // 超时 → impact-advice 降级覆盖 LLM 内容）；in-flight 拦截同 code 的
  // 第二次调用。用户切换公司（code 变化）不受影响，且旧请求完成时
  // 若已切走则忽略其 setState（防污染新公司数据）。
  const loadInFlight = useRef(false);
  const loadForCode = useRef("");

  useEffect(() => {
    if (code) {
      loadData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  const loadData = async () => {
    if (!code) return;
    const myCode = code;
    if (loadInFlight.current && loadForCode.current === myCode) return;
    loadInFlight.current = true;
    loadForCode.current = myCode;
    setError(null);
    setLoading(true);
    setProfile(null);
    setFinancialAnomalies([]);
    setEquityData(null);
    setSentimentEvents([]);
    setEventClusters([]);
    setRiskData(null);
    setImpactAdvice(null);
    setDerivationChains([]);
    setFinanceQuality(null);
    setAnnouncementsAvailable(null);
    setRuleDefinitions([]);
    setRuleEvidenceSummary({});
    setFinanceLoaded(false);
    setEventsLoaded(false);
    // 8/23 分步渲染：先取公司基础信息（页头/概览依赖），其余请求并行发起，
    // 各数据到达即渲染对应区块——页面渐进填充，总耗时 = 最慢请求。
    try {
      const profileRes = await truthnetAPI.getCompanyProfile(code);
      if (loadForCode.current !== myCode) return; // 已切走，忽略旧请求结果
      setProfile(profileRes.data);
    } catch (err) {
      loadInFlight.current = false;
      if (loadForCode.current === myCode) {
        setError(err instanceof Error ? err.message : "加载失败");
      }
      return;
    }

    const others = [
      truthnetAPI
        .getFinance(code)
        .then((res) => {
          if (loadForCode.current !== myCode) return;
          setFinancialAnomalies(res.data?.rules || []);
          setFinanceQuality(res.data?.data_quality || null);
        })
        .catch((err) => {
          if (loadForCode.current !== myCode) return;
          console.warn("财务数据加载失败:", err);
        })
        .finally(() => {
          if (loadForCode.current === myCode) setFinanceLoaded(true);
        }),
      truthnetAPI.getEquity(code).then((res) => {
        if (loadForCode.current !== myCode) return;
        setEquityData(res.data);
      }),
      truthnetAPI
        .getEvents(code, true, riskData?.as_of)
        .then((res) => {
          if (loadForCode.current !== myCode) return;
          setSentimentEvents(res.data?.timeline || []);
          setEventClusters(res.data?.event_clusters || []);
          setAnnouncementsAvailable(res.data?.announcements_available ?? null);
        })
        .catch((err) => {
          if (loadForCode.current !== myCode) return;
          console.warn("舆情数据加载失败:", err);
        })
        .finally(() => {
          if (loadForCode.current === myCode) setEventsLoaded(true);
        }),
      truthnetAPI.getRisk(code).then((res) => {
        if (loadForCode.current !== myCode) return;
        setRiskData(res.data);
        const allChains = res.data?.derivation_chains || [];
        setDerivationChains([
          ...allChains.filter((c) => c.conclusion_type === "risk_level"),
          ...allChains
            .filter((c) => c.conclusion_type === "pattern_match")
            .slice(0, 3),
        ]);
      }),
      truthnetAPI.getRuleDefinitions().then((res) => {
        if (loadForCode.current !== myCode) return;
        setRuleDefinitions(res.data?.rules || []);
        setRuleDefsOverridden(res.data?.is_overridden ?? false);
      }),
      truthnetAPI.getImpactAdvice(code).then((res) => {
        if (loadForCode.current !== myCode) return;
        setImpactAdvice(res.data);
      }),
    ];
    // 其余单个请求失败不整页报错（区块保持空/占位），仅记录。
    others.forEach((p) =>
      p.catch((err) => console.warn("画像页数据加载失败:", err)),
    );
    setImpactAdviceLoading(true);
    await Promise.allSettled(others);
    if (loadForCode.current !== myCode) return; // 已切走：复位交给新公司加载
    setImpactAdviceLoading(false);
    setLoading(false);
    loadInFlight.current = false;
  };

  const handleNavClick = (id: string) => {
    setActiveSection(id);
    const ref = sectionRefs[id as keyof typeof sectionRefs];
    ref.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const openEvidenceDetails = async (evidenceIds: string[], title: string) => {
    const uniqueEvidenceIds = [...new Set(evidenceIds)];
    setEvidenceDialogTitle(title);
    setEvidenceDialogItems(
      uniqueEvidenceIds.map((evidenceId) => ({ evidenceId })),
    );
    setEvidenceDialogLoading(true);
    setEvidenceDialogOpen(true);
    const results = await Promise.allSettled(
      uniqueEvidenceIds.map((evidenceId) =>
        truthnetAPI.getEvidence(evidenceId),
      ),
    );
    setEvidenceDialogItems(
      results.map((result, index) => ({
        evidenceId: uniqueEvidenceIds[index],
        ...(result.status === "fulfilled"
          ? { data: result.value.data }
          : {
              ...(uniqueEvidenceIds[index]?.startsWith("ev_fin_")
                ? { isGenerated: true }
                : {
                    error:
                      result.reason instanceof Error
                        ? result.reason.message
                        : "证据加载失败",
                  }),
            }),
      })),
    );
    setEvidenceDialogLoading(false);
  };

  const handleViewRuleEvidence = (ruleId: string) => {
    const rule = financialAnomalies.find((item) => item.rule_id === ruleId);
    if (rule && (rule.evidence_ids?.length ?? 0) > 0) {
      void openEvidenceDetails(
        rule.evidence_ids,
        `${rule.rule_name || rule.rule_id} · 证据详情`,
      );
    }
  };

  // Rules of Hooks：以下全部派生计算与 useMemo 必须在任何 early return
  // （loading/error 分支）之前注册，否则第二次渲染 Hook 数量不一致，
  // React 报 "Rendered more hooks than during the previous render"。
  const riskConfig =
    riskLevelConfig[(riskData?.risk_level || "unknown") as RiskLevel];
  // A3（8/9 老师要求）：触发的规则（风险提示集中展示 + 财务区筛选口径一致）
  const triggeredRules = financialAnomalies.filter(
    (r) => r.status === "triggered",
  );

  // 核心结论压缩：只展示 overall 风险链 + 风险模式链；
  // 逐规则推导链与财务异常区重复，不再在概览区完整展开。
  const overallConclusion = derivationChains.find(
    (c) => c.conclusion_type === "risk_level",
  );
  const patternConclusions = derivationChains
    .filter((c) => c.conclusion_type === "pattern_match")
    .slice(0, 3);
  const coreConclusionChains = [
    overallConclusion,
    ...patternConclusions,
  ].filter((c): c is NonNullable<typeof c> => Boolean(c));
  const patternMatches = riskData?.pattern_matches || [];
  const patternByConclusionId = new Map<
    string,
    (typeof patternMatches)[number]
  >(patternMatches.map((p) => [`pattern:${p.pattern_id}`, p]));

  // 2026-08-16 口径整改：覆盖判定改用"真实数据存在性"，废弃后端
  // coverage_ratio（其为模块执行成功占比，曾把"舆情无公告数据"算进 100%）。
  const financeHasData = (financeQuality?.periods_available ?? 0) > 0;
  const equityHasData = (equityData?.nodes?.length ?? 0) > 0;
  const eventsHasData =
    (announcementsAvailable ?? false) ||
    eventClusters.length > 0 ||
    sentimentEvents.length > 0;
  const benchmarksHasData = financialAnomalies.some((r) =>
    (r.industry_metrics ?? []).some((m) => (m.sample_count ?? 0) > 0),
  );
  const coverageGaps: string[] = [];
  if (!financeHasData) {
    coverageGaps.push("财务无报表数据");
  } else if (
    financeQuality &&
    financeQuality.periods_available < financeQuality.periods_requested
  ) {
    coverageGaps.push(
      `财务 ${financeQuality.periods_available}/${financeQuality.periods_requested} 期`,
    );
  }
  if (!equityHasData) coverageGaps.push("股权无数据");
  if (!eventsHasData) coverageGaps.push("舆情无公告数据");
  if (!benchmarksHasData) coverageGaps.push("行业基准无样本");
  const coverageModulesText = riskData
    ? `${[financeHasData, equityHasData, eventsHasData, benchmarksHasData].filter(Boolean).length}/4 有数据`
    : "-";
  const coverageStatusText = !riskData
    ? "-"
    : coverageGaps.length === 0
      ? "完整"
      : "部分覆盖";
  const coverageGapText =
    coverageGaps.length > 0 ? `数据说明：${coverageGaps.join(" · ")}` : "";

  const profileBrief = useMemo(() => {
    if (!profile) return null;
    const level = (riskData?.risk_level || "unknown") as RiskLevel;
    const levelLabel = riskLevelConfig[level]?.label || "未知";
    const levelColor =
      riskLevelConfig[level]?.color || riskLevelConfig.unknown.color;
    const financeLine = financeHasData
      ? triggeredRules.length > 0
        ? `财务发现 ${triggeredRules.length} 条异常信号`
        : "财务未见明显异常信号"
      : "财务数据不足";
    const equityLine = equityHasData
      ? equityData?.paths?.length
        ? `股权穿透已识别 ${equityData.paths.length} 条路径`
        : "股权数据存在但未形成稳定穿透路径"
      : "股权数据不足";
    const eventLine = eventsHasData
      ? impactAdvice?.overall_advice
        ? `舆情已形成影响结论（${impactAdvice.evidence_count} 条可回查证据）`
        : sentimentEvents.length > 0
          ? `舆情已有 ${sentimentEvents.length} 条事件记录`
          : "舆情暂无明显事件"
      : "舆情数据不足";
    const dateText = riskData?.as_of || "截止日暂无";
    const stance =
      level === "red" || level === "orange" || level === "yellow"
        ? "偏谨慎"
        : level === "green"
          ? "相对平稳"
          : "待补充数据后再判断";
    return {
      levelLabel,
      levelColor,
      dateText,
      stance,
      financeLine,
      equityLine,
      eventLine,
      note:
        coverageGapText ||
        (impactAdvice?.overall_advice
          ? impactAdvice.overall_advice.slice(0, 120)
          : ""),
    };
  }, [
    profile,
    riskData?.risk_level,
    riskData?.as_of,
    financeHasData,
    equityHasData,
    eventsHasData,
    triggeredRules.length,
    equityData?.paths?.length,
    impactAdvice?.evidence_count,
    sentimentEvents.length,
    coverageGapText,
    impactAdvice?.overall_advice,
  ]);
  const impactAdviceWarnings = impactAdvice
    ? formatImpactAdviceWarnings(impactAdvice.method, impactAdvice.warnings)
    : [];
  const impactSignalSegments = (impactAdvice?.segments || []).filter(
    (segment) =>
      !["财务建议", "股权建议", "舆情建议", "综合建议"].includes(segment.title),
  );
  const verificationNavigation = impactAdvice?.verification_navigation || [];

  // 8/23 分步渲染：profile 未到达时显示加载中（不得落入「加载失败」分支——
  // 首次渲染 profile=null 且 error=null，需区分加载中与加载失败）
  if (!profile && !error) {
    return (
      <div className="flex h-screen bg-background">
        <div className="w-40 border-r border-border p-4">
          <Skeleton className="h-full w-full" />
        </div>
        <div className="flex-1 overflow-auto p-6">
          <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            正在加载公司信息…
          </div>
          <Skeleton className="mb-4 h-8 w-64" />
          <Skeleton className="mb-4 h-32 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <Card className="w-96">
          <CardContent className="pt-6 text-center">
            <p className="text-destructive">{error || "加载失败"}</p>
            <Button className="mt-4" onClick={() => navigate(-1)}>
              返回
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100dvh-3.5rem)] min-h-0 bg-background">
      {/* 左侧锚点导航 */}
      <div className="w-40 border-r border-border bg-card" data-no-print>
        <div className="p-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/")}
            className="mb-4 w-full justify-start"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            返回
          </Button>
          <nav className="space-y-1">
            {navItems.map((item) => (
              <button
                key={item.id}
                onClick={() => handleNavClick(item.id)}
                className={cn(
                  "flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                  activeSection === item.id
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                )}
              >
                <i
                  className={cn(
                    "ph ph-duotone text-[15px] leading-none",
                    item.ph,
                    activeSection === item.id
                      ? "opacity-100"
                      : "opacity-70",
                  )}
                />
                {item.label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* 右侧内容区 */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScrollSync}
        className="flex-1 overflow-auto"
      >
        <div className="mx-auto max-w-5xl p-6">
          {/* 概览区块 · Hero 头部 */}
          <div ref={sectionRefs.overview} className="mb-8">
            <Reveal>
              <div className="tn-card-sheen relative mb-6 overflow-hidden rounded-2xl border border-border bg-card p-6 sm:p-8">
                {/* Unsplash 素材：深色 K 线图，浅色主题下大幅降透明度保持可读性 */}
                <img
                  src="/assets/hero-finance.jpg"
                  alt=""
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-0 h-full w-full object-cover opacity-[0.10] dark:opacity-[0.32]"
                />
                <div
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-0 bg-gradient-to-r from-card via-card/90 to-card/35 dark:via-card/75 dark:to-card/25"
                />
                <div
                  aria-hidden="true"
                  className="tn-noise pointer-events-none absolute inset-0 opacity-[0.05] dark:opacity-[0.09]"
                />
                <div
                  aria-hidden="true"
                  className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-primary/10 blur-3xl"
                />
                <div
                  aria-hidden="true"
                  className="pointer-events-none absolute -bottom-20 left-1/3 h-40 w-40 rounded-full bg-primary/[0.06] blur-3xl"
                />
                <div className="relative text-card-foreground">
                  <p className="mb-3 font-mono text-[11px] uppercase tracking-[0.3em] text-muted-foreground sm:text-xs">
                    财报反欺诈画像 · 多源交叉验证
                  </p>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                    <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
                      {profile.sec_name}
                    </h1>
                    <Badge className={riskConfig.color}>
                      {riskConfig.label}
                    </Badge>
                    <span className="font-mono text-sm text-muted-foreground">
                      {profile.wind_code}
                    </span>
                    {riskData !== null && (
                      <span className="flex items-baseline gap-1.5 font-mono text-sm text-muted-foreground">
                        <span className="text-[10px] uppercase tracking-[0.2em]">
                          score
                        </span>
                        <CountUpNumber
                          value={riskData.overall_score}
                          decimals={3}
                          active={riskData !== null}
                          className="text-base font-semibold text-foreground"
                        />
                      </span>
                    )}
                  </div>
                  <div className="mt-5 flex flex-wrap items-center gap-2">
                    <ExportSnapshotButton className="gap-1.5" />
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-1.5"
                      data-no-print
                      onClick={handleGenerateReport}
                      disabled={reportCreating}
                    >
                      {reportCreating ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <FileText className="h-3.5 w-3.5" />
                      )}
                      生成报告
                    </Button>
                  </div>
                </div>
              </div>
            </Reveal>
            <Card className="overflow-hidden">
              <div className="bg-gradient-to-r from-muted/30 to-muted/10 px-6 py-3 border-b border-border/50">
                <div className="flex items-center gap-2">
                  <Shield className="h-4 w-4 text-primary" />
                  <span className="text-sm font-semibold text-foreground">
                    风险概览
                  </span>
                </div>
              </div>
              <CardContent className="pt-5 space-y-4">
                {riskData === null ? (
                  <div className="space-y-3 py-2">
                    <Skeleton className="h-12 w-full" />
                    <Skeleton className="h-12 w-full" />
                    <Skeleton className="h-16 w-full" />
                  </div>
                ) : (
                  <>
                    {/* 风险概览指标（bento 网格） */}
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                      <div className="tn-card-sheen tn-lift relative col-span-2 flex flex-col justify-center overflow-hidden rounded-xl border border-border p-5">
                        <img
                          src="/assets/hero-abstract.jpg"
                          alt=""
                          aria-hidden
                          className="pointer-events-none absolute inset-0 h-full w-full object-cover opacity-[0.07] mix-blend-luminosity dark:opacity-[0.14]"
                        />
                        <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/15 to-primary/5" />
                        <p className="relative mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                          综合风险等级
                        </p>
                        <div className="relative flex flex-wrap items-center gap-3">
                          <p className="text-3xl font-bold leading-none text-foreground">
                            {riskConfig.label}
                          </p>
                          <Badge className={riskConfig.color}>
                            {riskConfig.label}
                          </Badge>
                        </div>
                      </div>
                      <div className="tn-card-sheen tn-lift flex flex-col justify-center rounded-xl bg-muted/50 p-5 text-center">
                        <p className="mb-1 text-xs text-muted-foreground">
                          触发规则数
                        </p>
                        <p className="text-2xl font-bold">
                          <CountUpNumber
                            value={triggeredRules.length}
                            active={riskData !== null}
                          />
                        </p>
                      </div>
                      <div className="tn-card-sheen tn-lift flex flex-col justify-center rounded-xl bg-muted/50 p-5 text-center">
                        <p className="mb-1 text-xs text-muted-foreground">
                          舆情事件数
                        </p>
                        <p className="text-2xl font-bold">
                          <CountUpNumber
                            value={sentimentEvents.length}
                            active={eventsHasData}
                          />
                        </p>
                      </div>
                      {/* A3（8/9 老师要求）：数据截止日 / 数据模块 / 覆盖状态
                      （2026-08-16 口径整改：截止日由后端从库内真实期次推导；
                      覆盖率不再显示百分比，改为真实数据模块数 x/4） */}
                      <div className="tn-card-sheen tn-lift flex flex-col justify-center rounded-xl border border-border/60 p-4 text-center">
                        <p className="mb-1 text-xs text-muted-foreground">
                          数据截止日
                        </p>
                        <p className="text-sm font-semibold">
                          {riskData?.as_of || "-"}
                        </p>
                      </div>
                      <div className="tn-card-sheen tn-lift flex flex-col justify-center rounded-xl border border-border/60 p-4 text-center">
                        <p className="mb-1 text-xs text-muted-foreground">
                          数据模块
                        </p>
                        <p className="text-sm font-semibold">
                          {coverageModulesText}
                        </p>
                      </div>
                      <div className="tn-card-sheen tn-lift col-span-2 flex flex-col justify-center rounded-xl border border-border/60 p-4 text-center">
                        <p className="mb-1 text-xs text-muted-foreground">
                          覆盖状态
                        </p>
                        <p className="text-sm font-semibold">
                          {coverageStatusText}
                        </p>
                      </div>
                    </div>
                    {coverageGapText && (
                      <p className="rounded-md border border-dashed border-border/60 p-2 text-xs text-muted-foreground">
                        {coverageGapText}
                      </p>
                    )}

                    {profileBrief && (
                      <div className="rounded-md border border-border/60 bg-background p-4 space-y-3">
                        <div className="flex flex-wrap items-center gap-2 text-xs">
                          <Badge className={profileBrief.levelColor}>
                            {profileBrief.levelLabel}
                          </Badge>
                          <span className="text-muted-foreground">
                            简要分析
                          </span>
                          <span className="text-muted-foreground">
                            数据截止：{profileBrief.dateText}
                          </span>
                        </div>
                        <p className="text-sm leading-6 text-foreground">
                          {profile.sec_name}整体{profileBrief.stance}；
                          {profileBrief.financeLine}；{profileBrief.equityLine}
                          ；{profileBrief.eventLine}。
                        </p>
                        {profileBrief.note && (
                          <p className="text-xs leading-5 text-muted-foreground">
                            {profileBrief.note}
                          </p>
                        )}
                      </div>
                    )}

                    {/* A3：top 触发规则（点击跳转财务异常区） */}
                    {triggeredRules.length > 0 && (
                      <div className="rounded-md border border-border/60 p-3">
                        <p className="text-xs text-muted-foreground mb-2">
                          主要风险信号（点击查看详情）
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {triggeredRules.slice(0, 5).map((r) => (
                            <button
                              key={r.rule_id}
                              onClick={() => handleNavClick("financial")}
                              className={cn(
                                "flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors",
                                "border-border/60 bg-background hover:border-primary/50 hover:bg-muted/50",
                              )}
                            >
                              <span className="text-foreground">
                                {r.rule_name || r.rule_id}
                              </span>
                              <span
                                className={`rounded-full px-1.5 py-0.5 ${getRiskBadgeStyle(r.severity)}`}
                              >
                                {RISK_SEVERITY_LABELS[r.severity] ??
                                  RISK_SEVERITY_LABELS.unknown}
                              </span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* A3：risk warnings 集中展示 */}
                    {(riskData?.warnings?.length ?? 0) > 0 && (
                      <div className="rounded-md border border-yellow-500/40 bg-yellow-500/5 p-3 space-y-1">
                        {riskData!.warnings.map((w, wi) => (
                          <p
                            key={wi}
                            className="flex items-start gap-1.5 text-xs text-muted-foreground"
                          >
                            <AlertTriangle className="h-3.5 w-3.5 text-yellow-600 shrink-0 mt-0.5" />
                            {w}
                          </p>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          </div>

          {/* 核心结论区块 (Phase E P0-1) */}
          <div ref={sectionRefs.conclusions} className="mb-8">
            <Reveal>
              <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-foreground">
                <i className="ph ph-duotone ph-file-text text-[20px] text-primary" />
                核心结论
              </h2>
            </Reveal>
            {riskData === null ? (
              <Card>
                <CardContent className="py-6 space-y-3">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-16 w-full" />
                </CardContent>
              </Card>
            ) : derivationChains.length > 0 ? (
              <div className="space-y-3">
                {derivationChains.map((chain, ci) => (
                  <InsightDisclosure
                    key={ci}
                    severity={
                      // 后端 derivation_chains 用色彩词表（red/orange/yellow/blue/green），映射到信封皮肤
                      chainSeveritySkin(chain.risk_level)
                    }
                    defaultOpen={ci === 0}
                    title={<span>{chain.conclusion}</span>}
                    meta={
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${getRiskBadgeStyle(chain.risk_level)}`}
                      >
                        {RISK_SEVERITY_LABELS[chain.risk_level] ??
                          RISK_SEVERITY_LABELS.unknown}
                      </span>
                    }
                  >
                    <div className="space-y-3">
                      {(chain.conclusion_type === "risk_level"
                        ? chain.signals.slice(0, 3)
                        : []
                      ).map((signal, si) => (
                        <div
                          key={si}
                          className="rounded-lg border bg-muted/30 p-3"
                        >
                          <div className="mb-1 flex items-center justify-between">
                            <span className="text-sm font-medium">
                              {signal.label}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              {RISK_SEVERITY_LABELS[signal.severity] ??
                                RISK_SEVERITY_LABELS.unknown}
                            </span>
                          </div>
                          <p className="mb-2 text-sm text-muted-foreground">
                            {signal.explanation}
                          </p>
                          {signal.industry_percentile != null && (
                            <p className="mb-1 text-xs text-muted-foreground">
                              行业分位: {signal.industry_percentile}%
                            </p>
                          )}
                        </div>
                      ))}
                      {chain.conclusion_type === "pattern_match" &&
                        (() => {
                          const pattern = patternByConclusionId.get(
                            chain.conclusion_id,
                          );
                          if (!pattern) return null;
                          return (
                            <div className="rounded-lg border border-border/60 bg-muted/30 p-3 text-xs space-y-1.5">
                              <div className="flex flex-wrap items-center gap-2 text-muted-foreground">
                                <span>置信度：{pattern.confidence || "-"}</span>
                                {pattern.phase && (
                                  <span>阶段：{pattern.phase}</span>
                                )}
                                {pattern.triggered_rules.length > 0 && (
                                  <span>
                                    关联规则：
                                    {pattern.triggered_rules.join("、")}
                                  </span>
                                )}
                              </div>
                              {pattern.reasoning && (
                                <p className="leading-5">
                                  匹配理由：{pattern.reasoning}
                                </p>
                              )}
                              {pattern.alternative_explanation && (
                                <p className="leading-5">
                                  替代解释：{pattern.alternative_explanation}
                                </p>
                              )}
                              {pattern.regulatory_hint && (
                                <p className="leading-5 text-amber-700 dark:text-amber-400">
                                  监管提示：{pattern.regulatory_hint}
                                </p>
                              )}
                            </div>
                          );
                        })()}
                    </div>
                  </InsightDisclosure>
                ))}
              </div>
            ) : (
              <Card className="border-dashed">
                <CardContent className="py-8 text-center text-muted-foreground">
                  <p>暂无结论数据</p>
                  <p className="text-xs mt-1">
                    选择公司后将自动加载风险分析结论
                  </p>
                </CardContent>
              </Card>
            )}
          </div>

          <Separator className="my-6" />

          <div ref={sectionRefs.impact} className="mb-8">
            <Reveal>
              <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-foreground">
                <i className="ph ph-duotone ph-shield-star text-[20px] text-primary" />
                影响与建议
              </h2>
            </Reveal>
            {impactAdviceLoading ? (
              <Card>
                <CardContent className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  正在聚合财务、股权与舆情信号
                </CardContent>
              </Card>
            ) : impactAdvice ? (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <Badge
                    className={
                      riskLevelConfig[
                        (impactAdvice.risk_level || "unknown") as RiskLevel
                      ].color
                    }
                  >
                    {
                      riskLevelConfig[
                        (impactAdvice.risk_level || "unknown") as RiskLevel
                      ].label
                    }
                  </Badge>
                  <span>{impactAdvice.as_of || "数据截止日暂无"}</span>
                  <span>{impactAdvice.evidence_count} 条可回查证据</span>
                </div>

                {verificationNavigation.length > 0 && (
                  <Card className="border-primary/30 bg-primary/[0.03]">
                    <CardHeader className="pb-3">
                      <CardTitle className="flex items-center gap-2 text-base">
                        <Shield className="h-4 w-4 text-primary" />
                        优先核查清单
                        <Badge
                          variant="outline"
                          className="text-[11px] font-normal"
                        >
                          规则排序 · 人工核验
                        </Badge>
                      </CardTitle>
                      <p className="text-xs leading-5 text-muted-foreground">
                        系统先说明风险点与量化依据，再给出固定核查步骤；判断结论由分析人员结合原始披露作出。
                      </p>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {verificationNavigation.map((item, index) => (
                        <div
                          key={item.rule_id}
                          className={`rounded-md border p-3 ${getVerificationCardStyle(item.severity)}`}
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">
                              {index + 1}
                            </span>
                            <p className="text-sm font-semibold text-foreground">
                              {item.rule_id} {item.rule_name}
                            </p>
                            <Badge className={getRiskBadgeStyle(item.severity)}>
                              {RISK_SEVERITY_LABELS[item.severity] ??
                                RISK_SEVERITY_LABELS.unknown}
                            </Badge>
                          </div>
                          {item.explanation && (
                            <p className="mt-2 text-sm leading-6 text-muted-foreground">
                              <span className="font-semibold text-foreground">
                                风险点：
                              </span>
                              {item.explanation}
                            </p>
                          )}
                          {item.quantified_context && (
                            <p className="mt-2 rounded-md border border-primary/10 bg-background/80 px-2.5 py-2 text-xs font-medium leading-5 text-foreground shadow-sm">
                              {item.quantified_context}
                            </p>
                          )}
                          {item.actions.length > 0 && (
                            <div className="mt-3">
                              <p className="text-xs font-semibold text-foreground">
                                建议核查
                              </p>
                              <ol className="mt-1.5 space-y-1.5 text-xs leading-5 text-foreground">
                                {item.actions.map((action, actionIndex) => (
                                  <li
                                    key={action}
                                    className="flex items-start gap-2"
                                  >
                                    <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[10px] font-bold text-primary">
                                      {actionIndex + 1}
                                    </span>
                                    <span className="font-medium">
                                      {action}
                                    </span>
                                  </li>
                                ))}
                              </ol>
                            </div>
                          )}
                          {item.evidence_ids.length > 0 && (
                            <Button
                              variant="link"
                              size="sm"
                              className="mt-2 h-auto p-0 text-xs"
                              onClick={() =>
                                void openEvidenceDetails(
                                  item.evidence_ids,
                                  `${item.rule_id} ${item.rule_name} · 核查证据`,
                                )
                              }
                            >
                              查看 {item.evidence_ids.length} 条相关证据
                            </Button>
                          )}
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                )}

                <Card className="border-primary/25 border-l-4 border-l-primary bg-primary/[0.025]">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-semibold text-foreground">
                      {impactAdvice.method === "llm"
                        ? "AI 辅助综合研判"
                        : "系统综合摘要"}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <MarkdownRenderer
                      content={impactAdvice.overall_advice}
                      className="text-sm leading-6 text-foreground [&_strong]:font-semibold [&_strong]:text-primary"
                    />
                  </CardContent>
                </Card>

                {impactSignalSegments.length > 0 && (
                  <div className="space-y-3 rounded-md border border-border/60 p-4">
                    <p className="text-sm font-medium text-foreground">
                      补充信号与证据
                    </p>
                    {impactSignalSegments.map((segment, index) => (
                      <div
                        key={`${segment.source_module}-${index}`}
                        className="border-l-2 border-primary/40 pl-4"
                      >
                        <p className="text-sm font-medium text-foreground">
                          {segment.title}
                        </p>
                        <p className="mt-1 text-sm leading-6 text-muted-foreground">
                          {segment.detail}
                        </p>
                        {segment.evidence_ids.length > 0 && (
                          <Button
                            variant="link"
                            size="sm"
                            className="mt-1 h-auto p-0 text-xs"
                            onClick={() =>
                              void openEvidenceDetails(
                                segment.evidence_ids,
                                `${segment.title} · 证据详情`,
                              )
                            }
                          >
                            查看 {segment.evidence_ids.length} 条证据
                          </Button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                {impactAdviceWarnings.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    {impactAdviceWarnings.join("；")}
                  </p>
                )}
              </div>
            ) : (
              <Card className="border-dashed">
                <CardContent className="py-6 text-sm text-muted-foreground">
                  当前未生成可回查的综合影响建议。
                </CardContent>
              </Card>
            )}
          </div>

          <Separator className="my-6" />

          {/* 财务规则区块 - 使用 RuleCard 组件 */}
          <div ref={sectionRefs.financial} className="mb-8">
            <Reveal>
              <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-foreground">
                <i className="ph ph-duotone ph-chart-bar-up text-[20px] text-primary" />
                财务异常
              </h2>
            </Reveal>
            {!financeLoaded ? (
              <Card>
                <CardContent className="py-6 space-y-3">
                  <Skeleton className="h-14 w-full" />
                  <Skeleton className="h-24 w-full" />
                  <Skeleton className="h-24 w-full" />
                </CardContent>
              </Card>
            ) : financialAnomalies.length > 0 ? (
              <>
                <FinanceTrendOverview rules={financialAnomalies} />
                <div className="grid gap-2.5 md:grid-cols-2">
                  {financialAnomalies
                    .filter((a) => a.status === "triggered")
                    .map((anomaly, i) => (
                      <div
                        key={anomaly.rule_id}
                        className="tn-rise"
                        style={{ animationDelay: `${i * 70}ms` }}
                      >
                        <RuleCard
                          rule={anomaly}
                          onViewEvidence={handleViewRuleEvidence}
                          evidenceSummaries={(anomaly.evidence_ids || [])
                            .map((id) => ruleEvidenceSummary[id])
                            .filter((x): x is RuleEvidenceSummary => Boolean(x))}
                        />
                      </div>
                    ))}
                </div>
                {financialAnomalies.some((a) => a.status !== "triggered") && (
                  <div className="tn-sweep relative mt-3 overflow-hidden rounded-lg border border-border/50 bg-muted/25 px-3 py-2.5">
                    <div className="mb-1.5 flex items-center gap-2">
                      <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted-foreground">
                        未触发 · {financialAnomalies.filter((a) => a.status !== "triggered").length} 项规则运行正常
                      </span>
                      <span className="h-px flex-1 bg-gradient-to-r from-border to-transparent" />
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {financialAnomalies
                        .filter((a) => a.status !== "triggered")
                        .map((a) => (
                          <button
                            key={a.rule_id}
                            onClick={() => handleViewRuleEvidence(a.rule_id)}
                            className="group inline-flex items-center gap-1.5 rounded-full border border-border/60 bg-card/80 px-2.5 py-1 text-[11px] text-muted-foreground transition-all hover:border-primary/40 hover:text-foreground"
                          >
                            <span
                              className={`size-1.5 rounded-full ${
                                a.status === "insufficient_data"
                                  ? "bg-yellow-500/70"
                                  : a.status === "not_applicable"
                                    ? "bg-gray-400/70"
                                    : "bg-emerald-500/80 shadow-[0_0_6px_rgba(16,185,129,0.6)]"
                              }`}
                            />
                            {a.rule_name || a.rule_id}
                            <span className="font-mono text-[10px] opacity-60 group-hover:opacity-100">
                              {a.status === "insufficient_data"
                                ? "数据不足"
                                : a.status === "not_applicable"
                                  ? "不适用"
                                  : "通过"}
                            </span>
                          </button>
                        ))}
                    </div>
                  </div>
                )}
                {ruleDefinitions.length > 0 && (
                  <div className="mt-4 rounded-lg border border-border/60 bg-muted/20 p-4">
                    <div className="mb-3 flex items-center gap-2 flex-wrap">
                      <SlidersHorizontal className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm font-medium">规则配置参数</span>
                      <span className="text-xs text-muted-foreground">
                        参数决定触发阈值
                      </span>
                      {ruleDefsOverridden && (
                        <Badge
                          variant="outline"
                          className="text-[11px] text-amber-600 border-amber-500/40"
                        >
                          已使用自定义阈值
                        </Badge>
                      )}
                      <div className="ml-auto flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 text-xs"
                          disabled={configResetting || !ruleDefsOverridden}
                          onClick={handleResetRuleConfig}
                        >
                          {configResetting ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : null}
                          重置
                        </Button>
                        <Button
                          size="sm"
                          className="h-7 text-xs gap-1"
                          disabled={configSaving}
                          onClick={handleSaveRuleConfig}
                        >
                          {configSaving ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : null}
                          保存并刷新
                        </Button>
                      </div>
                    </div>
                    <p className="mb-3 text-xs text-muted-foreground">
                      单位说明：%
                      表示比例或同比增速；百分点表示两个百分比之间的差值。
                    </p>
                    {configError && (
                      <p className="mb-2 text-xs text-destructive">
                        {configError}
                      </p>
                    )}
                    {/* 8/23 可读性：修改效果说明 */}
                    <p className="mb-3 rounded-md border border-dashed border-border/60 bg-background/40 px-3 py-2 text-[11px] leading-5 text-muted-foreground">
                      这里列出全部 7
                      条反欺诈规则的判定参数（即「什么情况算触发预警」的临界值）。
                      修改后点击「保存并刷新」，财务异常、风险评分与影响建议将按新参数重新计算；
                      点击「重置」恢复系统默认值。绿色徽标=已触发，灰色=未触发，橙色=数据不足。
                    </p>
                    <div className="space-y-3">
                      {/* 8/23：配置区显示全部规则（参数决定触发阈值，不只显示已触发）；
                        触发状态以徽标标注 */}
                      {ruleDefinitions.map((def) => {
                        const rule = financialAnomalies.find(
                          (r) => r.rule_id === def.rule_id,
                        );
                        return (
                          <div
                            key={def.rule_id}
                            className="rounded-md border border-border/60 bg-background/60 p-3"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-medium">
                                  {def.name}
                                </span>
                                <span className="text-xs text-muted-foreground">
                                  {def.rule_id}
                                </span>
                              </div>
                              {rule ? (
                                <span
                                  className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${getRiskBadgeStyle(rule.severity || "unknown")}`}
                                >
                                  {RULE_STATUS_LABELS[rule.status] ??
                                    rule.status}
                                </span>
                              ) : (
                                <span className="rounded-full px-2 py-0.5 text-[11px] font-medium bg-gray-500/10 text-gray-600">
                                  未执行
                                </span>
                              )}
                            </div>
                            {def.description && (
                              <p className="mt-1 text-xs text-muted-foreground">
                                {def.description}
                              </p>
                            )}
                            {Object.keys(def.thresholds).length > 0 && (
                              <div className="mt-2 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                                {Object.entries(def.thresholds).map(([k]) => {
                                  const param = def.parameters.find(
                                    (p) => p.key === k,
                                  );
                                  return (
                                    <label
                                      key={k}
                                      className="flex items-center justify-between gap-2 rounded border border-border/60 bg-background px-2 py-1"
                                    >
                                      <span
                                        className="min-w-0 flex-1"
                                        title={`${k}${param?.description ? `（${param.description}）` : ""}`}
                                      >
                                        <span className="block truncate text-xs text-foreground">
                                          {param?.description || k}
                                        </span>
                                      </span>
                                      <span className="flex items-center gap-1 shrink-0">
                                        <input
                                          type="number"
                                          step="any"
                                          value={
                                            draftThresholds[def.rule_id]?.[k] ??
                                            String(def.thresholds[k] ?? "")
                                          }
                                          onChange={(e) =>
                                            setDraftThresholds((prev) => ({
                                              ...prev,
                                              [def.rule_id]: {
                                                ...(prev[def.rule_id] || {}),
                                                [k]: e.target.value,
                                              },
                                            }))
                                          }
                                          className="w-20 rounded border border-border/60 bg-background px-1.5 py-0.5 text-right text-xs"
                                        />
                                        {param?.unit && (
                                          <span className="text-[10px] text-muted-foreground">
                                            {RULE_UNIT_LABELS[param.unit] ??
                                              param.unit}
                                          </span>
                                        )}
                                      </span>
                                    </label>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <Card>
                <CardContent className="py-8 text-center text-muted-foreground">
                  暂无财务异常数据
                </CardContent>
              </Card>
            )}
          </div>

          <Separator className="my-6" />

          {/* 股权穿透区块：移除缺列关联方表，保留多跳分层穿透图 */}
          <div ref={sectionRefs.equity} className="mb-8">
            <Reveal>
              <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-foreground">
                <i className="ph ph-duotone ph-tree-structure text-[20px] text-primary" />
                股权穿透图
              </h2>
            </Reveal>
            {equityData === null ? (
              <Card>
                <CardContent className="py-6 space-y-3">
                  <Skeleton className="h-14 w-full" />
                  <Skeleton className="h-48 w-full" />
                </CardContent>
              </Card>
            ) : equityData ? (
              <>
                <Card>
                  <CardContent className="p-4">
                    <RelatedPartyTable equityData={equityData} />

                    {/* 间接持股链路：消费后端 equity_chains，补齐多跳最终持股视图 */}
                    {(equityData.equity_chains?.length ?? 0) > 0 && (
                      <div className="mb-4 rounded-lg border border-border/60 bg-muted/20 p-3">
                        <div className="mb-2 flex items-center justify-between">
                          <span className="text-xs font-semibold text-foreground">
                            间接持股链路（多跳）
                          </span>
                          <span className="text-[10px] text-muted-foreground">
                            表格仅直接持股；最终持股=各跳比例连乘，多跳时会稀释到极小值
                          </span>
                        </div>
                        <div className="space-y-1.5">
                          {(
                            equityData.equity_chains as Array<
                              Record<string, unknown>
                            >
                          )
                            .slice(0, 6)
                            .map((chain, index) => {
                              const names = Array.isArray(chain.path_names)
                                ? chain.path_names.map(String).filter(Boolean)
                                : [];
                              const pct =
                                typeof chain.final_control_pct === "number"
                                  ? chain.final_control_pct
                                  : null;
                              const nodeIds = Array.isArray(chain.node_ids)
                                ? chain.node_ids.map(String)
                                : [];
                              const edgeIds = Array.isArray(chain.edge_ids)
                                ? chain.edge_ids.map(String)
                                : [];
                              const firstEdge = equityData.edges.find(
                                (edge) => {
                                  if (
                                    edgeIds.length > 0 &&
                                    edge.relationship_id &&
                                    edgeIds[0] === edge.relationship_id
                                  ) {
                                    return true;
                                  }
                                  return (
                                    nodeIds.length >= 2 &&
                                    edge.source === nodeIds[0] &&
                                    edge.target === nodeIds[1]
                                  );
                                },
                              );
                              const firstPct = firstEdge?.ownership_pct ?? null;
                              const pathType = String(
                                chain.path_type || "ownership",
                              );
                              const riskLevel = String(
                                chain.risk_level || "green",
                              );
                              return (
                                <div
                                  key={String(chain.chain_id || index)}
                                  className="rounded-md border border-border/50 bg-background px-2.5 py-2"
                                >
                                  <div className="flex items-start justify-between gap-3">
                                    <p className="min-w-0 flex-1 text-xs leading-5 text-foreground">
                                      {names.length > 0
                                        ? names.join(" → ")
                                        : "未命名链路"}
                                    </p>
                                    <span className="shrink-0 text-xs font-semibold text-foreground">
                                      {pct != null
                                        ? `${pathType === "control" ? "最终控制" : "最终持股"} ${formatChainPct(pct)}${firstPct != null ? ` · 首层 ${formatChainPct(firstPct)}` : ""}`
                                        : "比例缺失"}
                                    </span>
                                  </div>
                                  <div className="mt-1 flex items-center gap-2">
                                    <span
                                      className={`rounded px-1.5 py-0.5 text-[10px] ${getRiskBadgeStyle(riskLevel)}`}
                                    >
                                      {RISK_SEVERITY_LABELS[riskLevel] ??
                                        RISK_SEVERITY_LABELS.unknown}
                                    </span>
                                    <span className="text-[10px] text-muted-foreground">
                                      {Array.isArray(chain.risk_reasons) &&
                                      chain.risk_reasons.length > 0
                                        ? String(chain.risk_reasons[0]).slice(
                                            0,
                                            60,
                                          )
                                        : "未发现附加风险说明"}
                                    </span>
                                  </div>
                                </div>
                              );
                            })}
                        </div>
                      </div>
                    )}

                    <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <Badge variant="outline">
                        {equityData.nodes.length} 个节点
                      </Badge>
                      <Badge variant="outline">
                        {equityData.edges.length} 条边
                      </Badge>
                      <Badge variant="outline">
                        {equityData.paths.length > 0
                          ? `${equityData.paths.length} 条穿透路径`
                          : "暂无路径"}
                      </Badge>
                      <Badge variant="outline">
                        最深{" "}
                        {equityData.max_observed_hops ??
                          Math.max(
                            0,
                            ...equityData.paths.map((p) => p.depth || 0),
                          )}{" "}
                        跳
                      </Badge>
                      <span>悬停节点看摘要与持股信息，点击节点展开全景详情（含上下游风险）</span>
                    </div>
                    <div className="mt-4">
                      <EquityGraph
                        data={equityData as unknown as EquityGraphData}
                        onNodeClick={(n) =>
                          setOrbitDetail({
                            id: n.id,
                            name: n.name,
                            entity_type: n.type,
                            risk_level: n.risk_level,
                          })
                        }
                      />
                    </div>

                    <Dialog
                      open={orbitDetail !== null}
                      onOpenChange={(open) => {
                        if (!open) setOrbitDetail(null);
                      }}
                    >
                      <DialogContent className="max-w-lg">
                        <DialogHeader>
                          <DialogTitle className="flex items-center gap-2">
                            <span className="inline-block h-2 w-2 rounded-full bg-primary shadow-[0_0_8px_var(--primary)]" />
                            {orbitDetail?.name}
                            <Badge variant="outline" className="text-[10px]">
                              {orbitDetail?.entity_type === "person"
                                ? "自然人"
                                : orbitDetail?.entity_type === "listed_company"
                                  ? "上市公司"
                                  : "企业主体"}
                            </Badge>
                            {orbitDetail?.risk_level && orbitDetail.risk_level !== "unknown" && (
                              <Badge
                                variant="outline"
                                className={
                                  orbitDetail.risk_level === "red"
                                    ? "border-red-500/40 bg-red-500/10 text-red-500"
                                    : orbitDetail.risk_level === "orange"
                                      ? "border-orange-500/40 bg-orange-500/10 text-orange-500"
                                      : orbitDetail.risk_level === "yellow"
                                        ? "border-yellow-500/40 bg-yellow-500/10 text-yellow-500"
                                        : "border-border text-muted-foreground"
                                }
                              >
                                风险 {orbitDetail.risk_level === "red" ? "高" : orbitDetail.risk_level === "orange" ? "中高" : "中"}
                              </Badge>
                            )}
                          </DialogTitle>
                          <DialogDescription className="text-xs">
                            股权穿透 · 关联关系全景
                          </DialogDescription>
                        </DialogHeader>
                        {orbitDetail && (
                          <div className="space-y-3">
                            <div className="rounded-lg border border-border/60 bg-muted/20 p-3">
                              <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                                直接关联（{equityData.edges.filter(
                                  (e) => e.source === orbitDetail.id || e.target === orbitDetail.id,
                                ).length} 条）
                              </div>
                              <div className="space-y-1.5">
                                {equityData.edges
                                  .filter(
                                    (e) => e.source === orbitDetail.id || e.target === orbitDetail.id,
                                  )
                                  .map((e, i) => {
                                    const isSource = e.source === orbitDetail.id;
                                    const otherId = isSource ? e.target : e.source;
                                    const other =
                                      equityData.nodes.find((n) => n.id === otherId)?.name ?? otherId;
                                    return (
                                      <div
                                        key={e.id || i}
                                        className="flex items-center justify-between gap-2 rounded border border-border/40 bg-card/60 px-2.5 py-1.5"
                                      >
                                        <span className="min-w-0 truncate text-xs text-foreground">
                                          {isSource ? "持股 → " : "← 持股 "}
                                          {other}
                                        </span>
                                        <span className="shrink-0 font-mono text-[11px] font-semibold text-primary">
                                          {e.ownership_pct != null ? `${e.ownership_pct}%` : (e.relation_type ?? "—")}
                                        </span>
                                      </div>
                                    );
                                  })}
                              </div>
                            </div>
                            <div className="rounded-lg border border-border/60 bg-muted/20 p-3">
                              <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                                所在穿透链路
                              </div>
                              {(equityData.equity_chains as Array<Record<string, unknown>> || [])
                                .filter((c) =>
                                  Array.isArray(c.path_names)
                                    ? (c.path_names as string[]).some(
                                        (nm) => nm === orbitDetail.name,
                                      )
                                    : false,
                                )
                                .slice(0, 4)
                                .map((c, i) => (
                                  <div
                                    key={i}
                                    className="mb-1 flex items-center justify-between gap-2 text-xs"
                                  >
                                    <span className="min-w-0 truncate text-muted-foreground">
                                      {(c.path_names as string[]).join(" → ")}
                                    </span>
                                    <span className="shrink-0 font-mono font-semibold text-foreground">
                                      {typeof c.final_control_pct === "number"
                                        ? `${c.final_control_pct.toFixed(2)}%`
                                        : "—"}
                                    </span>
                                  </div>
                                ))}
                              {(equityData.equity_chains || []).filter((c) =>
                                Array.isArray(c.path_names)
                                  ? (c.path_names as unknown as string[]).some(
                                      (nm) => nm === orbitDetail.name,
                                    )
                                  : false,
                              ).length === 0 && (
                                <div className="text-xs text-muted-foreground">
                                  未出现在多跳穿透链中（仅直接持股）
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </DialogContent>
                    </Dialog>
                  </CardContent>
                </Card>

                <div className="mt-4">
                  <EquityInsight equityData={equityData} />
                </div>
                <div className="mt-4">
                  <UpstreamDownstream
                    equityData={equityData}
                    downstreamRelations={equityData.downstream_relations}
                    downstreamTotal={equityData.downstream_total}
                  />
                </div>
              </>
            ) : (
              <Card>
                <CardContent className="py-8 text-center text-muted-foreground">
                  暂无股权穿透数据
                </CardContent>
              </Card>
            )}
          </div>

          <Separator className="my-6" />

          {/* 舆情时间线区块 - 使用 RiskTimeline 组件 */}
          <div ref={sectionRefs.sentiment} className="mb-8">
            <Reveal>
              <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-foreground">
                <i className="ph ph-duotone ph-newspaper text-[20px] text-primary" />
                舆情时间线
              </h2>
            </Reveal>
            {!eventsLoaded ? (
              <Card>
                <CardContent className="py-6 space-y-3">
                  <Skeleton className="h-14 w-full" />
                  <Skeleton className="h-32 w-full" />
                </CardContent>
              </Card>
            ) : sentimentEvents.length > 0 ? (
              <RiskTimeline
                events={sentimentEvents}
                companyCode={code}
                clusters={eventClusters}
                onEventClick={() => {
                  const evidenceSection = sectionRefs.evidence;
                  evidenceSection.current?.scrollIntoView({
                    behavior: "smooth",
                  });
                }}
              />
            ) : (
              <Card className="relative overflow-hidden">
                <img
                  src="/assets/hero-globe.jpg"
                  alt=""
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-0 h-full w-full object-cover object-center opacity-[0.18] dark:opacity-[0.4]"
                />
                <div
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-0 bg-gradient-to-b from-card/50 via-card/20 to-card/75 dark:from-card/45 dark:via-card/15 dark:to-card/60"
                />
                <CardContent className="relative flex min-h-[260px] flex-col items-center justify-center py-10 text-center">
                  <div className="mx-auto mb-4 flex h-11 w-11 items-center justify-center rounded-full border border-border bg-card/80 backdrop-blur-sm">
                    <i className="ph-duotone ph-newspaper text-[22px] text-primary" aria-hidden="true" />
                  </div>
                  <p className="text-sm text-foreground/80">
                    舆情事件数据源待接入（需 full profile）
                  </p>
                  <p className="mt-1 font-mono text-[11px] uppercase tracking-[0.25em] text-muted-foreground">
                    global monitoring · standby
                  </p>
                </CardContent>
              </Card>
            )}
          </div>

          <Separator className="my-6" />

          {/* 证据引用区块 - 使用 EvidenceChain 组件 */}
          <div ref={sectionRefs.evidence} className="mb-8">
            <Reveal>
              <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-foreground">
                <i className="ph ph-duotone ph-files text-[20px] text-primary" />
                证据引用
              </h2>
            </Reveal>
            {riskData === null ? (
              <Card>
                <CardContent className="py-6 space-y-3">
                  <Skeleton className="h-14 w-full" />
                  <Skeleton className="h-24 w-full" />
                </CardContent>
              </Card>
            ) : riskData && riskData.evidence.length > 0 ? (
              <EvidenceChain
                categories={groupEvidenceBySource(riskData.evidence)}
                onViewSource={(evidence) => {
                  void openEvidenceDetails(
                    [evidence.evidence_id],
                    `${evidence.evidence_id} · 来源详情`,
                  );
                }}
              />
            ) : (
              <Card>
                <CardContent className="py-8 text-center text-muted-foreground">
                  暂无证据数据
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
      <Dialog open={evidenceDialogOpen} onOpenChange={setEvidenceDialogOpen}>
        <DialogContent className="max-h-[80vh] max-w-3xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{evidenceDialogTitle}</DialogTitle>
            <DialogDescription>
              可回查记录来自后端
              provenance；本次计算输入在规则卡中按报表期次展示。
            </DialogDescription>
          </DialogHeader>
          {evidenceDialogLoading ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              正在加载证据详情…
            </div>
          ) : (
            <div className="space-y-4">
              {(() => {
                const persistedItems = evidenceDialogItems.filter(
                  (item) => item.data,
                );
                const generatedCount = evidenceDialogItems.filter(
                  (item) => item.isGenerated,
                ).length;
                const failedItems = evidenceDialogItems.filter(
                  (item) => item.error && !item.isGenerated,
                );
                return (
                  <>
                    <div className="rounded-md border border-border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
                      已定位{" "}
                      <span className="font-medium text-foreground">
                        {persistedItems.length}
                      </span>{" "}
                      条可回查来源记录
                      {generatedCount > 0 && (
                        <>
                          ；另有{" "}
                          <span className="font-medium text-foreground">
                            {generatedCount}
                          </span>{" "}
                          项本次计算输入，已在“核查计算依据”中汇总展示。
                        </>
                      )}
                    </div>
                    {failedItems.length > 0 && (
                      <p className="text-xs text-destructive">
                        {failedItems.length}{" "}
                        条来源记录暂时无法加载，请稍后重试。
                      </p>
                    )}
                    {persistedItems.map((item) => {
                      const evidence = item.data?.evidence || {};
                      const source = item.data?.source || {};
                      const record = source.record || {};
                      const claims = uniqueEvidenceClaims(
                        item.data?.claims || [],
                      );
                      const displayedClaims = claims.slice(0, 3);
                      return (
                        <div
                          key={item.evidenceId}
                          className="rounded-md border border-border p-4"
                        >
                          <p className="text-sm font-medium text-foreground">
                            {formatEvidenceField(evidence.field_path)} ·{" "}
                            {formatEvidencePeriod(evidence.period)}
                          </p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {String(
                              evidence.source_title ||
                                EVIDENCE_SOURCE_LABELS[
                                  String(evidence.source_type || "")
                                ] ||
                                "来源记录",
                            )}
                            {" · "}
                            {source.resolved
                              ? "已定位原始记录"
                              : "原始记录待补充"}
                          </p>
                          {claims.length > 0 && (
                            <div className="mt-3 border-t border-border pt-3">
                              <div className="text-xs text-muted-foreground">
                                支持的结论
                              </div>
                              {displayedClaims.map((claim, index) => (
                                <p
                                  key={String(claim.claim_id || index)}
                                  className="mt-1 text-sm"
                                >
                                  {String(claim.text || claim.claim_id || "-")}
                                </p>
                              ))}
                              {claims.length > displayedClaims.length && (
                                <p className="mt-1 text-xs text-muted-foreground">
                                  该记录还被{" "}
                                  {claims.length - displayedClaims.length}{" "}
                                  条关联分析复用。
                                </p>
                              )}
                            </div>
                          )}
                          <details className="mt-3">
                            <summary className="cursor-pointer text-xs text-muted-foreground">
                              技术详情与来源记录
                            </summary>
                            <dl className="mt-2 grid gap-x-4 gap-y-1 text-xs text-muted-foreground sm:grid-cols-2">
                              <div>
                                <dt className="inline">证据 ID：</dt>
                                <dd className="inline font-mono">
                                  {item.evidenceId}
                                </dd>
                              </div>
                              <div>
                                <dt className="inline">来源记录：</dt>
                                <dd className="inline">
                                  {String(evidence.source_record_id || "-")}
                                </dd>
                              </div>
                            </dl>
                            {Object.keys(record).length > 0 && (
                              <pre className="mt-2 max-h-48 overflow-auto rounded bg-muted p-3 text-xs">
                                {JSON.stringify(record, null, 2)}
                              </pre>
                            )}
                          </details>
                        </div>
                      );
                    })}
                  </>
                );
              })()}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
