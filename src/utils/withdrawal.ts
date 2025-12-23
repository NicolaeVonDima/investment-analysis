import { Scenario, Portfolio } from '../types';

/**
 * Calculate withdrawal rate based on the formula:
 * Withdrawal Rate = (Weighted total return of Growth + Cashflow assets) - Inflation - Growth Cushion
 * 
 * Growth assets: VWCE, TVBETETF
 * Cashflow assets: AYEG
 * 
 * With hard floor at 0% (no soft cap - growth cushion controls the rate)
 */
export interface WithdrawalCalculation {
  weightedReturn: number;      // Weighted return of Growth + Cashflow assets
  weightedTrimRate: number;     // Additional income from trim rules (as % of portfolio)
  weightedInflation: number;    // Weighted inflation (TVBETETF uses Romanian, others use International)
  growthCushion: number;       // Real growth cushion (configurable)
  rawWithdrawalRate: number;    // Before applying floor
  withdrawalRate: number;       // Final withdrawal rate (after floor)
  floorApplied: boolean;        // Whether floor was applied
}

export function calculateWithdrawalRate(
  scenario: Scenario,
  portfolio: Portfolio
): WithdrawalCalculation {
  // Calculate weighted return of Growth + Cashflow assets
  // Growth: VWCE, TVBETETF
  // Cashflow: AYEG
  const growthCashflowAllocation = 
    portfolio.allocation.vwce + 
    portfolio.allocation.tvbetetf + 
    portfolio.allocation.ayeg;
  
  // If no Growth + Cashflow allocation, return 0
  if (growthCashflowAllocation === 0) {
    const intInflation = scenario.inflation ?? 0.03; // Default to 3% if not set
    return {
      weightedReturn: 0,
      weightedTrimRate: 0,
      weightedInflation: intInflation,
      growthCushion: scenario.growthCushion ?? 0.02,
      rawWithdrawalRate: 0,
      withdrawalRate: 0,
      floorApplied: true
    };
  }
  
  // Calculate weighted return
  const vwceWeight = portfolio.allocation.vwce / growthCashflowAllocation;
  const tvbetetfWeight = portfolio.allocation.tvbetetf / growthCashflowAllocation;
  const ayegWeight = portfolio.allocation.ayeg / growthCashflowAllocation;
  
  // Calculate base weighted return (total return of assets)
  const baseWeightedReturn = 
    (vwceWeight * scenario.assetReturns.vwce) +
    (tvbetetfWeight * scenario.assetReturns.tvbetetf) +
    (ayegWeight * scenario.assetReturns.ayeg);
  
  // Calculate trim-based income rate (additional income from trimming excess returns)
  // Trim amount = max(0, (assetReturn - inflation - growthCushion) - threshold)
  // TVBETETF uses Romanian inflation, other assets use International inflation
  // This represents income generated from excess returns above inflation + growthCushion + threshold
  const growthCushion = scenario.growthCushion ?? 0.02; // Default to 2% if not set
  const romanianInflation = scenario.romanianInflation ?? 0.08; // Default to 8% if not set
  const intInflation = scenario.inflation ?? 0.03; // Default to 3% if not set
  let vwceTrimRate = 0;
  if (scenario.trimRules.vwce.enabled) {
    const excessReturn = Math.max(0, scenario.assetReturns.vwce - intInflation - growthCushion);
    vwceTrimRate = Math.max(0, excessReturn - scenario.trimRules.vwce.threshold);
  }
  
  let tvbetetfTrimRate = 0;
  if (scenario.trimRules.tvbetetf.enabled) {
    // TVBETETF uses Romanian inflation
    const excessReturn = Math.max(0, scenario.assetReturns.tvbetetf - romanianInflation - growthCushion);
    tvbetetfTrimRate = Math.max(0, excessReturn - scenario.trimRules.tvbetetf.threshold);
  }
  
  let ayegTrimRate = 0;
  if (scenario.trimRules.ayeg.enabled) {
    const excessReturn = Math.max(0, scenario.assetReturns.ayeg - intInflation - growthCushion);
    ayegTrimRate = Math.max(0, excessReturn - scenario.trimRules.ayeg.threshold);
  }
  
  // Weighted trim rate (additional income from trims, as % of portfolio)
  const weightedTrimRate = 
    (vwceWeight * vwceTrimRate) +
    (tvbetetfWeight * tvbetetfTrimRate) +
    (ayegWeight * ayegTrimRate);
  
  // Calculate weighted inflation
  // TVBETETF uses Romanian inflation, other assets use International inflation
  const weightedInflation = 
    (vwceWeight * intInflation) +
    (tvbetetfWeight * romanianInflation) +
    (ayegWeight * intInflation);
  
  // The withdrawal formula accounts for trim income as additional available withdrawal capacity
  // Total available = Base Return (capital growth) + Trim Income (converted to income)
  // Withdrawal Rate = (Base Return + Trim Income) - Weighted Inflation - Growth Cushion
  // This reflects that trim rules convert excess returns into withdrawable income
  
  const weightedReturn = baseWeightedReturn;
  
  // Apply the formula: (Total Return + Trim Income) - Weighted Inflation - Growth Cushion
  // The trim income increases the effective withdrawal capacity
  const rawWithdrawalRate = (weightedReturn + weightedTrimRate) - weightedInflation - growthCushion;
  
  // Apply hard floor at 0% (no soft cap - growth cushion controls the rate)
  let withdrawalRate = Math.max(0, rawWithdrawalRate);
  const floorApplied = rawWithdrawalRate < 0;
  
  return {
    weightedReturn,
    weightedTrimRate,
    weightedInflation,
    growthCushion: growthCushion,
    rawWithdrawalRate,
    withdrawalRate,
    floorApplied
  };
}

/**
 * Calculate withdrawal rate for a scenario using a default/example allocation
 * Useful for displaying withdrawal rates in scenario selector
 * 
 * No soft cap - growth cushion controls the withdrawal rate
 */
export function calculateWithdrawalRateForScenario(
  scenario: Scenario
): WithdrawalCalculation {
  // Use a default allocation for demonstration (e.g., Balanced Allocation style)
  const defaultAllocation = {
    vwce: 35,
    tvbetetf: 25,
    ernx: 20,
    ayeg: 10,
    fidelis: 10
  };
  
  const defaultPortfolio: Portfolio = {
    id: 'default',
    name: 'Default',
    color: '#000000',
    capital: 0,
    allocation: defaultAllocation,
    rules: {
      tvbetetfConditional: false
    }
  };
  
  return calculateWithdrawalRate(scenario, defaultPortfolio);
}

