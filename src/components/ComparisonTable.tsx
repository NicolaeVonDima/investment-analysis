import React from 'react';
import { SimulationResult } from '../types';
import { formatCurrency } from '../utils/formatters';

interface ComparisonTableProps {
  results: SimulationResult[];
}

const KEY_YEARS = [1, 5, 10, 15, 20, 25];

export default function ComparisonTable({ results }: ComparisonTableProps) {
  if (results.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow-md p-4 text-center text-gray-500">
        No portfolios to compare
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-4 overflow-x-auto">
      <h3 className="text-lg font-semibold mb-4">Comparison at Key Years</h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b">
            <th className="text-left p-2">Portfolio</th>
            <th className="text-left p-2">Year</th>
            <th className="text-right p-2">Capital (Real)</th>
            <th className="text-right p-2">Monthly Income (Real)</th>
            <th className="text-right p-2">Total Withdrawn</th>
          </tr>
        </thead>
        <tbody>
          {results.map((result) => {
            let cumulativeWithdrawn = 0;
            return KEY_YEARS.map((yearOffset) => {
              const yearData = result.years[yearOffset - 1];
              if (!yearData) return null;
              
              cumulativeWithdrawn += yearData.income.total;
              
              return (
                <tr key={`${result.portfolioId}-${yearOffset}`} className="border-b hover:bg-gray-50">
                  <td className="p-2">
                    <div className="flex items-center gap-2">
                      <div 
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: result.portfolioColor }}
                      />
                      {result.portfolioName}
                    </div>
                  </td>
                  <td className="p-2">{yearData.year}</td>
                  <td className="text-right p-2 font-medium">{formatCurrency(yearData.realCapital)}</td>
                  <td className="text-right p-2">{formatCurrency(yearData.realMonthlyIncome)}</td>
                  <td className="text-right p-2">{formatCurrency(cumulativeWithdrawn)}</td>
                </tr>
              );
            });
          })}
        </tbody>
      </table>
    </div>
  );
}

