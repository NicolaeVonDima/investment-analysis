import { Portfolio } from '../types';

export interface PortfolioTemplate extends Omit<Portfolio, 'id' | 'color'> {
  goal: string;
}

export const portfolioTemplates: PortfolioTemplate[] = [
  {
    name: 'Balanced Allocation',
    goal: 'A balanced approach combining global diversification with Romanian market exposure and income generation.',
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
