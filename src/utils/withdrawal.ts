import { Scenario, Portfolio } from '../types';

/**
 * Calculate withdrawal rate based on the formula:
 * Withdrawal Rate = (Weighted total return of Growth + Cashflow assets) - Inflation - (2% real growth cushion)
 * 
 * Growth assets: VWCE, TVBETETF
 * Cashflow assets: WQDV
 * 
 * With hard floor at 0% and optional soft cap at 6-7%
 */
export interface WithdrawalCalculation {
  weightedReturn: number;      // Weighted return of Growth + Cashflow assets
  weightedTrimRate: number;     // Additional income from trim rules (as % of portfolio)
  inflation: number;            // Inflation rate
  growthCushion: number;       // 2% real growth cushion
  rawWithdrawalRate: number;    // Before applying floor/cap
  withdrawalRate: number;       // Final withdrawal rate (after floor/cap)
  softCapApplied: boolean;     // Whether soft cap was applied
  floorApplied: boolean;        // Whether floor was applied
}

export function calculateWithdrawalRate(
  scenario: Scenario,
  portfolio: Portfolio,
  softCap?: number  // If undefined, no soft cap is applied. Default 6% if provided
): WithdrawalCalculation {
  // Calculate weighted return of Growth + Cashflow assets
  // Growth: VWCE, TVBETETF
  // Cashflow: WQDV
  const growthCashflowAllocation = 
    portfolio.allocation.vwce + 
    portfolio.allocation.tvbetetf + 
    portfolio.allocation.wqdv;
  
  // If no Growth + Cashflow allocation, return 0
  if (growthCashflowAllocation === 0) {
    return {
      weightedReturn: 0,
      weightedTrimRate: 0,
      inflation: scenario.inflation,
      growthCushion: 0.02,
      rawWithdrawalRate: 0,
      withdrawalRate: 0,
      softCapApplied: false,
      floorApplied: true
    };
  }
  
  // Calculate weighted return
  const vwceWeight = portfolio.allocation.vwce / growthCashflowAllocation;
  const tvbetetfWeight = portfolio.allocation.tvbetetf / growthCashflowAllocation;
  const wqdvWeight = portfolio.allocation.wqdv / growthCashflowAllocation;
  
  // Calculate base weighted return (total return of assets)
  const baseWeightedReturn = 
    (vwceWeight * scenario.assetReturns.vwce) +
    (tvbetetfWeight * scenario.assetReturns.tvbetetf) +
    (wqdvWeight * scenario.assetReturns.wqdv);
  
  // Calculate trim-based income rate (additional income from trimming excess returns)
  // Trim amount = max(0, (assetReturn - inflation - growthCushion) - threshold)
  // This represents income generated from excess returns above inflation + growthCushion + threshold
  const growthCushion = scenario.growthCushion ?? 0.02; // Default to 2% if not set
  let vwceTrimRate = 0;
  if (scenario.trimRules.vwce.enabled) {
    const excessReturn = Math.max(0, scenario.assetReturns.vwce - scenario.inflation - growthCushion);
    vwceTrimRate = Math.max(0, excessReturn - scenario.trimRules.vwce.threshold);
  }
  
  let tvbetetfTrimRate = 0;
  if (scenario.trimRules.tvbetetf.enabled) {
    const excessReturn = Math.max(0, scenario.assetReturns.tvbetetf - scenario.inflation - growthCushion);
    tvbetetfTrimRate = Math.max(0, excessReturn - scenario.trimRules.tvbetetf.threshold);
  }
  
  let wqdvTrimRate = 0;
  if (scenario.trimRules.wqdv.enabled) {
    const excessReturn = Math.max(0, scenario.assetReturns.wqdv - scenario.inflation - growthCushion);
    wqdvTrimRate = Math.max(0, excessReturn - scenario.trimRules.wqdv.threshold);
  }
  
  // Weighted trim rate (additional income from trims, as % of portfolio)
  const weightedTrimRate = 
    (vwceWeight * vwceTrimRate) +
    (tvbetetfWeight * tvbetetfTrimRate) +
    (wqdvWeight * wqdvTrimRate);
  
  // The withdrawal formula accounts for trim income as additional available withdrawal capacity
  // Total available = Base Return (capital growth) + Trim Income (converted to income)
  // Withdrawal Rate = (Base Return + Trim Income) - Inflation - Growth Cushion
  // This reflects that trim rules convert excess returns into withdrawable income
  
  const weightedReturn = baseWeightedReturn;
  
  // Apply the formula: (Total Return + Trim Income) - Inflation - Growth Cushion
  // The trim income increases the effective withdrawal capacity
  const rawWithdrawalRate = (weightedReturn + weightedTrimRate) - scenario.inflation - growthCushion;
  
  // Apply hard floor at 0%
  let withdrawalRate = Math.max(0, rawWithdrawalRate);
  const floorApplied = rawWithdrawalRate < 0;
  
  // Apply soft cap (if provided)
  let softCapApplied = false;
  if (softCap !== undefined && withdrawalRate > softCap) {
    withdrawalRate = softCap;
    softCapApplied = true;
  }
  
  return {
    weightedReturn,
    weightedTrimRate,
    inflation: scenario.inflation,
    growthCushion: growthCushion,
    rawWithdrawalRate,
    withdrawalRate,
    softCapApplied,
    floorApplied
  };
}

/**
 * Calculate withdrawal rate for a scenario using a default/example allocation
 * Useful for displaying withdrawal rates in scenario selector
 * 
 * Soft cap rules:
 * - Optimistic scenario: No soft cap (unlimited)
 * - Other scenarios: 6% soft cap
 */
export function calculateWithdrawalRateForScenario(
  scenario: Scenario,
  softCap?: number  // If undefined, will be determined by scenario name
): WithdrawalCalculation {
  // Use a default allocation for demonstration (e.g., Balanced Allocation style)
  const defaultAllocation = {
    vwce: 35,
    tvbetetf: 25,
    ernx: 20,
    wqdv: 10,
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
  
  // Determine soft cap based on scenario name if not provided
  let effectiveSoftCap: number | undefined = softCap;
  if (effectiveSoftCap === undefined) {
    // Optimistic scenario has no soft cap (unlimited)
    if (scenario.name.toLowerCase() === 'optimistic') {
      effectiveSoftCap = undefined; // No cap
    } else {
      effectiveSoftCap = 0.06; // 6% for other scenarios
    }
  }
  
  return calculateWithdrawalRate(scenario, defaultPortfolio, effectiveSoftCap);
}

