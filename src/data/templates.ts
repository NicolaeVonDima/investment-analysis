import { Portfolio } from '../types';

export interface PortfolioTemplate extends Omit<Portfolio, 'id' | 'color'> {
  goal: string;
}

export const portfolioTemplates: PortfolioTemplate[] = [
  {
    name: 'Aggressive Growth',
    goal: 'Maximum growth potential focusing on Romanian market with global diversification backup.',
    riskLabel: 'Risk: High to Very High',
    horizon: '2026 - 2029',
    overperformStrategy: {
      title: 'Over-performing rule: Harvest & Rotate',
      content: [
        'Trigger: if an asset exceeds target by ≥10% (e.g., TVBETETF > 70%).',
        'Sell only the excess above the trigger (never below original target).',
        'Reallocate proceeds to ERNX and/or FIDELIS to move gradually toward the Balanced portfolio.',
        'No new cash injections; rebalance using harvested gains only.'
      ]
    },
    capital: 675000,
    allocation: {
      vwce: 35,
      tvbetetf: 55,
      ernx: 0,
      ayeg: 10,
      fidelis: 0
    },
    rules: {
      tvbetetfConditional: false
    }
  },
  {
    name: 'Balanced Allocation',
    goal: 'A balanced approach combining global diversification with Romanian market exposure and income generation.',
    riskLabel: 'Risk: Medium',
    horizon: '2029 - 2035',
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
      vwce: 35,
      tvbetetf: 25,
      ernx: 15,
      ayeg: 15,
      fidelis: 10
    },
    rules: {
      tvbetetfConditional: false
    }
  },
  {
    name: 'Income Focused',
    goal: 'Prioritize steady income streams from dividends and bonds while maintaining growth potential.',
    riskLabel: 'Risk: Low to Medium',
    horizon: '2035 - 2100',
    overperformStrategy: {
      title: 'Over-performing rule',
      content: [
        'Do nothing (accept drift).',
        'Reinvest dividends within income sleeve (ERNX/FIDELIS) unless income quality changes.',
        'Avoid trimming winners to preserve cash-flow stability.'
      ]
    },
    capital: 675000,
    allocation: {
      vwce: 15,
      tvbetetf: 15,
      ernx: 30,
      ayeg: 20,
      fidelis: 20
    },
    rules: {
      tvbetetfConditional: false
    }
  },
  {
    name: 'Current Allocation',
    goal: 'Your actual current portfolio allocation for comparison with other strategies.',
    riskLabel: 'Risk: Custom',
    horizon: 'Current',
    overperformStrategy: {
      title: 'Current strategy',
      content: [
        'This represents your actual portfolio allocation.',
        'Use this to compare your current strategy with other portfolio approaches.'
      ]
    },
    capital: 675000,
    allocation: {
      vwce: 0,
      tvbetetf: 0,
      ernx: 0,
      ayeg: 0,
      fidelis: 0
    },
    rules: {
      tvbetetfConditional: false
    }
  }
];

export const portfolioColors = ['#DC3545', '#2E86AB', '#28A745', '#FFA500']; // Red, Blue, Green, Orange // Red for Aggressive Growth, Blue for Balanced Allocation, Green for Income Focused
