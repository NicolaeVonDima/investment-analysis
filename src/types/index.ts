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
  assetReturns: {
    vwce: number;      // Annual return rate (e.g., 0.07 = 7%)
    tvbetetf: number;  // Annual return rate
    ernx: number;      // Annual return rate
    ernxYield: number; // Yield for ERNX (ultrashort bond ETF)
    wqdv: number;      // Annual return rate
    wqdvYield: number; // Yield for WQDV
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
    ernxYield: number;
    ernxTrim?: number;
    wqdvYield: number;
    wqdvTrim?: number;
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

