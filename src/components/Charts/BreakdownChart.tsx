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
        'VWCE Yield': showReal 
          ? (year.income.vwceYield || 0) / inflationFactor
          : (year.income.vwceYield || 0),
        'VWCE Trim': showReal
          ? year.income.vwceTrim / inflationFactor
          : year.income.vwceTrim,
        'TVBETETF Yield': showReal 
          ? (year.income.tvbetetfYield || 0) / inflationFactor
          : (year.income.tvbetetfYield || 0),
        'TVBETETF Income': showReal
          ? year.income.tvbetetfToIncome / inflationFactor
          : year.income.tvbetetfToIncome,
        'ERNX Yield': showReal 
          ? year.income.ernxYield / inflationFactor
          : year.income.ernxYield,
        'ERNX Trim': showReal
          ? (year.income.ernxTrim || 0) / inflationFactor
          : (year.income.ernxTrim || 0),
        'AYEG Yield': showReal 
          ? year.income.ayegYield / inflationFactor
          : year.income.ayegYield,
        'AYEG Trim': showReal
          ? (year.income.ayegTrim || 0) / inflationFactor
          : (year.income.ayegTrim || 0),
        'FIDELIS Yield': showReal
          ? (year.income.fidelisYield || 0) / inflationFactor
          : (year.income.fidelisYield || 0),
        'FIDELIS Interest': showReal
          ? year.income.fidelisInterest / inflationFactor
          : year.income.fidelisInterest,
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
        <AreaChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 60 }}>
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
          <Legend wrapperStyle={{ paddingTop: '20px' }} />
          <Area type="monotone" dataKey="VWCE Yield" stackId="1" stroke="#2E86AB" fill="#2E86AB" />
          <Area type="monotone" dataKey="VWCE Trim" stackId="1" stroke="#1E6A8A" fill="#1E6A8A" />
          <Area type="monotone" dataKey="TVBETETF Yield" stackId="1" stroke="#F4A261" fill="#F4A261" />
          <Area type="monotone" dataKey="TVBETETF Income" stackId="1" stroke="#E76F51" fill="#E76F51" />
          <Area type="monotone" dataKey="ERNX Yield" stackId="1" stroke="#28A745" fill="#28A745" />
          <Area type="monotone" dataKey="ERNX Trim" stackId="1" stroke="#20C997" fill="#20C997" />
          <Area type="monotone" dataKey="AYEG Yield" stackId="1" stroke="#9B59B6" fill="#9B59B6" />
          <Area type="monotone" dataKey="AYEG Trim" stackId="1" stroke="#8E44AD" fill="#8E44AD" />
          <Area type="monotone" dataKey="FIDELIS Yield" stackId="1" stroke="#DC3545" fill="#DC3545" />
          <Area type="monotone" dataKey="FIDELIS Interest" stackId="1" stroke="#C82333" fill="#C82333" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

