import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { SimulationResult } from '../../types';
import { formatCurrency } from '../../utils/formatters';

interface AllocationChartProps {
  result: SimulationResult | null;
}

export default function AllocationChart({ result }: AllocationChartProps) {
  const data = React.useMemo(() => {
    if (!result) return [];
    
    return result.years.map(year => ({
      year: year.year,
      VWCE: year.assets.vwce,
      TVBETETF: year.assets.tvbetetf,
      ERNX: year.assets.ernx,
      WQDV: year.assets.wqdv,
      FIDELIS: year.assets.fidelis,
    }));
  }, [result]);

  if (!result) {
    return (
      <div className="w-full h-96 flex items-center justify-center text-gray-500">
        Select a portfolio to view asset allocation
      </div>
    );
  }

  return (
    <div className="w-full h-96">
      <h3 className="text-lg font-semibold mb-4">
        Asset Allocation Over Time - {result.portfolioName}
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
            label={{ value: 'EUR', angle: -90, position: 'insideLeft' }}
          />
          <Tooltip 
            formatter={(value: number) => formatCurrency(value)}
            labelFormatter={(label) => `Year: ${label}`}
          />
          <Legend wrapperStyle={{ paddingTop: '20px' }} />
          <Area type="monotone" dataKey="VWCE" stackId="1" stroke="#2E86AB" fill="#2E86AB" />
          <Area type="monotone" dataKey="TVBETETF" stackId="1" stroke="#F4A261" fill="#F4A261" />
          <Area type="monotone" dataKey="ERNX" stackId="1" stroke="#28A745" fill="#28A745" />
          <Area type="monotone" dataKey="WQDV" stackId="1" stroke="#9B59B6" fill="#9B59B6" />
          <Area type="monotone" dataKey="FIDELIS" stackId="1" stroke="#DC3545" fill="#DC3545" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

