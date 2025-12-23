import { Portfolio, Scenario, YearResult, SimulationResult } from '../types';

const SIMULATION_YEARS = 35;
const START_YEAR = 2025;

export function simulatePortfolio(
  portfolio: Portfolio,
  scenario: Scenario,
  years: number = SIMULATION_YEARS
): SimulationResult {
  const results: YearResult[] = [];
  
  // Initialize assets based on allocation
  let vwce = (portfolio.capital * portfolio.allocation.vwce) / 100;
  let tvbetetf = (portfolio.capital * portfolio.allocation.tvbetetf) / 100;
  let ernx = (portfolio.capital * portfolio.allocation.ernx) / 100;
  let wqdv = (portfolio.capital * portfolio.allocation.wqdv) / 100;
  let fidelis = (portfolio.capital * portfolio.allocation.fidelis) / 100;
  
  for (let year = 0; year < years; year++) {
    const currentYear = START_YEAR + year;
    
    // Use scenario-specific asset returns
    const vwceReturn = scenario.assetReturns.vwce;
    const vwceYield = scenario.assetReturns.vwceYield;
    const tvbetetfReturn = scenario.assetReturns.tvbetetf;
    const tvbetetfYield = scenario.assetReturns.tvbetetfYield;
    const ernxReturn = scenario.assetReturns.ernx;
    const ernxYield = scenario.assetReturns.ernxYield;
    const wqdvReturn = scenario.assetReturns.wqdv;
    const wqdvYield = scenario.assetReturns.wqdvYield;
    const fidelisReturn = scenario.assetReturns.fidelis;
    const fidelisYield = scenario.assetReturns.fidelisYield;
    
    // 1. Calculate income BEFORE applying trims
    const vwceYieldIncome = vwce * vwceYield;
    const tvbetetfYieldIncome = tvbetetf * tvbetetfYield;
    const ernxYieldIncome = ernx * ernxYield;
    const wqdvYieldIncome = wqdv * wqdvYield;
    const fidelisInterest = fidelis * fidelisReturn;
    const fidelisYieldIncome = fidelis * fidelisYield;
    
    // 2. Calculate trim amounts based on excess return over inflation and growth cushion
    // Trim = max(0, (assetReturn - inflation - growthCushion) - threshold)
    const growthCushion = scenario.growthCushion ?? 0.02; // Default to 2% if not set
    let vwceTrim = 0;
    if (scenario.trimRules.vwce.enabled) {
      const excessReturn = Math.max(0, vwceReturn - scenario.inflation - growthCushion);
      const trimAmount = Math.max(0, excessReturn - scenario.trimRules.vwce.threshold);
      vwceTrim = vwce * trimAmount;
    }
    
    let tvbetetfToIncome = 0;
    let tvbetetfToReinvest = 0;
    if (scenario.trimRules.tvbetetf.enabled) {
      const excessReturn = Math.max(0, tvbetetfReturn - scenario.inflation - growthCushion);
      const trimAmount = Math.max(0, excessReturn - scenario.trimRules.tvbetetf.threshold);
      // If using old conditional logic, apply it; otherwise use new trim logic
      if (portfolio.rules.tvbetetfConditional) {
        // Old conditional logic based on return rate
        if (tvbetetfReturn <= 0.05) {
          // No trimming
        } else if (tvbetetfReturn < 0.11) {
          tvbetetfToIncome = tvbetetf * 0.06;  // 6% to income
        } else {
          tvbetetfToReinvest = tvbetetf * 0.06;  // 6% reinvested
        }
      } else {
        // New trim logic: all excess goes to income
        tvbetetfToIncome = tvbetetf * trimAmount;
      }
    }
    
    let ernxTrim = 0;
    if (scenario.trimRules.ernx.enabled) {
      const excessReturn = Math.max(0, ernxReturn - scenario.inflation - growthCushion);
      const trimAmount = Math.max(0, excessReturn - scenario.trimRules.ernx.threshold);
      ernxTrim = ernx * trimAmount;
    }
    
    let wqdvTrim = 0;
    if (scenario.trimRules.wqdv.enabled) {
      const excessReturn = Math.max(0, wqdvReturn - scenario.inflation - growthCushion);
      const trimAmount = Math.max(0, excessReturn - scenario.trimRules.wqdv.threshold);
      wqdvTrim = wqdv * trimAmount;
    }
    
    // 3. FIDELIS cap logic (check before calculating income)
    let actualFidelisInterest = fidelisInterest;
    const isFidelisAtCap = fidelis >= scenario.fidelisCap;
    
    if (fidelis > scenario.fidelisCap) {
      const excess = fidelis - scenario.fidelisCap;
      vwce += excess;
      fidelis = scenario.fidelisCap;
    }
    
    // If FIDELIS is at or above cap, reinvest interest to VWCE (not income)
    if (isFidelisAtCap) {
      vwce += fidelisInterest;
      actualFidelisInterest = 0;  // Interest was reinvested, not income
    }
    
    // 4. Total income for the year
    const annualIncome = vwceYieldIncome + tvbetetfYieldIncome + ernxYieldIncome + wqdvYieldIncome + actualFidelisInterest + vwceTrim + tvbetetfToIncome + ernxTrim + wqdvTrim;
    
    // 5. Apply trims/withdrawals
    vwce -= vwceTrim;
    tvbetetf -= (tvbetetfToIncome + tvbetetfToReinvest);
    vwce += tvbetetfToReinvest;  // Reinvest to VWCE
    ernx -= ernxTrim;
    wqdv -= wqdvTrim;
    
    // 6. Grow assets for next year
    // For all assets: capital grows by (return - yield)
    // - Accumulation ETFs (yield = 0): capital grows by full return
    // - Distribution assets: capital grows by (return - yield), yield paid as income
    // - FIDELIS: capital grows by (return - yield). If yield = return, capital doesn't grow (interest paid out)
    const vwceNext = vwce * (1 + vwceReturn - vwceYield);
    const tvbetetfNext = tvbetetf * (1 + tvbetetfReturn - tvbetetfYield);
    const ernxNext = ernx * (1 + ernxReturn - ernxYield);
    const wqdvNext = wqdv * (1 + wqdvReturn - wqdvYield);
    const fidelisNext = fidelis * (1 + fidelisReturn - fidelisYield);
    
    // 7. Calculate totals (after growth)
    const totalCapital = vwceNext + tvbetetfNext + ernxNext + wqdvNext + fidelisNext;
    
    // 8. Calculate real values (inflation-adjusted)
    const inflationFactor = Math.pow(1 + scenario.inflation, year + 1);
    const realCapital = totalCapital / inflationFactor;
    
    const actualAnnualIncome = vwceYieldIncome + tvbetetfYieldIncome + ernxYieldIncome + wqdvYieldIncome + actualFidelisInterest + vwceTrim + tvbetetfToIncome + ernxTrim + wqdvTrim;
    const realIncome = actualAnnualIncome / inflationFactor;
    
    results.push({
      year: currentYear,
      capital: totalCapital,
      realCapital: realCapital,
      assets: {
        vwce: vwceNext,
        tvbetetf: tvbetetfNext,
        ernx: ernxNext,
        wqdv: wqdvNext,
        fidelis: fidelisNext
      },
      income: {
        vwceYield: vwceYieldIncome > 0 ? vwceYieldIncome : undefined,
        vwceTrim,
        tvbetetfYield: tvbetetfYieldIncome > 0 ? tvbetetfYieldIncome : undefined,
        tvbetetfToIncome,
        tvbetetfReinvested: tvbetetfToReinvest,
        ernxYield: ernxYieldIncome,
        ernxTrim: ernxTrim > 0 ? ernxTrim : undefined,
        wqdvYield: wqdvYieldIncome,
        wqdvTrim: wqdvTrim > 0 ? wqdvTrim : undefined,
        fidelisInterest: actualFidelisInterest,
        fidelisYield: fidelisYieldIncome,
        total: actualAnnualIncome,
        totalReal: realIncome
      },
      monthlyIncome: actualAnnualIncome / 12,
      realMonthlyIncome: realIncome / 12
    });
    
    // Update for next iteration
    vwce = vwceNext;
    tvbetetf = tvbetetfNext;
    ernx = ernxNext;
    wqdv = wqdvNext;
    fidelis = fidelisNext;
  }
  
  return {
    portfolioId: portfolio.id,
    portfolioName: portfolio.name,
    portfolioColor: portfolio.color,
    years: results
  };
}

export function simulateAllPortfolios(
  portfolios: Portfolio[],
  scenario: Scenario,
  years: number = SIMULATION_YEARS
): SimulationResult[] {
  return portfolios.map(portfolio => simulatePortfolio(portfolio, scenario, years));
}
