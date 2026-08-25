// 织网鉴真 TruthNet - 证据链组件
// Phase 2: 证据链展示 (ChatEvidenceV1 数据模型)

import { useAutoAnimate } from '@formkit/auto-animate/react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { FileText, ChevronDown, Link2, AlertCircle } from 'lucide-react';
import type { RiskEvidence, EvidenceCategory } from '@/types/truthnet';
import { cn } from '@/lib/utils';
import { useState } from 'react';

interface EvidenceChainProps {
  categories: EvidenceCategory[];
  onViewSource?: (evidence: RiskEvidence) => void;
  onLinkToRule?: (evidenceId: string) => void;
  // Task 8: 过滤 prop
  filterEvidenceIds?: string[];
}

// 证据类型颜色映射
const categoryColors: Record<string, string> = {
  finance: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
  equity: 'bg-teal-500/10 text-teal-600 border-teal-500/20',
  event: 'bg-orange-500/10 text-orange-600 border-orange-500/20',
  audit: 'bg-red-500/10 text-red-600 border-red-500/20',
  regulatory: 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20',
};

const categoryLabelsMap: Record<string, string> = {
  finance: '财务证据',
  equity: '股权证据',
  event: '舆情证据',
  audit: '审计证据',
  regulatory: '监管证据',
};

const sourceTypeLabels: Record<string, string> = {
  financial_statement: '财务报表',
  neo4j_relationship: '股权关系',
  announcement: '公司公告',
  news: '公开新闻',
  research_report: '研究报告',
  regulation: '监管信息',
  web_search: '联网线索',
};

export function EvidenceChain({ categories, onViewSource, onLinkToRule, filterEvidenceIds }: EvidenceChainProps) {
  // 2026-08-16 可读性：默认展开第一类证据，让用户在外面先看到基本介绍
  const [openCategories, setOpenCategories] = useState<Set<string>>(
    () => new Set(categories.length > 0 ? [categories[0].category] : []),
  );
  const [listParent] = useAutoAnimate();

  // Task 8: 按 filterEvidenceIds 过滤
  const filteredCategories = filterEvidenceIds
    ? categories.map(cat => ({
        ...cat,
        items: cat.items.filter(item => filterEvidenceIds.includes(item.evidence_id)),
      })).filter(cat => cat.items.length > 0)
    : categories;

  const toggleCategory = (categoryId: string) => {
    const newOpen = new Set(openCategories);
    if (newOpen.has(categoryId)) {
      newOpen.delete(categoryId);
    } else {
      newOpen.add(categoryId);
    }
    setOpenCategories(newOpen);
  };

  // 统计总证据数
  const totalEvidence = filteredCategories.reduce((sum, cat) => sum + cat.items.length, 0);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <FileText className="h-4 w-4" />
            证据链
          </CardTitle>
          <Badge variant="secondary" className="text-xs">
            {totalEvidence} 条证据
          </Badge>
        </div>
      </CardHeader>

      <CardContent>
        <ScrollArea className="h-[500px] pr-4">
          <div ref={listParent} className="space-y-3">
            {filteredCategories.map(category => (
              <RiskEvidenceSection
                key={category.category}
                category={category}
                isOpen={openCategories.has(category.category)}
                onToggle={() => toggleCategory(category.category)}
                onViewSource={onViewSource}
                onLinkToRule={onLinkToRule}
              />
            ))}
            {filteredCategories.length === 0 && (
              <div className="text-center text-sm text-muted-foreground py-8">
                暂无证据数据
              </div>
            )}
          </div>
        </ScrollArea>

        {/* 仅供参考标注 */}
        <div className="mt-4 pt-4 border-t border-border">
          <div className="flex items-start gap-2 text-xs text-muted-foreground">
            <AlertCircle className="h-3 w-3 flex-shrink-0 mt-0.5" />
            <span>
              以上证据仅供参考，不构成投资建议。数据来源于公开信息，可能存在滞后或不完整的情况。
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// 证据分类区块
interface RiskEvidenceSectionProps {
  category: EvidenceCategory;
  isOpen: boolean;
  onToggle: () => void;
  onViewSource?: (evidence: RiskEvidence) => void;
  onLinkToRule?: (evidenceId: string) => void;
}

function RiskEvidenceSection({
  category,
  isOpen,
  onToggle,
  onViewSource,
  onLinkToRule,
}: RiskEvidenceSectionProps) {
  const colorClass = categoryColors[category.category] || 'bg-gray-500/10 text-gray-600 border-gray-500/20';
  const label = category.label || categoryLabelsMap[category.category] || category.category;

  return (
    <Collapsible open={isOpen} onOpenChange={onToggle}>
      <CollapsibleTrigger asChild>
        <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50 hover:bg-muted transition-colors cursor-pointer">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className={cn('text-xs', colorClass)}>
              {label}
            </Badge>
            <span className="text-sm font-medium">
              {category.items.length} 条证据
            </span>
          </div>
          <ChevronDown className={cn(
            'h-4 w-4 text-muted-foreground transition-transform',
            isOpen && 'rotate-180'
          )} />
        </div>
      </CollapsibleTrigger>

      <CollapsibleContent>
        <div className="mt-2 ml-4 space-y-2 border-l-2 border-border pl-4">
          {category.items.map(item => (
            <RiskEvidenceCard
              key={item.evidence_id}
              item={item}
              onViewSource={onViewSource}
              onLinkToRule={onLinkToRule}
            />
          ))}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

// 证据单项卡片
function RiskEvidenceCard({ item, onViewSource, onLinkToRule }: {
  item: RiskEvidence;
  onViewSource?: (e: RiskEvidence) => void;
  onLinkToRule?: (id: string) => void;
}) {
  // 8/23 联网线索卡片：web 证据未落库（不可回查），渲染为外链卡片，
  // 不触发 GET /evidence——绝不假装可回查；诚实标注非本地核验。
  if (item.is_web) {
    return (
      <div className="relative p-3 rounded-lg border border-dashed border-amber-500/40 bg-amber-500/5">
        <div className="flex items-start gap-2">
          <Badge className="shrink-0 bg-amber-500/15 text-amber-700 border-amber-500/30 text-[11px]">
            联网检索
          </Badge>
          <span className="font-medium text-sm leading-5">{item.summary || '联网线索'}</span>
        </div>
        {item.source_uri && (
          <a
            href={item.source_uri}
            target="_blank"
            rel="noreferrer"
            className="mt-2 inline-flex items-center gap-1 text-xs text-primary underline break-all"
          >
            打开来源链接 <Link2 className="h-3 w-3" />
          </a>
        )}
        <p className="mt-2 text-[11px] text-muted-foreground leading-4">
          网络公开信息，未经过本地数据集核验，请以官方披露为准。
        </p>
      </div>
    );
  }

  return (
    <div className="group relative p-3 rounded-lg border border-border hover:border-primary/50 hover:shadow-sm transition-all">
      {/* 证据摘要（RiskEvidence 正式 schema，审计 P1-1 适配） */}
      <div className="font-medium text-sm">{item.summary || '风险证据'}</div>

      {/* 来源类型 + claim 关联 */}
      <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground flex-wrap">
        <span className="flex items-center gap-1">
          <Link2 className="h-3 w-3" />
          {sourceTypeLabels[item.source_type] || item.source_type || '未知来源'}
        </span>
        {item.claim_ids && item.claim_ids.length > 0 && (
          <span>·</span>
        )}
        {item.claim_ids && item.claim_ids.length > 0 && (
          <span>{item.claim_ids.length} 条声明关联</span>
        )}
      </div>

      {/* 操作按钮 */}
      <div className="flex gap-2 mt-2 opacity-100 transition-opacity">
        {onViewSource && (
          <Button variant="ghost" size="sm" className="h-7 text-xs gap-1"
            onClick={() => onViewSource(item)}>
            <FileText className="h-3 w-3" />
            查看详情
          </Button>
        )}
        {onLinkToRule && (
          <Button variant="ghost" size="sm" className="h-7 text-xs gap-1"
            onClick={() => onLinkToRule(item.evidence_id)}>
            <Link2 className="h-3 w-3" />
            关联规则
          </Button>
        )}
      </div>
    </div>
  );
}
