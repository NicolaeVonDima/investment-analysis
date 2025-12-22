import React, { useState } from 'react';
import { Scenario } from '../types';
import { formatPercentage } from '../utils/formatters';
import AssetReturnsConfig from './PortfolioBuilder/AssetReturnsConfig';

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
        {scenarios.map((scenario) => {
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
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-600">Inflation:</span>
                <span className="font-medium ml-2">{formatPercentage(selectedScenario.inflation)}</span>
              </div>
              <div>
                <span className="text-gray-600">VWCE Return:</span>
                <span className="font-medium ml-2">{formatPercentage(selectedScenario.assetReturns.vwce)}</span>
              </div>
              <div>
                <span className="text-gray-600">TVBETETF Return:</span>
                <span className="font-medium ml-2">{formatPercentage(selectedScenario.assetReturns.tvbetetf)}</span>
              </div>
              <div>
                <span className="text-gray-600">VGWD Return:</span>
                <span className="font-medium ml-2">{formatPercentage(selectedScenario.assetReturns.vgwd)}</span>
              </div>
              <div>
                <span className="text-gray-600">VGWD Yield:</span>
                <span className="font-medium ml-2">{formatPercentage(selectedScenario.assetReturns.vgwdYield)}</span>
              </div>
              <div>
                <span className="text-gray-600">FIDELIS Rate:</span>
                <span className="font-medium ml-2">{formatPercentage(selectedScenario.assetReturns.fidelis)}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
