import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { truthnetAPI } from '@/lib/api-client';
import type { RulesDefinitionsData, RuleDefinition } from '@/lib/api-client';

const LEVEL_COLORS: Record<string, string> = {
  red: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
  orange: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400',
  yellow: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
};

export default function RulesPage() {
  const [rulesData, setRulesData] = useState<RulesDefinitionsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await truthnetAPI.getRuleDefinitions();
        if (!cancelled) setRulesData(res.data);
      } catch (e) {
        if (!cancelled) setError((e as Error).message || '加载失败');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <Card className="border-destructive/50">
          <CardContent className="py-8 text-center">
            <p className="text-destructive">加载失败</p>
            <p className="text-sm text-muted-foreground mt-1">{error}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">规则配置</h1>
          <p className="text-sm text-muted-foreground mt-1">
            当前版本: {rulesData?.version ?? '-'} · 配置 hash: {rulesData?.definition_hash?.slice(0, 8) ?? '-'}
          </p>
        </div>
        <span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
          {rulesData?.rules.length ?? 0} 条规则
        </span>
      </div>

      {/* Rules list */}
      <ScrollArea className="h-[calc(100vh-200px)]">
        <div className="space-y-4">
          {rulesData?.rules.map((rule: RuleDefinition) => (
            <Card key={rule.rule_id}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{rule.name}</CardTitle>
                  <div className="flex items-center gap-2">
                    {rule.enabled ? (
                      <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-800 dark:bg-green-900/30 dark:text-green-400">
                        启用
                      </span>
                    ) : (
                      <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                        禁用
                      </span>
                    )}
                    <span className="text-xs text-muted-foreground">{rule.rule_id}</span>
                  </div>
                </div>
                {rule.description && (
                  <p className="text-sm text-muted-foreground">{rule.description}</p>
                )}
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Thresholds */}
                {Object.keys(rule.thresholds).length > 0 && (
                  <div>
                    <h4 className="mb-2 text-xs font-medium text-muted-foreground uppercase">阈值配置</h4>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(rule.thresholds).map(([key, value]) => (
                        <span key={key} className="rounded bg-muted px-2 py-1 text-xs">
                          {key}: {value}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {/* Conditions */}
                <div>
                  <h4 className="mb-2 text-xs font-medium text-muted-foreground uppercase">风险条件</h4>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(rule.conditions).map(([level, desc]) => (
                      <span key={level} className={`rounded-full px-2 py-0.5 text-xs ${LEVEL_COLORS[level] || 'bg-muted text-muted-foreground'}`}>
                        {level}: {desc}
                      </span>
                    ))}
                  </div>
                </div>
                {/* Metrics */}
                {rule.metrics.length > 0 && (
                  <div>
                    <h4 className="mb-2 text-xs font-medium text-muted-foreground uppercase">指标</h4>
                    <div className="flex flex-wrap gap-2">
                      {rule.metrics.map((m) => (
                        <span key={m.key} className="rounded bg-muted px-2 py-1 text-xs" title={m.formula}>
                          {m.label}{m.unit ? ` (${m.unit})` : ''}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}