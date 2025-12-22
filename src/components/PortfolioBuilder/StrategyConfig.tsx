import React from 'react';
import { Portfolio } from '../../types';

interface StrategyConfigProps {
  portfolio: Portfolio;
  onChange: (strategy: Portfolio['strategy']) => void;
}

export default function StrategyConfig({ portfolio, onChange }: StrategyConfigProps) {
  // Display over-performing strategy description if available
  const overperformStrategy = portfolio.overperformStrategy;

  return (
    <div className="space-y-4">
      {/* Over-performing Strategy Description */}
      {overperformStrategy && (
        <div>
          <h4 className="text-sm font-semibold text-gray-800 mb-2">
            {overperformStrategy.title}
          </h4>
          <ul className="space-y-1.5 text-xs text-gray-600">
            {overperformStrategy.content.map((line, index) => (
              <li key={index} className="flex items-start">
                <span className="mr-2 text-primary">•</span>
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      
      {!overperformStrategy && (
        <div className="text-xs text-gray-500 italic">
          No over-performing strategy defined for this portfolio.
        </div>
      )}
    </div>
  );
}

