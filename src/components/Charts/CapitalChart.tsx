import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { SimulationResult } from '../../types';
import { formatCurrency } from '../../utils/formatters';

interface CapitalChartProps {
  results: SimulationResult[];
  showReal: boolean;
}

export default function CapitalChart({ results, showReal }: CapitalChartProps) {
  const data = React.useMemo(() => {
    if (results.length === 0) return [];
    
    const years = results[0].years.map(y => y.year);
    return years.map(year => {
      const point: any = { year };
      results.forEach(result => {
        const yearData = result.years.find(y => y.year === year);
        if (yearData) {
          point[result.portfolioName] = showReal ? yearData.realCapital : yearData.capital;
        }
      });
      return point;
    });
  }, [results, showReal]);

  return (
    <div className="w-full h-96">
      <h3 className="text-lg font-semibold mb-4">
        Capital Growth ({showReal ? 'Real' : 'Nominal'})
      </h3>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
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
          <Legend />
          {results.map((result) => (
            <Line
              key={result.portfolioId}
              type="monotone"
              dataKey={result.portfolioName}
              stroke={result.portfolioColor}
              strokeWidth={2}
              dot={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

