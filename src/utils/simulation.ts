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
  let vgwd = (portfolio.capital * portfolio.allocation.vgwd) / 100;
  let fidelis = (portfolio.capital * portfolio.allocation.fidelis) / 100;
  
  for (let year = 0; year < years; year++) {
    const currentYear = START_YEAR + year;
    
    // Use scenario-specific asset returns
    const vwceReturn = scenario.assetReturns.vwce;
    const tvbetetfReturn = scenario.assetReturns.tvbetetf;
    const vgwdReturn = scenario.assetReturns.vgwd;
    const vgwdYield = scenario.assetReturns.vgwdYield;
    const fidelisRate = scenario.assetReturns.fidelis;
    
    // 1. Calculate income BEFORE applying trims
    const vgwdDividends = vgwd * vgwdYield;
    const fidelisInterest = fidelis * fidelisRate;
    
    // 2. Calculate trim amounts based on excess return over inflation
    // Trim = max(0, (assetReturn - inflation) - threshold)
    let vwceTrim = 0;
    if (scenario.trimRules.vwce.enabled) {
      const excessReturn = Math.max(0, vwceReturn - scenario.inflation);
      const trimAmount = Math.max(0, excessReturn - scenario.trimRules.vwce.threshold);
      vwceTrim = vwce * trimAmount;
    }
    
    let tvbetetfToIncome = 0;
    let tvbetetfToReinvest = 0;
    if (scenario.trimRules.tvbetetf.enabled) {
      const excessReturn = Math.max(0, tvbetetfReturn - scenario.inflation);
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
    
    let vgwdTrim = 0;
    if (scenario.trimRules.vgwd.enabled) {
      const excessReturn = Math.max(0, vgwdReturn - scenario.inflation);
      const trimAmount = Math.max(0, excessReturn - scenario.trimRules.vgwd.threshold);
      vgwdTrim = vgwd * trimAmount;
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
    const annualIncome = vgwdDividends + actualFidelisInterest + vwceTrim + tvbetetfToIncome + vgwdTrim;
    
    // 5. Apply trims/withdrawals
    vwce -= vwceTrim;
    tvbetetf -= (tvbetetfToIncome + tvbetetfToReinvest);
    vwce += tvbetetfToReinvest;  // Reinvest to VWCE
    vgwd -= vgwdTrim;
    
    // 6. Grow assets for next year
    const vwceNext = vwce * (1 + vwceReturn);
    const tvbetetfNext = tvbetetf * (1 + tvbetetfReturn);
    const vgwdNext = vgwd * (1 + vgwdReturn);
    const fidelisNext = fidelis * (1 + fidelisRate);  // FIDELIS grows at its interest rate
    
    // 7. Calculate totals (after growth)
    const totalCapital = vwceNext + tvbetetfNext + vgwdNext + fidelisNext;
    
    // 8. Calculate real values (inflation-adjusted)
    const inflationFactor = Math.pow(1 + scenario.inflation, year + 1);
    const realCapital = totalCapital / inflationFactor;
    
    const actualAnnualIncome = vgwdDividends + actualFidelisInterest + vwceTrim + tvbetetfToIncome + vgwdTrim;
    const realIncome = actualAnnualIncome / inflationFactor;
    
    results.push({
      year: currentYear,
      capital: totalCapital,
      realCapital: realCapital,
      assets: {
        vwce: vwceNext,
        tvbetetf: tvbetetfNext,
        vgwd: vgwdNext,
        fidelis: fidelisNext
      },
      income: {
        vgwdDividends,
        vgwdTrim: vgwdTrim > 0 ? vgwdTrim : undefined,
        fidelisInterest: actualFidelisInterest,
        vwceTrim,
        tvbetetfToIncome,
        tvbetetfReinvested: tvbetetfToReinvest,
        total: actualAnnualIncome,
        totalReal: realIncome
      },
      monthlyIncome: actualAnnualIncome / 12,
      realMonthlyIncome: realIncome / 12
    });
    
    // Update for next iteration
    vwce = vwceNext;
    tvbetetf = tvbetetfNext;
    vgwd = vgwdNext;
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
