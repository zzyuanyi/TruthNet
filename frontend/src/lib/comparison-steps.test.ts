// v3.3.4 收口复核审查 P2b：comparisonStepToUrl 导航纯函数单元测试。
// 覆盖：白名单 target、空主体、重复代码、参数编码、choose_comparison_pair。

import { describe, expect, it } from 'vitest';

import {
  ALLOWED_COMPARISON_TARGETS,
  comparisonStepToUrl,
  normalizeParticipantCodes,
} from './comparison-steps';
import type { ComparisonNextStep } from '@/types/truthnet';

function step(
  kind: ComparisonNextStep['kind'],
  codes: string[],
  params: Record<string, string> = {},
  target = '/compare',
): ComparisonNextStep {
  return { kind, label: kind, target, participant_codes: codes, params };
}

describe('normalizeParticipantCodes', () => {
  it('去重、去空、trim', () => {
    expect(normalizeParticipantCodes(['a', '', ' b ', 'a'])).toEqual(['a', 'b']);
    expect(normalizeParticipantCodes([])).toEqual([]);
  });
});

describe('comparisonStepToUrl', () => {
  it('白名单只允许 /compare', () => {
    expect(ALLOWED_COMPARISON_TARGETS.has('/compare')).toBe(true);
  });

  it('open_full_comparison → /compare?codes=A,B（URLSearchParams 编码）', () => {
    expect(
      comparisonStepToUrl(
        step('open_full_comparison', ['600519.SH', '600518.SH']),
      ),
    ).toBe('/compare?codes=600519.SH%2C600518.SH');
  });

  it('open_industry_comparison 携带 scope=industry 参数编码', () => {
    expect(
      comparisonStepToUrl(
        step(
          'open_industry_comparison',
          ['600519.SH', '600518.SH'],
          { scope: 'industry' },
        ),
      ),
    ).toBe('/compare?codes=600519.SH%2C600518.SH&scope=industry');
  });

  it('choose_comparison_pair → /compare?candidates=A,B,C（预填全部代码）', () => {
    expect(
      comparisonStepToUrl(
        step('choose_comparison_pair', ['600518.SH', '600519.SH', '000858.SZ']),
      ),
    ).toBe('/compare?candidates=600518.SH%2C600519.SH%2C000858.SZ');
  });

  it('非法 target 被拒绝（null）', () => {
    expect(
      comparisonStepToUrl(step('open_full_comparison', ['a'], {}, '/evil')),
    ).toBeNull();
    expect(
      comparisonStepToUrl(
        step('open_full_comparison', ['a'], {}, 'https://evil.example'),
      ),
    ).toBeNull();
  });

  it('空主体 / 全空白主体被拒绝（null）', () => {
    expect(comparisonStepToUrl(step('open_full_comparison', []))).toBeNull();
    expect(
      comparisonStepToUrl(step('open_full_comparison', ['', '  '])),
    ).toBeNull();
  });

  it('重复代码去重后再编码', () => {
    expect(
      comparisonStepToUrl(
        step('open_full_comparison', ['600519.SH', '600519.SH', '600518.SH']),
      ),
    ).toBe('/compare?codes=600519.SH%2C600518.SH');
  });

  it('params 中空值键值被跳过', () => {
    expect(
      comparisonStepToUrl(
        step('open_full_comparison', ['a'], { scope: '', empty: 'x' }),
      ),
    ).toBe('/compare?codes=a&empty=x');
  });
});
