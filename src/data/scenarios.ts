import { Scenario } from '../types';

export const scenarios: Scenario[] = [
  {
    name: 'Pessimistic',
    inflation: 0.045,         // International inflation
    romanianInflation: 0.08,  // Romanian inflation (default 8%)
    growthCushion: 0.02,      // 2% real growth cushion
    taxOnSaleProceeds: 0.10,  // 10% tax on capital gains
    taxOnDividends: 0.05,     // 5% tax on dividends/yield
    assetReturns: {
      vwce: 0.04,
      vwceYield: 0,  // Accumulation ETF - no yield
      tvbetetf: 0.03,
      tvbetetfYield: 0,  // Accumulation ETF - no yield
      ernx: 0.02,
      ernxYield: 0.025,
      ayeg: 0.025,
      ayegYield: 0.03,
      fidelis: 0.05,
      fidelisYield: 0.05  // Same as return for FIDELIS
    },
    trimRules: {
      vwce: {
        enabled: false,
        threshold: 0.0
      },
      tvbetetf: {
        enabled: false,
        threshold: 0.0
      },
      ernx: {
        enabled: false,
        threshold: 0.0
      },
      ayeg: {
        enabled: false,
        threshold: 0.0
      }
    },
    fidelisCap: 24000
  },
  {
    name: 'Average',
    inflation: 0.03,          // International inflation
    romanianInflation: 0.08,  // Romanian inflation (default 8%)
    growthCushion: 0.02,      // 2% real growth cushion
    taxOnSaleProceeds: 0.10,  // 10% tax on capital gains
    taxOnDividends: 0.05,     // 5% tax on dividends/yield
    assetReturns: {
      vwce: 0.07,
      vwceYield: 0,  // Accumulation ETF - no yield
      tvbetetf: 0.08,
      tvbetetfYield: 0,  // Accumulation ETF - no yield
      ernx: 0.05,
      ernxYield: 0.03,
      ayeg: 0.06,
      ayegYield: 0.04,
      fidelis: 0.06,
      fidelisYield: 0.06  // Same as return for FIDELIS
    },
    trimRules: {
      vwce: {
        enabled: true,
        threshold: 0.0  // Changed from 0.04 to 0.0 to generate 4% trim (7% - 3% - 0%)
      },
      tvbetetf: {
        enabled: true,
        threshold: 0.0  // Changed from 0.06 to 0.0 to generate 5% trim (8% - 3% - 0%)
      },
      ernx: {
        enabled: false,
        threshold: 0.0
      },
      ayeg: {
        enabled: false,
        threshold: 0.0
      }
    },
    fidelisCap: 24000
  },
  {
    name: 'Optimistic',
    inflation: 0.02,           // International inflation
    romanianInflation: 0.08,  // Romanian inflation (default 8%)
    growthCushion: 0.02,      // 2% real growth cushion
    taxOnSaleProceeds: 0.10,  // 10% tax on capital gains
    taxOnDividends: 0.05,     // 5% tax on dividends/yield
    assetReturns: {
      vwce: 0.10,
      vwceYield: 0,  // Accumulation ETF - no yield
      tvbetetf: 0.12,
      tvbetetfYield: 0,  // Accumulation ETF - no yield
      ernx: 0.07,
      ernxYield: 0.035,
      ayeg: 0.08,
      ayegYield: 0.045,
      fidelis: 0.065,
      fidelisYield: 0.065  // Same as return for FIDELIS
    },
    trimRules: {
      vwce: {
        enabled: true,
        threshold: 0.04
      },
      tvbetetf: {
        enabled: true,
        threshold: 0.06
      },
      ernx: {
        enabled: false,
        threshold: 0.0
      },
      ayeg: {
        enabled: false,
        threshold: 0.0
      }
    },
    fidelisCap: 24000
  }
];

export const defaultScenario = scenarios[1]; // Average
