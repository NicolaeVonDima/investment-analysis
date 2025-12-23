import React, { useState, useMemo, useEffect } from 'react';
import { Portfolio, YearResult } from '../../types';
import { formatCurrency, formatPercentage } from '../../utils/formatters';
import AllocationSlider from './AllocationSlider';
import RulesConfig from './RulesConfig';
import StrategyConfig from './StrategyConfig';
import EvolutionTable from './EvolutionTable';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';

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
  const [isFlipped, setIsFlipped] = useState(false);
  const [isWithdrawalGuidanceExpanded, setIsWithdrawalGuidanceExpanded] = useState(true);

  // Fixed height for all cards to ensure consistency (increased by 20% to avoid scrolling)
  const FIXED_CARD_HEIGHT = '1080px';

  // Sync local name state with portfolio prop (important for member portfolios synced from family members)
  useEffect(() => {
    setName(portfolio.name);
  }, [portfolio.name]);

  const totalAllocation = 
    portfolio.allocation.vwce +
    portfolio.allocation.tvbetetf +
    portfolio.allocation.ernx +
    portfolio.allocation.ayeg +
    portfolio.allocation.fidelis;

  // Check if this is a member portfolio (name ends with "'s Portfolio")
  const isMemberPortfolio = portfolio.name.endsWith("'s Portfolio");

  const handleNameChange = (newName: string) => {
    // Only allow editing for non-member portfolios
    if (!isMemberPortfolio) {
      setName(newName);
      onUpdate({ ...portfolio, name: newName });
    }
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

  // Calculate summary stats for the back
  const totalValue = portfolio.capital;
  const allocationBreakdown = [
    { name: 'VWCE', value: portfolio.allocation.vwce, amount: (totalValue * portfolio.allocation.vwce) / 100, color: '#2E86AB' },
    { name: 'TVBETETF', value: portfolio.allocation.tvbetetf, amount: (totalValue * portfolio.allocation.tvbetetf) / 100, color: '#F4A261' },
    { name: 'ERNX', value: portfolio.allocation.ernx, amount: (totalValue * portfolio.allocation.ernx) / 100, color: '#28A745' },
    { name: 'AYEG', value: portfolio.allocation.ayeg, amount: (totalValue * portfolio.allocation.ayeg) / 100, color: '#9B59B6' },
    { name: 'FIDELIS', value: portfolio.allocation.fidelis, amount: (totalValue * portfolio.allocation.fidelis) / 100, color: '#DC3545' },
  ].filter(item => item.value > 0);

  // Calculate allocation rationale by role
  const allocationRationale = useMemo(() => {
    const growth = portfolio.allocation.vwce + portfolio.allocation.tvbetetf;
    const defensive = portfolio.allocation.ernx + portfolio.allocation.fidelis;
    const cashflow = portfolio.allocation.ayeg;
    
    return [
      { name: 'Growth', value: growth, color: '#3B82F6' }, // Blue
      { name: 'Defensive', value: defensive, color: '#10B981' }, // Green
      { name: 'Cashflow', value: cashflow, color: '#8B5CF6' }, // Purple
    ].filter(item => item.value > 0);
  }, [portfolio.allocation]);

  return (
    <div 
      className="relative w-full" 
      style={{ 
        perspective: '1000px',
        height: FIXED_CARD_HEIGHT
      }}
    >
      <div 
        className="relative w-full h-full transition-all duration-500 ease-in-out"
        style={{ 
          transformStyle: 'preserve-3d',
          height: FIXED_CARD_HEIGHT
        }}
      >
        {/* Front of Card */}
        <div 
          className={`w-full h-full bg-white rounded-lg shadow-lg border-2 flex flex-col transition-opacity duration-500 overflow-y-auto ${
            isFlipped ? 'absolute opacity-0 pointer-events-none' : 'relative opacity-100'
          }`}
          style={{ 
            borderColor: portfolio.color,
            transform: isFlipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
            backfaceVisibility: 'hidden',
            WebkitBackfaceVisibility: 'hidden',
            top: 0,
            left: 0,
            height: FIXED_CARD_HEIGHT
          }}
        >
          {/* Header */}
          <div className="p-4 border-b h-[160px] flex flex-col justify-between relative">
            <div>
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2 flex-1">
                  <div 
                    className="w-3 h-3 rounded-full flex-shrink-0 mt-1"
                    style={{ backgroundColor: portfolio.color }}
                  />
                  {isMemberPortfolio ? (
                    <span className="font-bold text-lg flex-1">
                      {name}
                    </span>
                  ) : (
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => handleNameChange(e.target.value)}
                      className="font-bold text-lg border-none outline-none bg-transparent flex-1"
                      placeholder="Portfolio Name"
                    />
                  )}
                </div>
                {/* Flip Toggle Button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setIsFlipped(!isFlipped);
                  }}
                  className="ml-2 p-1.5 rounded-md hover:bg-gray-100 transition-colors"
                  title="Flip card"
                >
                  <svg 
                    className="w-5 h-5 text-gray-500" 
                    fill="none" 
                    stroke="currentColor" 
                    viewBox="0 0 24 24"
                  >
                    <path 
                      strokeLinecap="round" 
                      strokeLinejoin="round" 
                      strokeWidth={2} 
                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" 
                    />
                  </svg>
                </button>
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
          
          {/* Strategy selector for custom portfolios */}
          {isMemberPortfolio && (
            <div className="mt-2 mb-2 flex items-center gap-2">
              <label className="text-xs text-gray-600 font-medium whitespace-nowrap">
                Strategy:
              </label>
              <select
                value={portfolio.selectedStrategy || ''}
                onChange={(e) => {
                  onUpdate({
                    ...portfolio,
                    selectedStrategy: e.target.value || undefined
                  });
                }}
                className="flex-1 text-xs px-2 py-1 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="">-- Select Strategy --</option>
                <option value="Aggressive Growth">Aggressive Growth</option>
                <option value="Balanced Allocation">Balanced Allocation</option>
                <option value="Income Focused">Income Focused</option>
              </select>
            </div>
          )}
        </div>

        {portfolio.goal && (
          <p className="text-sm text-gray-600 italic line-clamp-3">{portfolio.goal}</p>
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
                width: `${portfolio.allocation.ayeg}%`,
                backgroundColor: '#9B59B6'
              }}
              title="AYEG"
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
          label="AYEG"
          value={portfolio.allocation.ayeg}
          onChange={(value) => handleAllocationChange('ayeg', value)}
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

        {/* Back of Card */}
        <div 
          className={`w-full h-full bg-white rounded-lg shadow-lg border-2 flex flex-col transition-opacity duration-500 overflow-y-auto ${
            isFlipped ? 'relative opacity-100' : 'absolute opacity-0 pointer-events-none'
          }`}
          style={{ 
            borderColor: portfolio.color,
            transform: isFlipped ? 'rotateY(0deg)' : 'rotateY(-180deg)',
            backfaceVisibility: 'hidden',
            WebkitBackfaceVisibility: 'hidden',
            top: 0,
            left: 0,
            height: FIXED_CARD_HEIGHT
          }}
        >
          {/* Back Header */}
          <div className="p-4 border-b h-[160px] flex flex-col justify-between relative">
            <div>
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2 flex-1">
                  <div 
                    className="w-3 h-3 rounded-full flex-shrink-0 mt-1"
                    style={{ backgroundColor: portfolio.color }}
                  />
                  <h3 className="font-bold text-lg">{name}</h3>
                </div>
                {/* Flip Toggle Button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setIsFlipped(!isFlipped);
                  }}
                  className="ml-2 p-1.5 rounded-md hover:bg-gray-100 transition-colors"
                  title="Flip card"
                >
                  <svg 
                    className="w-5 h-5 text-gray-500" 
                    fill="none" 
                    stroke="currentColor" 
                    viewBox="0 0 24 24"
                  >
                    <path 
                      strokeLinecap="round" 
                      strokeLinejoin="round" 
                      strokeWidth={2} 
                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" 
                    />
                  </svg>
                </button>
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
            </div>

            {portfolio.goal && (
              <p className="text-sm text-gray-600 italic line-clamp-3">{portfolio.goal}</p>
            )}
          </div>

          {/* Back Content - Summary & Strategy */}
          <div className="p-4 flex-grow overflow-y-auto">
            {/* Allocation Rationale */}
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-gray-700 mb-3">Allocation Rationale</h4>
              {allocationRationale.length > 0 ? (
                <div className="flex items-center gap-4">
                  <div className="w-32 h-32 flex-shrink-0">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={allocationRationale}
                          cx="50%"
                          cy="50%"
                          labelLine={false}
                          label={({ name, value }) => `${name}: ${value.toFixed(1)}%`}
                          outerRadius={50}
                          fill="#8884d8"
                          dataKey="value"
                        >
                          {allocationRationale.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip formatter={(value: number) => `${value.toFixed(2)}%`} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="flex-1 space-y-2">
                    {allocationRationale.map((item) => (
                      <div key={item.name} className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                          <div 
                            className="w-3 h-3 rounded"
                            style={{ backgroundColor: item.color }}
                          />
                          <span className="text-gray-600 font-medium">{item.name}</span>
                        </div>
                        <span className="font-bold text-gray-900">{formatPercentage(item.value / 100)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-xs text-gray-500 italic">No allocation configured</p>
              )}
            </div>

            {/* Portfolio Explanation - Aggressive Growth Only */}
            {portfolio.name === 'Aggressive Growth' && (
              <div className="mb-4 space-y-4">
                {/* Rationale Section */}
                <div>
                  <h4 className="text-sm font-semibold text-gray-700 mb-2">Rationale (user-facing)</h4>
                  <div className="flex gap-2">
                    <div className="w-0.5 bg-gray-300 flex-shrink-0"></div>
                    <p className="text-xs text-gray-600 italic flex-1">
                      This portfolio maximizes real capital growth. It accepts high volatility and does not generate income. It relies on external buffers for living expenses.
                    </p>
                  </div>
                </div>

                {/* Withdrawal Guidance & Rules Section */}
                <div>
                  <button
                    onClick={() => setIsWithdrawalGuidanceExpanded(!isWithdrawalGuidanceExpanded)}
                    className="flex items-center justify-between w-full text-left mb-2"
                  >
                    <h4 className="text-sm font-semibold text-gray-700">Withdrawal guidance & Rules</h4>
                    <svg
                      className={`w-4 h-4 text-gray-500 transition-transform ${isWithdrawalGuidanceExpanded ? 'rotate-180' : ''}`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  {isWithdrawalGuidanceExpanded && (
                    <div className="space-y-3">
                      <div className="border border-gray-200 rounded">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="border-b border-gray-200 bg-gray-50">
                              <th className="text-left p-2 font-semibold text-gray-700">Market</th>
                              <th className="text-left p-2 font-semibold text-gray-700">Guidance</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr className="border-b border-gray-200">
                              <td className="p-2 text-gray-600">Normal</td>
                              <td className="p-2">
                                <div className="flex items-center gap-1">
                                  <svg className="w-4 h-4 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                                    <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                                  </svg>
                                  <span className="text-gray-700">None</span>
                                </div>
                              </td>
                            </tr>
                            <tr className="border-b border-gray-200">
                              <td className="p-2 text-gray-600">Bull</td>
                              <td className="p-2">
                                <div className="flex items-center gap-1">
                                  <svg className="w-4 h-4 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                                    <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                                  </svg>
                                  <span className="text-gray-700">None</span>
                                </div>
                              </td>
                            </tr>
                            <tr>
                              <td className="p-2 text-gray-600">Bear</td>
                              <td className="p-2">
                                <div className="flex items-center gap-1">
                                  <svg className="w-4 h-4 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                                    <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                                  </svg>
                                  <span className="text-gray-700">None</span>
                                </div>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                      {/* Rules Section */}
                      <div>
                        <h5 className="text-xs font-semibold text-gray-700 mb-1">Rules:</h5>
                        <ul className="text-xs text-gray-600 space-y-1 list-disc list-inside">
                          <li>This portfolio is never a spending source.</li>
                        </ul>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Portfolio Explanation - Balanced Allocation Only */}
            {portfolio.name === 'Balanced Allocation' && (
              <div className="mb-4 space-y-4">
                {/* Rationale Section */}
                <div>
                  <h4 className="text-sm font-semibold text-gray-700 mb-2">Rationale</h4>
                  <div className="flex gap-2">
                    <div className="w-0.5 bg-gray-300 flex-shrink-0"></div>
                    <p className="text-xs text-gray-600 italic flex-1">
                      This portfolio balances long-term growth with protection against volatility and inflation. Income is generated selectively from dividend-paying equities, while bonds and cash preserve capital.
                    </p>
                  </div>
                </div>

                {/* Withdrawal Guidance & Rules Section */}
                <div>
                  <button
                    onClick={() => setIsWithdrawalGuidanceExpanded(!isWithdrawalGuidanceExpanded)}
                    className="flex items-center justify-between w-full text-left mb-2"
                  >
                    <h4 className="text-sm font-semibold text-gray-700">Withdrawal guidance & Rules</h4>
                    <svg
                      className={`w-4 h-4 text-gray-500 transition-transform ${isWithdrawalGuidanceExpanded ? 'rotate-180' : ''}`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  {isWithdrawalGuidanceExpanded && (
                    <div className="space-y-3">
                      <div className="border border-gray-200 rounded">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="border-b border-gray-200 bg-gray-50">
                              <th className="text-left p-2 font-semibold text-gray-700">Market</th>
                              <th className="text-left p-2 font-semibold text-gray-700">Guidance</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr className="border-b border-gray-200">
                              <td className="p-2 text-gray-600">Normal</td>
                              <td className="p-2">
                                <div className="flex items-center gap-1">
                                  <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                  </svg>
                                  <span className="text-gray-700">1.5-2.5% (from AYEG first)</span>
                                </div>
                              </td>
                            </tr>
                            <tr className="border-b border-gray-200">
                              <td className="p-2 text-gray-600">Bull</td>
                              <td className="p-2">
                                <div className="flex items-center gap-1">
                                  <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                  </svg>
                                  <span className="text-gray-700">Up to 3% (harvest gains)</span>
                                </div>
                              </td>
                            </tr>
                            <tr>
                              <td className="p-2 text-gray-600">Bear</td>
                              <td className="p-2">
                                <div className="flex items-center gap-1">
                                  <svg className="w-4 h-4 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
                                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                                  </svg>
                                  <span className="text-gray-700">≤1%, defensive assets only</span>
                                </div>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                      {/* Rules Section */}
                      <div>
                        <h5 className="text-xs font-semibold text-gray-700 mb-1">Rules:</h5>
                        <ul className="text-xs text-gray-600 space-y-1 list-disc list-inside">
                          <li>AYEG dividends may be spent or reinvested</li>
                          <li>FIDELIS coupons <strong>must be reinvested</strong></li>
                          <li>Growth assets untouched in drawdowns</li>
                        </ul>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Portfolio Explanation - Income Focused Only */}
            {portfolio.name === 'Income Focused' && (
              <div className="mb-4 space-y-4">
                {/* Rationale Section */}
                <div>
                  <h4 className="text-sm font-semibold text-gray-700 mb-2">Rationale</h4>
                  <div className="flex gap-2">
                    <div className="w-0.5 bg-gray-300 flex-shrink-0"></div>
                    <p className="text-xs text-gray-600 italic flex-1">
                      This portfolio prioritizes stable living support through equity income that can grow over time, while defensive assets protect capital against inflation and market stress.
                    </p>
                  </div>
                </div>

                {/* Withdrawal Guidance & Rules Section */}
                <div>
                  <button
                    onClick={() => setIsWithdrawalGuidanceExpanded(!isWithdrawalGuidanceExpanded)}
                    className="flex items-center justify-between w-full text-left mb-2"
                  >
                    <h4 className="text-sm font-semibold text-gray-700">Withdrawal guidance & Rules</h4>
                    <svg
                      className={`w-4 h-4 text-gray-500 transition-transform ${isWithdrawalGuidanceExpanded ? 'rotate-180' : ''}`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  {isWithdrawalGuidanceExpanded && (
                    <div className="space-y-3">
                      <div className="border border-gray-200 rounded">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="border-b border-gray-200 bg-gray-50">
                              <th className="text-left p-2 font-semibold text-gray-700">Market</th>
                              <th className="text-left p-2 font-semibold text-gray-700">Guidance</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr className="border-b border-gray-200">
                              <td className="p-2 text-gray-600">Normal</td>
                              <td className="p-2">
                                <div className="flex items-center gap-1">
                                  <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                  </svg>
                                  <span className="text-gray-700">3-4%</span>
                                </div>
                              </td>
                            </tr>
                            <tr className="border-b border-gray-200">
                              <td className="p-2 text-gray-600">Bull</td>
                              <td className="p-2">
                                <div className="flex items-center gap-1">
                                  <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                  </svg>
                                  <span className="text-gray-700">4-5% (harvest equity gains)</span>
                                </div>
                              </td>
                            </tr>
                            <tr>
                              <td className="p-2 text-gray-600">Bear</td>
                              <td className="p-2">
                                <div className="flex items-center gap-1">
                                  <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                  </svg>
                                  <span className="text-gray-700">2-3% (defensive assets only)</span>
                                </div>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                      {/* Critical Rules Section */}
                      <div>
                        <h5 className="text-xs font-semibold text-gray-700 mb-1">Critical rules (explicit):</h5>
                        <ul className="text-xs text-gray-600 space-y-1 list-disc list-inside">
                          <li>AYEG dividends = primary income</li>
                          <li>FIDELIS coupons are reinvested</li>
                          <li>ERNX used as liquidity buffer</li>
                          <li>Growth assets untouched in bear markets</li>
                        </ul>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Allocation Summary */}
            <div className="mb-4 pt-2 border-t border-gray-200">
              <h4 className="text-sm font-semibold text-gray-700 mb-2">Allocation Summary</h4>
              <div className="space-y-2">
                {allocationBreakdown.map((item) => (
                  <div key={item.name} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <div 
                        className="w-3 h-3 rounded"
                        style={{ backgroundColor: item.color }}
                      />
                      <span className="text-gray-600">{item.name}</span>
                    </div>
                    <div className="text-right">
                      <div className="font-medium text-gray-900">{formatPercentage(item.value / 100)}</div>
                      <div className="text-xs text-gray-500">{formatCurrency(item.amount)}</div>
                    </div>
                  </div>
                ))}
                <div className="pt-2 border-t border-gray-200 flex items-center justify-between">
                  <span className="text-sm font-semibold text-gray-700">Total</span>
                  <div className="text-right">
                    <div className="font-bold text-gray-900">{formatCurrency(totalValue)}</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Strategy Section */}
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-gray-700 mb-2">Strategy</h4>
              <StrategyConfig
                portfolio={portfolio}
                onChange={handleStrategyChange}
              />
            </div>

            {/* Rules Section */}
            <div>
              <h4 className="text-sm font-semibold text-gray-700 mb-2">Rules</h4>
              <RulesConfig
                rules={portfolio.rules}
                onChange={handleRulesChange}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
