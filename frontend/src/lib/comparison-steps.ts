// v3.3.4 收口复核清单 §5.2：结构化比较动作 → 页面 URL（纯函数）。
// 只允许后端白名单 target；participant_codes 去重非空；参数用
// URLSearchParams 编码，禁止字符串拼接未转义值。

import type { ComparisonNextStep } from '@/types/truthnet';

/** 后端允许的 next_steps target 白名单（清单 §5.2-1） */
export const ALLOWED_COMPARISON_TARGETS: ReadonlySet<string> = new Set(['/compare']);

/** 清洗 participant_codes：去重、去空（清单 §5.2-2） */
export function normalizeParticipantCodes(codes: string[]): string[] {
  return [...new Set((codes || []).map(c => String(c).trim()).filter(Boolean))];
}

/**
 * 结构化动作 → 页面 URL（清单 §5.2/§5.3）。
 * - choose_comparison_pair → /compare?candidates=A,B,C（打开选两家入口，
 *   预填全部代码，不自动选前两家）；
 * - 其余 kind → /compare?codes=A,B,C（+ params 编码，如 scope=industry）。
 * 非法 target / 空主体 → null（前端拒绝渲染可执行按钮）。
 */
export function comparisonStepToUrl(step: ComparisonNextStep): string | null {
  if (!step || !ALLOWED_COMPARISON_TARGETS.has(step.target)) return null;
  const codes = normalizeParticipantCodes(step.participant_codes || []);
  if (codes.length === 0) return null;
  const params = new URLSearchParams();
  if (step.kind === 'choose_comparison_pair') {
    params.set('candidates', codes.join(','));
  } else {
    params.set('codes', codes.join(','));
    for (const [key, value] of Object.entries(step.params || {})) {
      if (key && value) params.set(key, String(value));
    }
  }
  return `${step.target}?${params.toString()}`;
}
