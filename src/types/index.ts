export interface Portfolio {
  id: string;
  name: string;
  color: string;
  capital: number;
  goal?: string;
  allocation: {
    vwce: number;      // 0-100
    tvbetetf: number;  // 0-100
    vgwd: number;      // 0-100
    fidelis: number;   // 0-100
  };
  rules: {
    tvbetetfConditional: boolean; // Keep old conditional logic as option
  };
}

export interface Scenario {
  name: string;
  inflation: number;
  assetReturns: {
    vwce: number;      // Annual return rate (e.g., 0.07 = 7%)
    tvbetetf: number;  // Annual return rate
    vgwd: number;      // Annual return rate
    vgwdYield: number; // Dividend yield for VGWD
    fidelis: number;   // Interest rate for FIDELIS
  };
  trimRules: {
    vwce: {
      enabled: boolean;
      threshold: number; // Trim if (return - inflation) > threshold (e.g., 0.04 = 4%)
    };
    tvbetetf: {
      enabled: boolean;
      threshold: number;
    };
    vgwd: {
      enabled: boolean;
      threshold: number;
    };
  };
  fidelisCap: number;    // EUR amount - cap for FIDELIS holdings
  // Legacy fields for backward compatibility (deprecated)
  vwceGrowth?: number;
  tvbetetfGrowth?: number;
  vgwdGrowth?: number;
  vgwdYield?: number;
  fidelisRate?: number;
}

export interface YearResult {
  year: number;
  capital: number;
  realCapital: number;
  assets: {
    vwce: number;
    tvbetetf: number;
    vgwd: number;
    fidelis: number;
  };
  income: {
    vgwdDividends: number;
    vgwdTrim?: number;
    fidelisInterest: number;
    vwceTrim: number;
    tvbetetfToIncome: number;
    tvbetetfReinvested: number;
    total: number;
    totalReal: number;
  };
  monthlyIncome: number;
  realMonthlyIncome: number;
}

export interface SimulationResult {
  portfolioId: string;
  portfolioName: string;
  portfolioColor: string;
  years: YearResult[];
}

export type ChartType = 'capital' | 'income' | 'breakdown' | 'allocation';

