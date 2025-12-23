export type OverperformanceStrategy = 
  | 'reinvest'      // Reinvest excess returns back into the asset
  | 'rebalance'     // Rebalance to maintain target allocation
  | 'income'        // Take excess as income
  | 'diversify';    // Diversify into other assets

export interface Portfolio {
  id: string;
  name: string;
  color: string;
  capital: number;
  goal?: string;
  riskLabel?: string; // e.g., "Risk: Medium"
  horizon?: string; // e.g., "2026 - 2029"
  overperformStrategy?: {
    title: string;
    content: string[]; // Array of bullet points or lines
  };
  allocation: {
    vwce: number;      // 0-100
    tvbetetf: number;  // 0-100
    ernx: number;      // 0-100 (ultrashort bond ETF)
    wqdv: number;      // 0-100
    fidelis: number;   // 0-100
  };
  rules: {
    tvbetetfConditional: boolean; // Keep old conditional logic as option
  };
  strategy?: {
    overperformanceStrategy: OverperformanceStrategy;
    overperformanceThreshold?: number; // Percentage above expected return to trigger strategy
  };
}

export interface Scenario {
  name: string;
  inflation: number;
  taxOnSaleProceeds: number;  // Tax rate on capital gains (e.g., 0.10 = 10%)
  taxOnDividends: number;     // Tax rate on dividends/yield (e.g., 0.05 = 5%)
  assetReturns: {
    vwce: number;      // Total return (e.g., 0.07 = 7%)
    vwceYield: number; // Yield (cash/dividends) - 0 for accumulation ETFs
    tvbetetf: number;  // Total return
    tvbetetfYield: number; // Yield (cash/dividends) - 0 for accumulation ETFs
    ernx: number;      // Total return
    ernxYield: number; // Yield (cash/dividends)
    wqdv: number;      // Total return
    wqdvYield: number; // Yield (cash/dividends)
    fidelis: number;   // Total return (interest rate)
    fidelisYield: number; // Yield (same as return for FIDELIS, always enabled)
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
    ernx: {
      enabled: boolean;
      threshold: number;
    };
    wqdv: {
      enabled: boolean;
      threshold: number;
    };
  };
  fidelisCap: number;    // EUR amount - cap for FIDELIS holdings
  // Legacy fields for backward compatibility (deprecated)
  vwceGrowth?: number;
  tvbetetfGrowth?: number;
  ernxGrowth?: number;
  ernxYield?: number;
  fidelisRate?: number;
}

export interface YearResult {
  year: number;
  capital: number;
  realCapital: number;
  assets: {
    vwce: number;
    tvbetetf: number;
    ernx: number;
    wqdv: number;
    fidelis: number;
  };
  income: {
    vwceYield?: number;
    vwceTrim: number;
    tvbetetfYield?: number;
    tvbetetfToIncome: number;
    tvbetetfReinvested: number;
    ernxYield: number;
    ernxTrim?: number;
    wqdvYield: number;
    wqdvTrim?: number;
    fidelisInterest: number;
    fidelisYield: number;
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

