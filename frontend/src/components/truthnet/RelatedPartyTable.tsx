// 织网鉴真 TruthNet - 关联方表格组件
// Phase 3: 关联方表 + 图谱联动 (九列)

import { Fragment } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Building2, User, Network, ArrowRight, AlertTriangle } from 'lucide-react';
import type { EquityNodeDTO, EquityEdgeDTO, EquityResponseData, EventsResponseData } from '@/types/truthnet';
import { cn } from '@/lib/utils';

interface RelatedPartyTableProps {
  equityData: EquityResponseData;
  eventsData?: EventsResponseData;
  onNodeClick?: (node: EquityNodeDTO) => void;
  onHighlightPath?: (path: string[]) => void;
}

// 节点类型图标和颜色
const nodeTypeConfig = {
  company: {
    icon: Building2,
    color: 'text-blue-600',
    bgColor: 'bg-blue-500/10',
    label: '公司',
  },
  person: {
    icon: User,
    color: 'text-green-600',
    bgColor: 'bg-green-500/10',
    label: '个人',
  },
  fund: {
    icon: Network,
    color: 'text-purple-600',
    bgColor: 'bg-purple-500/10',
    label: '基金',
  },
};

export function RelatedPartyTable({ equityData, eventsData, onNodeClick, onHighlightPath }: RelatedPartyTableProps) {
  const { nodes, edges } = equityData;

  // 获取目标公司的直接关联方（V12 契约：edges 用 source/target；节点按 id/entity_id 匹配）
  const targetNode = nodes.find(
    n => n.id === equityData.target?.entity_id || n.entity_id === equityData.target?.entity_id
  );
  const relatedNodes = edges
    .filter(l => l.source === targetNode?.id || l.source === targetNode?.entity_id
      || l.target === targetNode?.id || l.target === targetNode?.entity_id)
    .map(l => {
      const isUpstream = l.target === targetNode?.id || l.target === targetNode?.entity_id;
      const relatedId = isUpstream ? l.source : l.target;
      const relatedNode = nodes.find(n => n.id === relatedId || n.entity_id === relatedId);
      return {
        node: relatedNode,
        link: l,
        isUpstream,
      };
    })
    .filter(r => r.node);

  // 按关系类型分组
  const groupedByRelation = relatedNodes.reduce((groups, item) => {
    const relation = item.link.relation_type || 'unknown';
    if (!groups[relation]) {
      groups[relation] = [];
    }
    groups[relation].push(item);
    return groups;
  }, {} as Record<string, typeof relatedNodes>);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Network className="h-4 w-4" />
            关联方关系
          </CardTitle>
          <Badge variant="secondary" className="text-xs">
            {nodes.length} 个节点
          </Badge>
        </div>
      </CardHeader>

      <CardContent>
        <ScrollArea className="h-[400px]">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[80px]">关系</TableHead>
                <TableHead className="w-[150px]">关联方</TableHead>
                <TableHead className="w-[80px]">持股比例</TableHead>
                <TableHead className="w-[60px]">方向</TableHead>
                <TableHead className="w-[70px]">风险等级</TableHead>
                <TableHead className="w-[60px]">事件数</TableHead>
                <TableHead className="w-[60px]">证据数</TableHead>
                <TableHead className="w-[80px]">数据来源</TableHead>
                <TableHead className="w-[80px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Object.entries(groupedByRelation).map(([relation, items]) => (
                <Fragment key={relation}>
                  <TableRow key={`header-${relation}`} className="bg-muted/50">
                    <TableCell colSpan={9} className="font-medium text-xs py-2">
                      {relationLabels[relation] || relation}
                    </TableCell>
                  </TableRow>
                  {items.map((item, index) => (
                    <RelatedPartyRow
                      key={`${item.node?.entity_id}-${index}`}
                      node={item.node!}
                      link={item.link}
                      isUpstream={item.isUpstream}
                      sourceSystem={equityData.source_system}
                      onNodeClick={onNodeClick}
                      onHighlightPath={onHighlightPath}
                    />
                  ))}
                </Fragment>
              ))}
            </TableBody>
          </Table>

          {/* 空状态 */}
          {relatedNodes.length === 0 && (
            <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
              <Network className="h-8 w-8 mb-2" />
              <span className="text-sm">暂无关联方数据</span>
            </div>
          )}
        </ScrollArea>

        {/* 风险提示 */}
        {hasRiskIndicators(equityData) && (
          <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-red-500 flex-shrink-0 mt-0.5" />
              <div className="text-xs text-red-600">
                <div className="font-medium mb-1">风险提示</div>
                <ul className="list-disc list-inside space-y-1">
                  {getRiskIndicators(equityData).map((risk, index) => (
                    <li key={index}>{risk}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// 关联方行组件
interface RelatedPartyRowProps {
  node: EquityNodeDTO;
  link: EquityEdgeDTO;
  isUpstream: boolean;
  sourceSystem: string;
  onNodeClick?: (node: EquityNodeDTO) => void;
  onHighlightPath?: (path: string[]) => void;
}

function RelatedPartyRow({ node, link, isUpstream, sourceSystem, onNodeClick, onHighlightPath }: RelatedPartyRowProps) {
  // entity_type（ListedCompany/Company/Person/其他）→ 节点类型映射
  const nodeType = node.entity_type === 'Person' ? 'person'
    : (node.entity_type === 'ListedCompany' || node.entity_type === 'Company') ? 'company' : 'fund';
  const typeConfig = nodeTypeConfig[nodeType] || nodeTypeConfig.company;
  const Icon = typeConfig.icon;

  return (
    <TableRow 
      className="group hover:bg-muted/50 cursor-pointer"
      onClick={() => onNodeClick?.(node)}
    >
      {/* 关系 */}
      <TableCell>
        <Badge variant="outline" className="text-xs">
          {relationLabels[link.relation_type] || link.relation_type || '投资'}
        </Badge>
      </TableCell>
      {/* 关联方 */}
      <TableCell>
        <div className="flex items-center gap-2">
          <div className={cn('p-1 rounded', typeConfig.bgColor)}>
            <Icon className={cn('h-3 w-3', typeConfig.color)} />
          </div>
          <div>
            <div className="font-medium text-sm">
              {node.name}
            </div>
            {node.wind_code && (
              <div className="text-xs text-muted-foreground">
                {node.wind_code}
              </div>
            )}
          </div>
        </div>
      </TableCell>
      {/* 持股比例（ownership_pct 已是百分数值，null → '--'） */}
      <TableCell>
        <span className="font-mono text-sm">
          {link.ownership_pct != null ? `${link.ownership_pct.toFixed(2)}%` : '--'}
        </span>
      </TableCell>
      {/* 方向 */}
      <TableCell>
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          {isUpstream ? (
            <>
              <span>投出</span>
              <ArrowRight className="h-3 w-3" />
            </>
          ) : (
            <>
              <ArrowRight className="h-3 w-3 rotate-180" />
              <span>持有</span>
            </>
          )}
        </div>
      </TableCell>
      {/* 风险等级（阈值：>50 高、>20 中） */}
      <TableCell>
        <Badge variant="outline" className={cn('text-xs',
          (link.ownership_pct ?? 0) > 50 ? 'bg-red-500/10 text-red-600' :
          (link.ownership_pct ?? 0) > 20 ? 'bg-yellow-500/10 text-yellow-600' :
          'bg-green-500/10 text-green-600'
        )}>
          {(link.ownership_pct ?? 0) > 50 ? '高' : (link.ownership_pct ?? 0) > 20 ? '中' : '低'}
        </Badge>
      </TableCell>
      {/* 事件数 */}
      <TableCell className="text-xs text-muted-foreground">-</TableCell>
      {/* 证据数 */}
      <TableCell className="text-xs text-muted-foreground">-</TableCell>
      {/* 数据来源 */}
      <TableCell className="text-xs text-muted-foreground">
        {sourceSystem || '-'}
      </TableCell>
      {/* 操作 */}
      <TableCell>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 text-xs opacity-0 group-hover:opacity-100 transition-opacity"
          onClick={(e) => {
            e.stopPropagation();
            onHighlightPath?.([link.source, link.target]);
          }}
        >
          定位
        </Button>
      </TableCell>
    </TableRow>
  );
}

// 关系类型标签映射
const relationLabels: Record<string, string> = {
  OWNS: '持股',
  holding: '控股',
  investment: '投资',
  shareholder: '股东',
  subsidiary: '子公司',
  associate: '联营',
  joint_venture: '合营',
  legal_representative: '法定代表人',
  executive: '高管',
  supervisor: '监事',
  director: '董事',
};

// 最大穿透深度（从 paths 计算，节点无 depth 字段）
function maxPathDepth(equityData: EquityResponseData): number {
  const paths = equityData.paths || [];
  return paths.length > 0 ? Math.max(...paths.map(p => p.depth || 0)) : 0;
}

// 检查是否有风险指标
function hasRiskIndicators(equityData: EquityResponseData): boolean {
  const { edges } = equityData;
  const hasCircular = checkCircularHolding(equityData);
  const maxDepth = maxPathDepth(equityData);
  const hasComplexStructure = maxDepth > 3;
  const hasHighOwnership = edges.some(l => (l.ownership_pct ?? 0) > 50);
  return hasCircular || hasComplexStructure || hasHighOwnership;
}

// 获取风险指标列表
function getRiskIndicators(equityData: EquityResponseData): string[] {
  const risks: string[] = [];
  const { edges } = equityData;

  if (checkCircularHolding(equityData)) {
    risks.push('存在循环持股结构，可能存在资本虚增风险');
  }

  const highOwnershipLinks = edges.filter(l => (l.ownership_pct ?? 0) > 50);
  if (highOwnershipLinks.length > 0) {
    risks.push(`${highOwnershipLinks.length} 条股权持股比例超过 50%`);
  }

  const maxDepth = maxPathDepth(equityData);
  if (maxDepth > 3) {
    risks.push(`股权结构复杂，穿透深度达 ${maxDepth} 层`);
  }

  return risks;
}

// 检查循环持股（邻接表基于 source/target）
function checkCircularHolding(equityData: EquityResponseData): boolean {
  const { edges } = equityData;
  const adjacencyList = new Map<string, string[]>();

  edges.forEach(link => {
    const src = link.source;
    const tgt = link.target;
    if (src && tgt) {
      if (!adjacencyList.has(src)) {
        adjacencyList.set(src, []);
      }
      adjacencyList.get(src)!.push(tgt);
    }
  });
  
  // DFS 检测环
  const visited = new Set<string>();
  const recursionStack = new Set<string>();
  
  function hasCycle(nodeId: string): boolean {
    if (!visited.has(nodeId)) {
      visited.add(nodeId);
      recursionStack.add(nodeId);
      
      const neighbors = adjacencyList.get(nodeId) || [];
      for (const neighbor of neighbors) {
        if (!visited.has(neighbor) && hasCycle(neighbor)) {
          return true;
        }
        if (recursionStack.has(neighbor)) {
          return true;
        }
      }
    }
    recursionStack.delete(nodeId);
    return false;
  }
  
  for (const node of equityData.nodes) {
    if (hasCycle(node.id || node.entity_id)) {
      return true;
    }
  }
  
  return false;
}
