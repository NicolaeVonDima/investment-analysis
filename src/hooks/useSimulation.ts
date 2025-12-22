import { useMemo } from 'react';
import { Portfolio, Scenario, SimulationResult } from '../types';
import { simulateAllPortfolios } from '../utils/simulation';

export function useSimulation(
  portfolios: Portfolio[],
  scenario: Scenario,
  years: number = 35
): SimulationResult[] {
  return useMemo(() => {
    if (portfolios.length === 0) return [];
    return simulateAllPortfolios(portfolios, scenario, years);
  }, [portfolios, scenario, years]);
}

