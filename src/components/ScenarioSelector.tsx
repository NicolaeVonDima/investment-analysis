import React, { useState, useMemo } from 'react';
import { Scenario } from '../types';
import { formatPercentage } from '../utils/formatters';
import AssetReturnsConfig from './PortfolioBuilder/AssetReturnsConfig';
import { calculateWithdrawalRateForScenario } from '../utils/withdrawal';

interface ScenarioSelectorProps {
  scenarios: Scenario[];
  selectedScenario: Scenario;
  onSelect: (scenario: Scenario) => void;
  onUpdate: (scenario: Scenario) => void;
  onSave?: (scenario: Scenario) => Promise<void>;
}

export default function ScenarioSelector({
  scenarios,
  selectedScenario,
  onSelect,
  onUpdate,
  onSave
}: ScenarioSelectorProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [saveStatus, setSaveStatus] = useState<Record<string, 'idle' | 'saving' | 'saved'>>({});

  const handlePresetSelect = (scenario: Scenario) => {
    onSelect(scenario);
  };

  const handleAssetReturnsUpdate = (scenario: Scenario) => {
    onUpdate(scenario);
  };

  const handleInflationChange = (value: number) => {
    onUpdate({
      ...selectedScenario,
      inflation: value
    });
  };

  // Get background color for the editing section based on selected scenario
  const getEditingBackgroundColor = (name: string) => {
    switch (name.toLowerCase()) {
      case 'pessimistic':
        return 'bg-rose-50 border-rose-200';
      case 'average':
        return 'bg-sky-50 border-sky-200';
      case 'optimistic':
        return 'bg-emerald-50 border-emerald-200';
      default:
        return 'bg-gray-50 border-gray-200';
    }
  };

  const handleSave = async (scenario: Scenario) => {
    if (!onSave) return;
    
    setSaveStatus(prev => ({ ...prev, [scenario.name]: 'saving' }));
    try {
      await onSave(scenario);
      setSaveStatus(prev => ({ ...prev, [scenario.name]: 'saved' }));
      setTimeout(() => {
        setSaveStatus(prev => ({ ...prev, [scenario.name]: 'idle' }));
      }, 2000);
    } catch (error) {
      console.error('Error saving scenario:', error);
      setSaveStatus(prev => ({ ...prev, [scenario.name]: 'idle' }));
    }
  };

  // Calculate withdrawal rate for the selected scenario
  // No soft cap - growth cushion controls the withdrawal rate
  const withdrawalCalc = useMemo(() => {
    return calculateWithdrawalRateForScenario(selectedScenario);
  }, [selectedScenario]);

  // Get border color based on selected scenario
  const getBorderColor = (name: string) => {
    switch (name.toLowerCase()) {
      case 'pessimistic':
        return '#EF4444'; // rose-500
      case 'average':
        return '#0EA5E9'; // sky-500
      case 'optimistic':
        return '#10B981'; // emerald-500
      default:
        return '#6B7280'; // gray-500
    }
  };

  return (
    <div 
      className="bg-white rounded-lg shadow-lg border-2 p-4"
      style={{ borderColor: getBorderColor(selectedScenario.name) }}
    >
      <div className="flex justify-between items-center mb-3 pb-2 border-b">
        <div className="flex items-center gap-2">
          <div 
            className="w-3 h-3 rounded-full flex-shrink-0"
            style={{ backgroundColor: getBorderColor(selectedScenario.name) }}
          />
          <h3 className="text-base font-semibold text-gray-800">Scenario</h3>
        </div>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-xs text-gray-600 hover:text-gray-800 font-medium"
        >
          {isExpanded ? '▼ Collapse' : '▶ Expand'}
        </button>
      </div>

      <div className="flex gap-2 mb-3">
        {scenarios
          .sort((a, b) => {
            // Define order: Pessimistic, Average, Optimistic
            const order: Record<string, number> = {
              'Pessimistic': 1,
              'Average': 2,
              'Optimistic': 3
            };
            return (order[a.name] || 999) - (order[b.name] || 999);
          })
          .map((scenario) => {
          const isSelected = selectedScenario.name === scenario.name;
          
          // Define colors for each scenario matching portfolio card style
          const getScenarioColors = (name: string) => {
            switch (name.toLowerCase()) {
              case 'pessimistic':
                return {
                  selected: 'bg-rose-500 text-white border-rose-500',
                  unselected: 'bg-white text-rose-700 hover:bg-rose-50 border-2 border-rose-200'
                };
              case 'average':
                return {
                  selected: 'bg-sky-500 text-white border-sky-500',
                  unselected: 'bg-white text-sky-700 hover:bg-sky-50 border-2 border-sky-200'
                };
              case 'optimistic':
                return {
                  selected: 'bg-emerald-500 text-white border-emerald-500',
                  unselected: 'bg-white text-emerald-700 hover:bg-emerald-50 border-2 border-emerald-200'
                };
              default:
                return {
                  selected: 'bg-primary text-white border-primary',
                  unselected: 'bg-white text-gray-700 hover:bg-gray-50 border-2 border-gray-200'
                };
            }
          };
          
          const colors = getScenarioColors(scenario.name);
          
          return (
            <button
              key={scenario.name}
              onClick={() => handlePresetSelect(scenario)}
              className={`flex-1 px-3 py-2 rounded-lg font-semibold transition-all border-2 shadow-sm text-sm ${
                isSelected ? colors.selected : colors.unselected
              }`}
            >
              {scenario.name}
            </button>
          );
        })}
      </div>

      <div className={`border-t pt-3 ${isExpanded ? getEditingBackgroundColor(selectedScenario.name) : ''} ${isExpanded ? 'rounded-lg p-3 -mx-4 -mb-4 mt-2' : ''}`}>
        {isExpanded ? (
          <div className="space-y-3">
            <div className="grid grid-cols-5 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Int Inflation (%)
                </label>
                <input
                  type="number"
                  value={(selectedScenario.inflation * 100).toFixed(2)}
                  onChange={(e) => handleInflationChange(parseFloat(e.target.value) / 100 || 0)}
                  className="w-full px-2 py-1.5 border-2 border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-primary bg-white text-sm [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  step="0.1"
                  min="0"
                  max="20"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Romanian Inflation (%)
                </label>
                <input
                  type="number"
                  value={((selectedScenario.romanianInflation ?? 0.08) * 100).toFixed(2)}
                  onChange={(e) => onUpdate({
                    ...selectedScenario,
                    romanianInflation: parseFloat(e.target.value) / 100 || 0.08
                  })}
                  className="w-full px-2 py-1.5 border-2 border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-primary bg-white text-sm [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  step="0.1"
                  min="0"
                  max="20"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Growth Cushion (%)
                </label>
                <input
                  type="number"
                  value={((selectedScenario.growthCushion ?? 0.02) * 100).toFixed(2)}
                  onChange={(e) => onUpdate({
                    ...selectedScenario,
                    growthCushion: parseFloat(e.target.value) / 100 || 0.02
                  })}
                  className="w-full px-2 py-1.5 border-2 border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-primary bg-white text-sm [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  step="0.1"
                  min="0"
                  max="10"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Tax on Sale Proceeds (%)
                </label>
                <input
                  type="number"
                  value={((selectedScenario.taxOnSaleProceeds ?? 0) * 100).toFixed(2)}
                  onChange={(e) => onUpdate({
                    ...selectedScenario,
                    taxOnSaleProceeds: parseFloat(e.target.value) / 100 || 0
                  })}
                  className="w-full px-2 py-1.5 border-2 border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-primary bg-white text-sm [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  step="0.1"
                  min="0"
                  max="50"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Tax on Dividends (%)
                </label>
                <input
                  type="number"
                  value={((selectedScenario.taxOnDividends ?? 0) * 100).toFixed(2)}
                  onChange={(e) => onUpdate({
                    ...selectedScenario,
                    taxOnDividends: parseFloat(e.target.value) / 100 || 0
                  })}
                  className="w-full px-2 py-1.5 border-2 border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-primary bg-white text-sm [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  step="0.1"
                  min="0"
                  max="50"
                />
              </div>
            </div>
            
            <AssetReturnsConfig
              scenario={selectedScenario}
              onUpdate={handleAssetReturnsUpdate}
            />
            
            {/* Withdrawal Rate Preview */}
            <div className="pt-3 border-t border-gray-200">
              <h4 className="text-xs font-semibold text-gray-700 mb-2">Withdrawal Rate Preview</h4>
              <div className="bg-white rounded-lg p-3 border-2 border-purple-200 shadow-sm">
                {/* Formula Display */}
                <div className="flex items-center justify-center gap-2 flex-wrap text-sm mb-2">
                  <span className="text-gray-600">Weighted Return:</span>
                  <span className="font-semibold text-purple-700">{formatPercentage(withdrawalCalc.weightedReturn)}</span>
                  {withdrawalCalc.weightedTrimRate > 0 && (
                    <>
                      <span className="text-gray-400">+</span>
                      <span className="text-gray-600">Trim Income:</span>
                      <span className="font-semibold text-purple-600">{formatPercentage(withdrawalCalc.weightedTrimRate)}</span>
                    </>
                  )}
                  <span className="text-gray-400">−</span>
                  <span className="text-gray-600">Weighted Inflation:</span>
                  <span className="font-semibold text-purple-700">{formatPercentage(withdrawalCalc.weightedInflation)}</span>
                  <span className="text-gray-400">−</span>
                  <span className="text-gray-600">Growth Cushion:</span>
                  <span className="font-semibold text-purple-700">{formatPercentage(withdrawalCalc.growthCushion)}</span>
                  <span className="text-gray-400">=</span>
                  <span className={`font-semibold ${withdrawalCalc.rawWithdrawalRate < 0 ? 'text-red-600' : 'text-gray-700'}`}>
                    {formatPercentage(withdrawalCalc.rawWithdrawalRate)}
                  </span>
                </div>
                
                {/* Final Rate */}
                <div className="pt-2 border-t border-purple-200 flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-gray-700">Final Withdrawal Rate:</span>
                    <span className="text-lg font-bold text-purple-800">{formatPercentage(withdrawalCalc.withdrawalRate)}</span>
                    {withdrawalCalc.floorApplied ? (
                      <span className="text-xs text-gray-600">✓ Floor applied (0% min)</span>
                    ) : (
                      <span className="text-xs text-gray-500 italic">No floor or cap applied</span>
                    )}
                    <span className="text-xs text-gray-500 italic">* Default allocation: 35% VWCE, 25% TVBETETF, 10% AYEG</span>
                  </div>
                </div>
              </div>
            </div>
            
            {onSave && (
              <div className="pt-3 border-t border-gray-200 flex justify-end">
                <button
                  onClick={() => handleSave(selectedScenario)}
                  disabled={saveStatus[selectedScenario.name] === 'saving'}
                  className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-colors ${
                    saveStatus[selectedScenario.name] === 'saving'
                      ? 'bg-gray-400 text-white cursor-not-allowed'
                      : saveStatus[selectedScenario.name] === 'saved'
                      ? 'bg-green-500 text-white'
                      : 'bg-primary text-white hover:bg-primary/90'
                  }`}
                >
                  {saveStatus[selectedScenario.name] === 'saving' 
                    ? 'Saving...' 
                    : saveStatus[selectedScenario.name] === 'saved' 
                    ? '✓ Saved' 
                    : `Save ${selectedScenario.name}`}
                </button>
              </div>
            )}
          </div>
        ) : (
          <div>
            <div className="grid grid-cols-3 gap-3">
              {/* First Column - Asset Returns */}
              <div>
                <div className="bg-white rounded-lg p-3 border-2 border-green-200 shadow-sm">
                  <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-2 pb-1.5 border-b">Asset Returns</h4>
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between py-1.5 border-b border-gray-100 last:border-0">
                      <span className="text-xs text-gray-700 font-medium">VWCE</span>
                      <span className="text-sm font-bold text-green-700">{formatPercentage(selectedScenario.assetReturns.vwce)}</span>
                    </div>
                    <div className="flex items-center justify-between py-1.5 border-b border-gray-100 last:border-0">
                      <span className="text-xs text-gray-700 font-medium">TVBETETF</span>
                      <span className="text-sm font-bold text-green-700">{formatPercentage(selectedScenario.assetReturns.tvbetetf)}</span>
                    </div>
                    <div className="flex items-center justify-between py-1.5 border-b border-gray-100 last:border-0">
                      <span className="text-xs text-gray-700 font-medium">ERNX</span>
                      <span className="text-sm font-bold text-green-700">{formatPercentage(selectedScenario.assetReturns.ernx)}</span>
                    </div>
                    <div className="flex items-center justify-between py-1.5 border-b border-gray-100 last:border-0">
                      <span className="text-xs text-gray-700 font-medium">AYEG</span>
                      <span className="text-sm font-bold text-green-700">{formatPercentage(selectedScenario.assetReturns.ayeg)}</span>
                    </div>
                    <div className="flex items-center justify-between py-1.5">
                      <span className="text-xs text-gray-700 font-medium">FIDELIS</span>
                      <span className="text-sm font-bold text-green-700">{formatPercentage(selectedScenario.assetReturns.fidelis)}</span>
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Second Column - Economic & Tax */}
              <div>
                <div className="bg-white rounded-lg p-3 border-2 border-blue-200 shadow-sm">
                  <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-2 pb-1.5 border-b">Economic & Tax</h4>
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between py-1.5 border-b border-gray-100 last:border-0">
                      <span className="text-xs text-gray-700 font-medium">Int Inflation</span>
                      <span className="text-sm font-bold text-blue-700">{formatPercentage(selectedScenario.inflation)}</span>
                    </div>
                    <div className="flex items-center justify-between py-1.5 border-b border-gray-100 last:border-0">
                      <span className="text-xs text-gray-700 font-medium">Romanian Inflation</span>
                      <span className="text-sm font-bold text-blue-700">{formatPercentage(selectedScenario.romanianInflation ?? 0.08)}</span>
                    </div>
                    <div className="flex items-center justify-between py-1.5 border-b border-gray-100 last:border-0">
                      <span className="text-xs text-gray-700 font-medium">Growth Cushion</span>
                      <span className="text-sm font-bold text-blue-700">{formatPercentage(selectedScenario.growthCushion ?? 0.02)}</span>
                    </div>
                    <div className="flex items-center justify-between py-1.5 border-b border-gray-100 last:border-0">
                      <span className="text-xs text-gray-700 font-medium">Tax on Sale Proceeds</span>
                      <span className="text-sm font-bold text-orange-600">{formatPercentage(selectedScenario.taxOnSaleProceeds ?? 0)}</span>
                    </div>
                    <div className="flex items-center justify-between py-1.5">
                      <span className="text-xs text-gray-700 font-medium">Tax on Dividends</span>
                      <span className="text-sm font-bold text-orange-600">{formatPercentage(selectedScenario.taxOnDividends ?? 0)}</span>
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Third Column - Withdrawal Rate */}
              <div>
                <div className="bg-white rounded-lg p-3 border-2 border-purple-200 shadow-sm">
                  <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-2 pb-1.5 border-b">Withdrawal Rate</h4>
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between py-1.5 border-b border-gray-100">
                      <span className="text-xs text-gray-700 font-medium">Weighted Return (Growth+Cashflow)</span>
                      <span className="text-xs font-semibold text-purple-700">{formatPercentage(withdrawalCalc.weightedReturn)}</span>
                    </div>
                    {withdrawalCalc.weightedTrimRate > 0 && (
                      <div className="flex items-center justify-between py-1.5 border-b border-gray-100">
                        <span className="text-xs text-gray-700 font-medium">+ Trim Income</span>
                        <span className="text-xs font-semibold text-purple-600">{formatPercentage(withdrawalCalc.weightedTrimRate)}</span>
                      </div>
                    )}
                    <div className="flex items-center justify-between py-1.5 border-b border-gray-100">
                      <span className="text-xs text-gray-700 font-medium">- Weighted Inflation</span>
                      <span className="text-xs font-semibold text-purple-700">{formatPercentage(withdrawalCalc.weightedInflation)}</span>
                    </div>
                    <div className="flex items-center justify-between py-1.5 border-b border-gray-100">
                      <span className="text-xs text-gray-700 font-medium">- Growth Cushion</span>
                      <span className="text-xs font-semibold text-purple-700">{formatPercentage(withdrawalCalc.growthCushion)}</span>
                    </div>
                    <div className="flex items-center justify-between py-1.5 border-b border-gray-100">
                      <span className="text-xs text-gray-700 font-medium">Raw Rate</span>
                      <span className={`text-xs font-semibold ${withdrawalCalc.rawWithdrawalRate < 0 ? 'text-red-600' : 'text-gray-700'}`}>
                        {formatPercentage(withdrawalCalc.rawWithdrawalRate)}
                      </span>
                    </div>
                    <div className="pt-1.5 mt-1.5 border-t-2 border-purple-200">
                      <div className="flex items-center justify-between flex-wrap gap-1.5">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="text-xs font-semibold text-gray-700">Final Withdrawal Rate:</span>
                          <span className="text-sm font-bold text-purple-800">{formatPercentage(withdrawalCalc.withdrawalRate)}</span>
                          {withdrawalCalc.floorApplied ? (
                            <span className="text-xs text-gray-500">✓ Floor applied</span>
                          ) : (
                            <span className="text-xs text-gray-500 italic">No floor or cap</span>
                          )}
                        </div>
                        <span className="text-xs text-gray-500 italic w-full">* Default: 35% VWCE, 25% TVBETETF, 10% AYEG</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
