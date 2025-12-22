import React, { useState } from 'react';
import { Portfolio, YearResult } from '../../types';
import { formatCurrency, formatPercentage } from '../../utils/formatters';
import AllocationSlider from './AllocationSlider';
import RulesConfig from './RulesConfig';
import StrategyConfig from './StrategyConfig';
import EvolutionTable from './EvolutionTable';

interface PortfolioCardProps {
  portfolio: Portfolio;
  onUpdate: (portfolio: Portfolio) => void;
  evolutionData?: YearResult[];
  showReal: boolean;
}

export default function PortfolioCard({
  portfolio,
  onUpdate,
  evolutionData,
  showReal
}: PortfolioCardProps) {
  const [name, setName] = useState(portfolio.name);
  const [isExpanded, setIsExpanded] = useState(false);

  const totalAllocation = 
    portfolio.allocation.vwce +
    portfolio.allocation.tvbetetf +
    portfolio.allocation.ernx +
    portfolio.allocation.wqdv +
    portfolio.allocation.fidelis;

  const handleNameChange = (newName: string) => {
    setName(newName);
    onUpdate({ ...portfolio, name: newName });
  };

  const handleAllocationChange = (asset: keyof Portfolio['allocation'], value: number) => {
    onUpdate({
      ...portfolio,
      allocation: {
        ...portfolio.allocation,
        [asset]: value
      }
    });
  };

  const handleRulesChange = (rules: Portfolio['rules']) => {
    onUpdate({
      ...portfolio,
      rules
    });
  };

  const handleStrategyChange = (strategy: Portfolio['strategy']) => {
    onUpdate({
      ...portfolio,
      strategy
    });
  };

  return (
    <div className="bg-white rounded-lg shadow-lg border-2 h-full flex flex-col" style={{ borderColor: portfolio.color }}>
      {/* Header */}
      <div className="p-4 border-b">
        <div className="flex items-start justify-between mb-2">
          <div className="flex items-center gap-2 flex-1">
            <div 
              className="w-3 h-3 rounded-full flex-shrink-0 mt-1"
              style={{ backgroundColor: portfolio.color }}
            />
            <input
              type="text"
              value={name}
              onChange={(e) => handleNameChange(e.target.value)}
              className="font-bold text-lg border-none outline-none bg-transparent flex-1"
              placeholder="Portfolio Name"
            />
          </div>
        </div>
        
        {(portfolio.riskLabel || portfolio.horizon) && (
          <div className="mt-1 mb-2 flex items-center gap-2">
            {portfolio.riskLabel && (
              <span 
                className="text-xs font-medium px-2 py-0.5 rounded"
                style={{ 
                  color: portfolio.color,
                  backgroundColor: `${portfolio.color}15`,
                  border: `1px solid ${portfolio.color}40`
                }}
              >
                {portfolio.riskLabel}
              </span>
            )}
            {portfolio.horizon && (
              <span className="text-xs text-gray-600 font-medium">
                Horizon: {portfolio.horizon}
              </span>
            )}
          </div>
        )}
        
        {portfolio.goal && (
          <p className="text-sm text-gray-600 mt-2 italic">{portfolio.goal}</p>
        )}
      </div>

      {/* Allocation Section */}
      <div className="p-4 border-b">
        <label className="block text-sm font-semibold text-gray-700 mb-3">
          Asset Allocation
        </label>
        <div className="mb-3">
          <div className="flex gap-1 h-4 rounded overflow-hidden">
            <div 
              style={{ 
                width: `${portfolio.allocation.vwce}%`,
                backgroundColor: '#2E86AB'
              }}
              title="VWCE"
            />
            <div 
              style={{ 
                width: `${portfolio.allocation.tvbetetf}%`,
                backgroundColor: '#F4A261'
              }}
              title="TVBETETF"
            />
            <div 
              style={{ 
                width: `${portfolio.allocation.ernx}%`,
                backgroundColor: '#28A745'
              }}
              title="ERNX"
            />
            <div 
              style={{ 
                width: `${portfolio.allocation.wqdv}%`,
                backgroundColor: '#9B59B6'
              }}
              title="WQDV"
            />
            <div 
              style={{ 
                width: `${portfolio.allocation.fidelis}%`,
                backgroundColor: '#DC3545'
              }}
              title="FIDELIS"
            />
          </div>
        </div>
        <AllocationSlider
          label="VWCE"
          value={portfolio.allocation.vwce}
          onChange={(value) => handleAllocationChange('vwce', value)}
          capital={portfolio.capital}
        />
        <AllocationSlider
          label="TVBETETF"
          value={portfolio.allocation.tvbetetf}
          onChange={(value) => handleAllocationChange('tvbetetf', value)}
          capital={portfolio.capital}
        />
        <AllocationSlider
          label="ERNX"
          value={portfolio.allocation.ernx}
          onChange={(value) => handleAllocationChange('ernx', value)}
          capital={portfolio.capital}
        />
        <AllocationSlider
          label="WQDV"
          value={portfolio.allocation.wqdv}
          onChange={(value) => handleAllocationChange('wqdv', value)}
          capital={portfolio.capital}
        />
        <AllocationSlider
          label="FIDELIS"
          value={portfolio.allocation.fidelis}
          onChange={(value) => handleAllocationChange('fidelis', value)}
          capital={portfolio.capital}
        />
        <div className={`text-xs mt-2 ${totalAllocation === 100 ? 'text-green-600' : 'text-red-600'}`}>
          Total: {formatPercentage(totalAllocation / 100)} 
          {totalAllocation !== 100 && ' (must equal 100%)'}
        </div>
      </div>

      {/* Strategy Section - Collapsible */}
      <div className="p-4 border-b">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full flex justify-between items-center text-sm font-semibold text-gray-700 hover:text-primary"
        >
          <span>Strategy</span>
          <span>{isExpanded ? '▼' : '▶'}</span>
        </button>
        {isExpanded && (
          <div className="mt-3">
            <StrategyConfig
              portfolio={portfolio}
              onChange={handleStrategyChange}
            />
          </div>
        )}
      </div>

      {/* Evolution Table */}
      {evolutionData && evolutionData.length > 0 && (
        <div className="p-4 flex-grow">
          <EvolutionTable years={evolutionData} showReal={showReal} />
        </div>
      )}
    </div>
  );
}
