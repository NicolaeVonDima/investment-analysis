/**
 * API service for saving and loading portfolio data.
 */

import axios from 'axios';
import { Portfolio, Scenario, FamilyMember } from '../types';

// Create React App uses process.env.REACT_APP_*
// In production, nginx proxies /api to backend, so use relative URLs
// In development, use explicit localhost:8000
const getApiUrl = () => {
  // Check for explicit API URL from environment
  if (typeof process !== 'undefined' && (process.env as any)?.REACT_APP_API_URL) {
    return (process.env as any).REACT_APP_API_URL;
  }
  // In production (nginx proxy), use relative URL
  // In development, use explicit localhost:8000
  if (process.env.NODE_ENV === 'production') {
    return ''; // Relative URL - nginx will proxy to backend
  }
  return 'http://localhost:8000';
};

const API_URL = getApiUrl();

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface SaveDataRequest {
  portfolios: Portfolio[];
  scenarios: Scenario[];
  familyMembers?: FamilyMember[];
  default_scenario_id?: string;
}

export interface LoadDataResponse {
  portfolios: (Portfolio & { created_at?: string; updated_at?: string })[];
  scenarios: (Scenario & { id?: string; created_at?: string; updated_at?: string })[];
  familyMembers?: (FamilyMember & { created_at?: string; updated_at?: string })[];
  default_scenario_id?: string;
}

export async function saveData(data: SaveDataRequest): Promise<void> {
  try {
    await api.post('/api/data/save', data);
  } catch (error) {
    console.error('Error saving data:', error);
    throw error;
  }
}

// Transform backend response to frontend format
function transformScenario(scenario: any): Scenario {
  // Handle both camelCase (from frontend) and snake_case (from backend)
  const assetReturns = scenario.assetReturns || scenario.asset_returns;
  const trimRules = scenario.trimRules || scenario.trim_rules;
  const fidelisCap = scenario.fidelisCap !== undefined ? scenario.fidelisCap : (scenario.fidelis_cap !== undefined ? scenario.fidelis_cap : 24000);
  
  return {
    name: scenario.name,
    inflation: scenario.inflation,
    romanianInflation: scenario.romanianInflation !== undefined ? scenario.romanianInflation : (scenario.romanian_inflation !== undefined ? scenario.romanian_inflation : 0.08),
    growthCushion: scenario.growthCushion !== undefined ? scenario.growthCushion : (scenario.growth_cushion !== undefined ? scenario.growth_cushion : 0.02),
    taxOnSaleProceeds: scenario.taxOnSaleProceeds !== undefined ? scenario.taxOnSaleProceeds : (scenario.tax_on_sale_proceeds !== undefined ? scenario.tax_on_sale_proceeds : 0.10),
    taxOnDividends: scenario.taxOnDividends !== undefined ? scenario.taxOnDividends : (scenario.tax_on_dividends !== undefined ? scenario.tax_on_dividends : 0.05),
    assetReturns: assetReturns ? {
      vwce: assetReturns.vwce || 0.07,
      vwceYield: assetReturns.vwceYield !== undefined ? assetReturns.vwceYield : 0,
      tvbetetf: assetReturns.tvbetetf || 0.08,
      tvbetetfYield: assetReturns.tvbetetfYield !== undefined ? assetReturns.tvbetetfYield : 0,
      ernx: assetReturns.ernx || 0.06,
      ernxYield: assetReturns.ernxYield !== undefined ? assetReturns.ernxYield : 0.03,
      // Migrate wqdv to ayeg if present
      ayeg: assetReturns.ayeg !== undefined ? assetReturns.ayeg : (assetReturns.wqdv !== undefined ? assetReturns.wqdv : 0.06),
      ayegYield: assetReturns.ayegYield !== undefined ? assetReturns.ayegYield : (assetReturns.wqdvYield !== undefined ? assetReturns.wqdvYield : 0.04),
      fidelis: assetReturns.fidelis || 0.06,
      fidelisYield: assetReturns.fidelisYield !== undefined ? assetReturns.fidelisYield : (assetReturns.fidelis || 0.06)
    } : {
      vwce: 0.07,
      vwceYield: 0,
      tvbetetf: 0.08,
      tvbetetfYield: 0,
      ernx: 0.06,
      ernxYield: 0.03,
      ayeg: 0.06,
      ayegYield: 0.04,
      fidelis: 0.06,
      fidelisYield: 0.06
    },
    trimRules: trimRules ? {
      vwce: {
        enabled: trimRules.vwce?.enabled !== undefined ? trimRules.vwce.enabled : false,
        threshold: trimRules.vwce?.threshold !== undefined ? trimRules.vwce.threshold : 0
      },
      tvbetetf: {
        enabled: trimRules.tvbetetf?.enabled !== undefined ? trimRules.tvbetetf.enabled : false,
        threshold: trimRules.tvbetetf?.threshold !== undefined ? trimRules.tvbetetf.threshold : 0
      },
      ernx: {
        enabled: trimRules.ernx?.enabled !== undefined ? trimRules.ernx.enabled : false,
        threshold: trimRules.ernx?.threshold !== undefined ? trimRules.ernx.threshold : 0
      },
      // Migrate wqdv to ayeg if present
      ayeg: trimRules.ayeg ? {
        enabled: trimRules.ayeg.enabled !== undefined ? trimRules.ayeg.enabled : false,
        threshold: trimRules.ayeg.threshold !== undefined ? trimRules.ayeg.threshold : 0
      } : (trimRules.wqdv ? {
        enabled: trimRules.wqdv.enabled !== undefined ? trimRules.wqdv.enabled : false,
        threshold: trimRules.wqdv.threshold !== undefined ? trimRules.wqdv.threshold : 0
      } : { enabled: false, threshold: 0 })
    } : {
      vwce: { enabled: false, threshold: 0 },
      tvbetetf: { enabled: false, threshold: 0 },
      ernx: { enabled: false, threshold: 0 },
      ayeg: { enabled: false, threshold: 0 }
    },
    fidelisCap: fidelisCap
  };
}

// Transform portfolio from backend format to frontend format
function transformPortfolio(portfolio: any): Portfolio {
  return {
    id: portfolio.id,
    name: portfolio.name,
    color: portfolio.color,
    capital: portfolio.capital,
    goal: portfolio.goal || undefined,
    riskLabel: portfolio.riskLabel || portfolio.risk_label || undefined,
    horizon: portfolio.horizon || undefined,
    selectedStrategy: portfolio.selectedStrategy || portfolio.selected_strategy || undefined,
    overperformStrategy: portfolio.overperformStrategy || portfolio.overperform_strategy || undefined,
    allocation: portfolio.allocation,
    rules: portfolio.rules,
    strategy: portfolio.strategy || undefined
  };
}

// Transform family member from backend format to frontend format
function transformFamilyMember(member: any): FamilyMember {
  return {
    id: member.id,
    name: member.name,
    amount: member.amount,
    displayOrder: member.displayOrder || member.display_order || 0
  };
}

export async function loadData(): Promise<LoadDataResponse> {
  try {
    const response = await api.get<any>('/api/data/load');
    // Transform scenarios to ensure proper format
    const transformedScenarios = (response.data.scenarios || []).map(transformScenario);
    // Transform portfolios to ensure proper format
    const transformedPortfolios = (response.data.portfolios || []).map(transformPortfolio);
    // Transform family members to ensure proper format
    const transformedFamilyMembers = (response.data.familyMembers || []).map(transformFamilyMember);
    
    return {
      ...response.data,
      portfolios: transformedPortfolios,
      scenarios: transformedScenarios,
      familyMembers: transformedFamilyMembers.length > 0 ? transformedFamilyMembers : undefined
    };
  } catch (error) {
    console.error('Error loading data:', error);
    throw error;
  }
}

export async function clearData(): Promise<void> {
  try {
    await api.delete('/api/data/clear');
  } catch (error) {
    console.error('Error clearing data:', error);
    throw error;
  }
}

