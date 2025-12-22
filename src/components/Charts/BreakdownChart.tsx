import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { SimulationResult } from '../../types';
import { formatCurrency } from '../../utils/formatters';

interface BreakdownChartProps {
  result: SimulationResult | null;
  showReal: boolean;
}

export default function BreakdownChart({ result, showReal }: BreakdownChartProps) {
  const data = React.useMemo(() => {
    if (!result) return [];
    
    return result.years.map((year, index) => {
      const inflationFactor = Math.pow(1.03, index + 1); // Using 3% as default inflation
      return {
        year: year.year,
        'VGWD Dividends': showReal 
          ? year.income.vgwdDividends / inflationFactor
          : year.income.vgwdDividends,
        'VGWD Trim': showReal
          ? (year.income.vgwdTrim || 0) / inflationFactor
          : (year.income.vgwdTrim || 0),
        'FIDELIS Interest': showReal
          ? year.income.fidelisInterest / inflationFactor
          : year.income.fidelisInterest,
        'VWCE Trim': showReal
          ? year.income.vwceTrim / inflationFactor
          : year.income.vwceTrim,
        'TVBETETF Income': showReal
          ? year.income.tvbetetfToIncome / inflationFactor
          : year.income.tvbetetfToIncome,
      };
    });
  }, [result, showReal]);

  if (!result) {
    return (
      <div className="w-full h-96 flex items-center justify-center text-gray-500">
        Select a portfolio to view income breakdown
      </div>
    );
  }

  return (
    <div className="w-full h-96">
      <h3 className="text-lg font-semibold mb-4">
        Income Breakdown - {result.portfolioName} ({showReal ? 'Real' : 'Nominal'})
      </h3>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis 
            dataKey="year" 
            tick={{ fontSize: 12 }}
            label={{ value: 'Year', position: 'insideBottom', offset: -5 }}
          />
          <YAxis 
            tick={{ fontSize: 12 }}
            tickFormatter={(value) => formatCurrency(value)}
            label={{ value: 'EUR/year', angle: -90, position: 'insideLeft' }}
          />
          <Tooltip 
            formatter={(value: number) => formatCurrency(value)}
            labelFormatter={(label) => `Year: ${label}`}
          />
          <Legend />
          <Area type="monotone" dataKey="VGWD Dividends" stackId="1" stroke="#28A745" fill="#28A745" />
          <Area type="monotone" dataKey="VGWD Trim" stackId="1" stroke="#20C997" fill="#20C997" />
          <Area type="monotone" dataKey="FIDELIS Interest" stackId="1" stroke="#DC3545" fill="#DC3545" />
          <Area type="monotone" dataKey="VWCE Trim" stackId="1" stroke="#2E86AB" fill="#2E86AB" />
          <Area type="monotone" dataKey="TVBETETF Income" stackId="1" stroke="#F4A261" fill="#F4A261" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

