import React, { useMemo } from 'react';
import { Portfolio, YearResult } from '../../types';
import { formatCurrency } from '../../utils/formatters';

interface FamilyTotalCardProps {
  memberPortfolios: Portfolio[];
  evolutionData?: { [portfolioId: string]: YearResult[] };
  showReal: boolean;
}

export default function FamilyTotalCard({
  memberPortfolios,
  evolutionData,
  showReal
}: FamilyTotalCardProps) {
  // Calculate total family capital
  const totalCapital = useMemo(() => {
    return memberPortfolios.reduce((sum, p) => sum + p.capital, 0);
  }, [memberPortfolios]);

  // Calculate weighted average allocation
  const aggregatedAllocation = useMemo(() => {
    if (totalCapital === 0) {
      return { vwce: 0, tvbetetf: 0, ernx: 0, ayeg: 0, fidelis: 0 };
    }

    const weighted = memberPortfolios.reduce((acc, portfolio) => {
      const weight = portfolio.capital / totalCapital;
      return {
        vwce: acc.vwce + portfolio.allocation.vwce * weight,
        tvbetetf: acc.tvbetetf + portfolio.allocation.tvbetetf * weight,
        ernx: acc.ernx + portfolio.allocation.ernx * weight,
        ayeg: acc.ayeg + portfolio.allocation.ayeg * weight,
        fidelis: acc.fidelis + portfolio.allocation.fidelis * weight,
      };
    }, { vwce: 0, tvbetetf: 0, ernx: 0, ayeg: 0, fidelis: 0 });

    return weighted;
  }, [memberPortfolios, totalCapital]);

  // Calculate total family monthly income from first year (year 0)
  // This shows expected income based on current allocations, not projected future income
  // Use monthlyIncome/realMonthlyIncome directly (already calculated in simulation)
  const totalIncome = useMemo(() => {
    if (!evolutionData) return 0;
    
    let totalMonthlyIncome = 0;
    memberPortfolios.forEach(portfolio => {
      const evolution = evolutionData[portfolio.id];
      if (evolution && evolution.length > 0) {
        // Use year 0 (first year) to show expected income based on current allocations
        const firstYear = evolution[0];
        // Use the pre-calculated monthly income fields for accuracy
        totalMonthlyIncome += showReal ? firstYear.realMonthlyIncome : firstYear.monthlyIncome;
      }
    });
    
    return totalMonthlyIncome;
  }, [memberPortfolios, evolutionData, showReal]);

  // Calculate allocation amounts
  const allocationBreakdown = [
    { name: 'VWCE', value: aggregatedAllocation.vwce, amount: (totalCapital * aggregatedAllocation.vwce) / 100, color: '#2E86AB' },
    { name: 'TVBETETF', value: aggregatedAllocation.tvbetetf, amount: (totalCapital * aggregatedAllocation.tvbetetf) / 100, color: '#F4A261' },
    { name: 'ERNX', value: aggregatedAllocation.ernx, amount: (totalCapital * aggregatedAllocation.ernx) / 100, color: '#28A745' },
    { name: 'AYEG', value: aggregatedAllocation.ayeg, amount: (totalCapital * aggregatedAllocation.ayeg) / 100, color: '#9B59B6' },
    { name: 'FIDELIS', value: aggregatedAllocation.fidelis, amount: (totalCapital * aggregatedAllocation.fidelis) / 100, color: '#DC3545' },
  ].filter(item => item.value > 0);

  const FIXED_CARD_HEIGHT = '1080px';

  return (
    <div 
      className="relative w-full" 
      style={{ 
        height: FIXED_CARD_HEIGHT
      }}
    >
      <div 
        className="w-full h-full bg-gradient-to-br from-indigo-50 to-purple-50 rounded-lg shadow-lg border-2 border-indigo-300 flex flex-col overflow-y-auto"
        style={{ height: FIXED_CARD_HEIGHT }}
      >
        {/* Header */}
        <div className="p-3 border-b border-indigo-200 bg-white/50">
          <div className="flex flex-col items-center">
            <div className="w-6 h-6 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center mb-2">
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            </div>
            <h3 className="font-bold text-sm text-indigo-900 text-center leading-tight">Family Total</h3>
            <p className="text-xs text-indigo-600 text-center mt-1">{memberPortfolios.length} {memberPortfolios.length === 1 ? 'Member' : 'Members'}</p>
          </div>
        </div>

        {/* Total Capital */}
        <div className="p-3 border-b border-indigo-200 bg-white/30">
          <div className="text-center">
            <p className="text-xs text-gray-600 mb-1 font-medium">Total Capital</p>
            <p className="text-lg font-bold text-indigo-900 leading-tight">{formatCurrency(totalCapital)}</p>
          </div>
        </div>

        {/* Allocation Visualization */}
        <div className="p-3 border-b border-indigo-200">
          <p className="text-xs font-semibold text-gray-700 mb-2 text-center">Asset Allocation</p>
          <div className="flex flex-col gap-1 mb-3">
            <div className="flex gap-0.5 h-3 rounded overflow-hidden">
              {allocationBreakdown.map((item) => (
                <div 
                  key={item.name}
                  style={{ 
                    width: `${item.value}%`,
                    backgroundColor: item.color
                  }}
                  title={`${item.name}: ${item.value.toFixed(1)}%`}
                />
              ))}
            </div>
          </div>

          {/* Allocation Breakdown */}
          <div className="space-y-1.5">
            {allocationBreakdown.map((item) => (
              <div key={item.name} className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <div 
                    className="w-2 h-2 rounded-sm flex-shrink-0"
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="text-xs text-gray-700 font-medium">{item.name}</span>
                </div>
                <span className="text-xs font-bold text-gray-900">{item.value.toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>

        {/* Allocation Amounts */}
        <div className="p-3 border-b border-indigo-200 bg-white/20">
          <p className="text-xs font-semibold text-gray-700 mb-2 text-center">Amounts</p>
          <div className="space-y-1.5">
            {allocationBreakdown.map((item) => (
              <div key={item.name} className="flex items-center justify-between">
                <span className="text-xs text-gray-600">{item.name}</span>
                <span className="text-xs font-medium text-gray-900">
                  {formatCurrency(item.amount, true)}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Expected Monthly Income */}
        {evolutionData && totalIncome > 0 && (
          <div className="p-3 border-b border-indigo-200 bg-indigo-50/50">
            <div className="text-center">
              <p className="text-xs text-gray-600 mb-1 font-medium">Monthly Income</p>
              <p className="text-sm font-bold text-indigo-900">{formatCurrency(totalIncome)}</p>
              <p className="text-xs text-gray-500 mt-0.5">{showReal ? '(Real)' : '(Nominal)'}</p>
            </div>
          </div>
        )}

        {/* Info Note */}
        <div className="p-3 flex-grow flex items-end">
          <div className="w-full bg-indigo-100/50 rounded p-2">
            <p className="text-xs text-indigo-800 italic text-center leading-relaxed">
              Weighted average of all family member portfolios
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

