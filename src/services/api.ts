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

// Add auth token to requests if available
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle token refresh on 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          const response = await axios.post(`${API_URL}/api/auth/refresh`, {
            refresh_token: refreshToken
          });
          const { access_token } = response.data;
          localStorage.setItem('access_token', access_token);
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return api(originalRequest);
        }
      } catch (refreshError) {
        // Refresh failed, clear tokens and redirect to login
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

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
    
    // Ensure response.data exists and is an object
    if (!response.data || typeof response.data !== 'object') {
      throw new Error('Invalid response format from server');
    }
    
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
  } catch (error: any) {
    // Don't throw error objects directly - convert to string
    const errorMessage = error?.response?.data?.detail || error?.message || 'Failed to load data';
    console.error('Error loading data:', typeof errorMessage === 'string' ? errorMessage : JSON.stringify(errorMessage));
    throw new Error(typeof errorMessage === 'string' ? errorMessage : 'Failed to load data');
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

// Authentication API functions
export interface User {
  id: string;
  email: string;
  email_verified: boolean;
  first_name?: string;
  last_name?: string;
  role: 'freemium' | 'paid' | 'admin';
  subscription_tier?: string;
  subscription_expires_at?: string;
  is_primary_account: boolean;
  created_at: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  first_name?: string;
  last_name?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export async function register(data: RegisterRequest): Promise<User> {
  try {
    const response = await api.post<User>('/api/auth/register', data);
    return response.data;
  } catch (error: any) {
    console.error('Error registering:', error);
    throw error;
  }
}

export async function login(data: LoginRequest): Promise<TokenResponse> {
  try {
    // Backend expects the data wrapped in a 'credentials' object or directly as email/password
    // Based on the schema, it should be sent directly
    const response = await api.post<TokenResponse>('/api/auth/login', {
      email: data.email,
      password: data.password
    });
    // Store tokens
    localStorage.setItem('access_token', response.data.access_token);
    localStorage.setItem('refresh_token', response.data.refresh_token);
    return response.data;
  } catch (error: any) {
    console.error('Error logging in:', error);
    throw error;
  }
}

export async function logout(): Promise<void> {
  try {
    await api.post('/api/auth/logout');
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  } catch (error) {
    console.error('Error logging out:', error);
    // Clear tokens even if request fails
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  }
}

export async function getCurrentUser(): Promise<User> {
  try {
    const response = await api.get<User>('/api/auth/me');
    return response.data;
  } catch (error) {
    console.error('Error getting current user:', error);
    throw error;
  }
}

// Admin API functions
export interface UserUpdateRequest {
  email?: string;
  first_name?: string;
  last_name?: string;
  role?: 'freemium' | 'paid' | 'admin';
  subscription_tier?: string;
}

export interface PlatformStats {
  total_users: number;
  freemium_users: number;
  paid_users: number;
  admin_users: number;
}

export async function getUsers(): Promise<User[]> {
  try {
    const response = await api.get<User[]>('/api/admin/users');
    return response.data;
  } catch (error) {
    console.error('Error getting users:', error);
    throw error;
  }
}

export async function getUser(userId: string): Promise<User> {
  try {
    const response = await api.get<User>(`/api/admin/users/${userId}`);
    return response.data;
  } catch (error) {
    console.error('Error getting user:', error);
    throw error;
  }
}

export async function updateUser(userId: string, data: UserUpdateRequest): Promise<User> {
  try {
    const response = await api.put<User>(`/api/admin/users/${userId}`, data);
    return response.data;
  } catch (error) {
    console.error('Error updating user:', error);
    throw error;
  }
}

export async function deleteUser(userId: string): Promise<void> {
  try {
    await api.delete(`/api/admin/users/${userId}`);
  } catch (error) {
    console.error('Error deleting user:', error);
    throw error;
  }
}

export async function getPlatformStats(): Promise<PlatformStats> {
  try {
    const response = await api.get<PlatformStats>('/api/admin/stats');
    return response.data;
  } catch (error) {
    console.error('Error getting stats:', error);
    throw error;
  }
}

