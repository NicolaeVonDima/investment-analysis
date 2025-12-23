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
  softCap: number = 0.06  // Default 6%, can be set to 0.07 for 7%
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
  
  const weightedReturn = 
    (vwceWeight * scenario.assetReturns.vwce) +
    (tvbetetfWeight * scenario.assetReturns.tvbetetf) +
    (wqdvWeight * scenario.assetReturns.wqdv);
  
  // Apply the formula
  const growthCushion = 0.02; // 2% real growth cushion
  const rawWithdrawalRate = weightedReturn - scenario.inflation - growthCushion;
  
  // Apply hard floor at 0%
  let withdrawalRate = Math.max(0, rawWithdrawalRate);
  const floorApplied = rawWithdrawalRate < 0;
  
  // Apply soft cap (6-7%)
  let softCapApplied = false;
  if (withdrawalRate > softCap) {
    withdrawalRate = softCap;
    softCapApplied = true;
  }
  
  return {
    weightedReturn,
    inflation: scenario.inflation,
    growthCushion,
    rawWithdrawalRate,
    withdrawalRate,
    softCapApplied,
    floorApplied
  };
}

/**
 * Calculate withdrawal rate for a scenario using a default/example allocation
 * Useful for displaying withdrawal rates in scenario selector
 */
export function calculateWithdrawalRateForScenario(
  scenario: Scenario,
  softCap: number = 0.06
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
  
  return calculateWithdrawalRate(scenario, defaultPortfolio, softCap);
}

