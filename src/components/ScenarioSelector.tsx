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
  const withdrawalCalc = useMemo(() => {
    return calculateWithdrawalRateForScenario(selectedScenario, 0.06); // 6% soft cap
  }, [selectedScenario]);

  return (
    <div className="bg-white rounded-lg shadow-md p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">Scenario</h3>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-sm text-gray-600 hover:text-gray-800"
        >
          {isExpanded ? '▼ Collapse' : '▶ Expand'}
        </button>
      </div>

      <div className="flex gap-2 mb-4">
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
          
          // Define colors for each scenario (muted/subtle colors)
          const getScenarioColors = (name: string) => {
            switch (name.toLowerCase()) {
              case 'pessimistic':
                return {
                  selected: 'bg-rose-400 text-white',
                  unselected: 'bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200'
                };
              case 'average':
                return {
                  selected: 'bg-sky-400 text-white',
                  unselected: 'bg-sky-50 text-sky-700 hover:bg-sky-100 border border-sky-200'
                };
              case 'optimistic':
                return {
                  selected: 'bg-emerald-400 text-white',
                  unselected: 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200'
                };
              default:
                return {
                  selected: 'bg-primary text-white',
                  unselected: 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                };
            }
          };
          
          const colors = getScenarioColors(scenario.name);
          
          return (
            <button
              key={scenario.name}
              onClick={() => handlePresetSelect(scenario)}
              className={`flex-1 px-4 py-2 rounded-md font-medium transition-colors ${
                isSelected ? colors.selected : colors.unselected
              }`}
            >
              {scenario.name}
            </button>
          );
        })}
      </div>

      <div className={`border-t pt-4 ${isExpanded ? getEditingBackgroundColor(selectedScenario.name) : ''} ${isExpanded ? 'rounded-lg p-4 -mx-4 -mb-4' : ''}`}>
        {isExpanded ? (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Inflation (%)
                </label>
                <input
                  type="number"
                  value={(selectedScenario.inflation * 100).toFixed(2)}
                  onChange={(e) => handleInflationChange(parseFloat(e.target.value) / 100 || 0)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary bg-white [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  step="0.1"
                  min="0"
                  max="20"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Tax on Sale Proceeds (%)
                </label>
                <input
                  type="number"
                  value={((selectedScenario.taxOnSaleProceeds ?? 0) * 100).toFixed(2)}
                  onChange={(e) => onUpdate({
                    ...selectedScenario,
                    taxOnSaleProceeds: parseFloat(e.target.value) / 100 || 0
                  })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary bg-white [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  step="0.1"
                  min="0"
                  max="50"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Tax on Dividends (%)
                </label>
                <input
                  type="number"
                  value={((selectedScenario.taxOnDividends ?? 0) * 100).toFixed(2)}
                  onChange={(e) => onUpdate({
                    ...selectedScenario,
                    taxOnDividends: parseFloat(e.target.value) / 100 || 0
                  })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary bg-white [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
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
            
            {onSave && (
              <div className="pt-4 border-t border-gray-200 flex justify-end">
                <button
                  onClick={() => handleSave(selectedScenario)}
                  disabled={saveStatus[selectedScenario.name] === 'saving'}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
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
            <div className="grid grid-cols-3 gap-4">
              {/* First Column - Asset Returns */}
              <div>
                <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-lg p-3 border border-green-100">
                  <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-2">Asset Returns</h4>
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between py-1 border-b border-green-100 last:border-0">
                      <span className="text-xs text-gray-600 font-medium">VWCE</span>
                      <span className="text-base font-bold text-green-700">{formatPercentage(selectedScenario.assetReturns.vwce)}</span>
                    </div>
                    <div className="flex items-center justify-between py-1 border-b border-green-100 last:border-0">
                      <span className="text-xs text-gray-600 font-medium">TVBETETF</span>
                      <span className="text-base font-bold text-green-700">{formatPercentage(selectedScenario.assetReturns.tvbetetf)}</span>
                    </div>
                    <div className="flex items-center justify-between py-1 border-b border-green-100 last:border-0">
                      <span className="text-xs text-gray-600 font-medium">ERNX</span>
                      <span className="text-base font-bold text-green-700">{formatPercentage(selectedScenario.assetReturns.ernx)}</span>
                    </div>
                    <div className="flex items-center justify-between py-1 border-b border-green-100 last:border-0">
                      <span className="text-xs text-gray-600 font-medium">WQDV</span>
                      <span className="text-base font-bold text-green-700">{formatPercentage(selectedScenario.assetReturns.wqdv)}</span>
                    </div>
                    <div className="flex items-center justify-between py-1">
                      <span className="text-xs text-gray-600 font-medium">FIDELIS</span>
                      <span className="text-base font-bold text-green-700">{formatPercentage(selectedScenario.assetReturns.fidelis)}</span>
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Second Column - Economic & Tax */}
              <div>
                <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg p-3 border border-blue-100">
                  <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-2">Economic & Tax</h4>
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between py-1 border-b border-blue-100 last:border-0">
                      <span className="text-xs text-gray-600 font-medium">Inflation</span>
                      <span className="text-base font-bold text-blue-700">{formatPercentage(selectedScenario.inflation)}</span>
                    </div>
                    <div className="flex items-center justify-between py-1 border-b border-blue-100 last:border-0">
                      <span className="text-xs text-gray-600 font-medium">Tax on Sale Proceeds</span>
                      <span className="text-base font-bold text-orange-600">{formatPercentage(selectedScenario.taxOnSaleProceeds ?? 0)}</span>
                    </div>
                    <div className="flex items-center justify-between py-1">
                      <span className="text-xs text-gray-600 font-medium">Tax on Dividends</span>
                      <span className="text-base font-bold text-orange-600">{formatPercentage(selectedScenario.taxOnDividends ?? 0)}</span>
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Third Column - Withdrawal Rate */}
              <div>
                <div className="bg-gradient-to-br from-purple-50 to-pink-50 rounded-lg p-3 border border-purple-100">
                  <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-2">Withdrawal Rate</h4>
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between py-1 border-b border-purple-100">
                      <span className="text-xs text-gray-600 font-medium">Weighted Return (Growth+Cashflow)</span>
                      <span className="text-sm font-semibold text-purple-700">{formatPercentage(withdrawalCalc.weightedReturn)}</span>
                    </div>
                    <div className="flex items-center justify-between py-1 border-b border-purple-100">
                      <span className="text-xs text-gray-600 font-medium">- Inflation</span>
                      <span className="text-sm font-semibold text-purple-700">{formatPercentage(withdrawalCalc.inflation)}</span>
                    </div>
                    <div className="flex items-center justify-between py-1 border-b border-purple-100">
                      <span className="text-xs text-gray-600 font-medium">- Growth Cushion (2%)</span>
                      <span className="text-sm font-semibold text-purple-700">{formatPercentage(withdrawalCalc.growthCushion)}</span>
                    </div>
                    <div className="flex items-center justify-between py-1 border-b border-purple-100">
                      <span className="text-xs text-gray-600 font-medium">Raw Rate</span>
                      <span className={`text-sm font-semibold ${withdrawalCalc.rawWithdrawalRate < 0 ? 'text-red-600' : 'text-gray-700'}`}>
                        {formatPercentage(withdrawalCalc.rawWithdrawalRate)}
                      </span>
                    </div>
                    <div className="pt-1 border-t-2 border-purple-200">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-gray-700">Final Withdrawal Rate</span>
                        <span className="text-lg font-bold text-purple-800">{formatPercentage(withdrawalCalc.withdrawalRate)}</span>
                      </div>
                      {withdrawalCalc.floorApplied && (
                        <div className="text-xs text-gray-500 mt-1">✓ Floor applied (0% minimum)</div>
                      )}
                      {withdrawalCalc.softCapApplied && (
                        <div className="text-xs text-gray-500 mt-1">✓ Soft cap applied (6% maximum)</div>
                      )}
                    </div>
                  </div>
                  <div className="mt-2 pt-2 border-t border-purple-100">
                    <p className="text-xs text-gray-500 italic">
                      * Calculated using default allocation (35% VWCE, 25% TVBETETF, 10% WQDV)
                    </p>
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
