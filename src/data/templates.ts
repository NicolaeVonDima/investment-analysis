import { Portfolio } from '../types';

export interface PortfolioTemplate extends Omit<Portfolio, 'id' | 'color'> {
  goal: string;
}

export const portfolioTemplates: PortfolioTemplate[] = [
  {
    name: 'Balanced Allocation',
    goal: 'A balanced approach combining global diversification with Romanian market exposure and income generation.',
    riskLabel: 'Risk: Medium',
    overperformStrategy: {
      title: 'Over-performing rule',
      content: [
        'Do nothing (accept drift).',
        'Optional tolerance band: ±5% absolute from target.',
        'If contributions exist, direct new contributions to underweight assets.'
      ]
    },
    capital: 675000,
    allocation: {
      vwce: 40,
      tvbetetf: 30,
      vgwd: 20,
      fidelis: 10
    },
    rules: {
      tvbetetfConditional: false
    }
  },
  {
    name: 'Aggressive Growth',
    goal: 'Maximum growth potential focusing on Romanian market with global diversification backup.',
    riskLabel: 'Risk: High to Very High',
    overperformStrategy: {
      title: 'Over-performing rule: Harvest & Rotate',
      content: [
        'Trigger: if an asset exceeds target by ≥10% (e.g., TVBETETF > 70%).',
        'Sell only the excess above the trigger (never below original target).',
        'Reallocate proceeds to VGWD and/or FIDELIS to move gradually toward the Balanced portfolio.',
        'No new cash injections; rebalance using harvested gains only.'
      ]
    },
    capital: 675000,
    allocation: {
      vwce: 40,
      tvbetetf: 60,
      vgwd: 0,
      fidelis: 0
    },
    rules: {
      tvbetetfConditional: false
    }
  },
  {
    name: 'Income Focused',
    goal: 'Prioritize steady income streams from dividends and bonds while maintaining growth potential.',
    riskLabel: 'Risk: Low to Medium',
    overperformStrategy: {
      title: 'Over-performing rule',
      content: [
        'Do nothing (accept drift).',
        'Reinvest dividends within income sleeve (VGWD/FIDELIS) unless income quality changes.',
        'Avoid trimming winners to preserve cash-flow stability.'
      ]
    },
    capital: 675000,
    allocation: {
      vwce: 20,
      tvbetetf: 20,
      vgwd: 40,
      fidelis: 20
    },
    rules: {
      tvbetetfConditional: false
    }
  }
];

export const portfolioColors = ['#2E86AB', '#DC3545', '#28A745'];
