import React from 'react';
import { YearResult } from '../../types';
import { formatCurrency } from '../../utils/formatters';

interface EvolutionTableProps {
  years: YearResult[];
  showReal: boolean;
}

export default function EvolutionTable({ years, showReal }: EvolutionTableProps) {
  // Show every 5 years plus the last year (for 35 years: 0, 5, 10, 15, 20, 25, 30, 34)
  const keyYears = [0, 4, 9, 14, 19, 24, 29, 34].filter(i => i < years.length);
  if (keyYears.length > 0 && keyYears[keyYears.length - 1] !== years.length - 1) {
    keyYears.push(years.length - 1);
  }

  const displayYears = keyYears.map(i => years[i]);

  return (
    <div className="mt-4">
      <h4 className="text-sm font-semibold text-gray-700 mb-2">35-Year Evolution</h4>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b bg-gray-50">
              <th className="text-left p-2 font-semibold">Year</th>
              <th className="text-right p-2 font-semibold">Capital</th>
              <th className="text-right p-2 font-semibold">Monthly Income</th>
            </tr>
          </thead>
          <tbody>
            {displayYears.map((year, idx) => (
              <tr key={year.year} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                <td className="p-2">{year.year}</td>
                <td className="text-right p-2 font-medium">
                  {formatCurrency(showReal ? year.realCapital : year.capital)}
                </td>
                <td className="text-right p-2">
                  {formatCurrency(showReal ? year.realMonthlyIncome : year.monthlyIncome)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

