import React, { useState, useEffect } from 'react';
import { Scenario } from '../../types';
import { formatPercentage } from '../../utils/formatters';

interface AssetReturnsConfigProps {
  scenario: Scenario;
  onUpdate: (scenario: Scenario) => void;
}

export default function AssetReturnsConfig({ scenario, onUpdate }: AssetReturnsConfigProps) {
  // Track raw input values for better typing experience
  const [rawInputs, setRawInputs] = useState<Record<string, string>>({});

  // Clear raw inputs when scenario changes externally
  useEffect(() => {
    setRawInputs({});
  }, [scenario.name]);

  const getDisplayValue = (asset: keyof Scenario['assetReturns']): string => {
    const key = `return_${asset}`;
    if (rawInputs[key] !== undefined) {
      return rawInputs[key];
    }
    return (scenario.assetReturns[asset] * 100).toFixed(2);
  };

  const handleReturnChange = (asset: keyof Scenario['assetReturns'], inputValue: string) => {
    const key = `return_${asset}`;
    setRawInputs({ ...rawInputs, [key]: inputValue });
    
    const numValue = parseFloat(inputValue);
    if (!isNaN(numValue)) {
      onUpdate({
        ...scenario,
        assetReturns: {
          ...scenario.assetReturns,
          [asset]: numValue / 100
        }
      });
    }
  };

  const handleReturnBlur = (asset: keyof Scenario['assetReturns']) => {
    const key = `return_${asset}`;
    const newRawInputs = { ...rawInputs };
    delete newRawInputs[key];
    setRawInputs(newRawInputs);
  };

  const handleTrimRuleChange = (
    asset: keyof Scenario['trimRules'],
    field: 'enabled' | 'threshold',
    value: boolean | number
  ) => {
    onUpdate({
      ...scenario,
      trimRules: {
        ...scenario.trimRules,
        [asset]: {
          ...scenario.trimRules[asset],
          [field]: value
        }
      }
    });
  };

  const calculateExcessReturn = (assetReturn: number): number => {
    return Math.max(0, assetReturn - scenario.inflation);
  };

  const calculateTrimAmount = (assetReturn: number, threshold: number): number => {
    const excess = calculateExcessReturn(assetReturn);
    return Math.max(0, excess - threshold);
  };

  return (
    <div className="space-y-2">
      <h4 className="text-xs font-semibold text-gray-700 mb-2">Asset Returns & Trim Rules</h4>
      
      <div className="grid grid-cols-4 gap-2">
        {/* VWCE */}
        <div className="border rounded p-2 bg-gray-50">
          <div className="flex justify-between items-center mb-1">
            <label className="text-xs font-medium text-gray-700">VWCE</label>
            <span className="text-xs text-gray-500">
              Excess: {formatPercentage(calculateExcessReturn(scenario.assetReturns.vwce))}
            </span>
          </div>
          <div className="mb-1">
            <label className="block text-xs text-gray-600 mb-0.5">Return (%)</label>
            <input
              type="number"
              value={getDisplayValue('vwce')}
              onChange={(e) => handleReturnChange('vwce', e.target.value)}
              onBlur={() => handleReturnBlur('vwce')}
              className="w-full px-1.5 py-0.5 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
              step="0.1"
              min="0"
              max="30"
            />
          </div>
          <div className="flex items-center gap-1.5 mb-1">
            <input
              type="checkbox"
              checked={scenario.trimRules.vwce.enabled}
              onChange={(e) => handleTrimRuleChange('vwce', 'enabled', e.target.checked)}
              className="w-3 h-3 text-primary border-gray-300 rounded focus:ring-primary"
            />
            <span className="text-xs text-gray-600">Trim</span>
          </div>
          {scenario.trimRules.vwce.enabled && (
            <div>
              <div className="flex justify-between items-center mb-0.5">
                <span className="text-xs text-gray-600">Threshold</span>
                <span className="text-xs font-medium">
                  {formatPercentage(scenario.trimRules.vwce.threshold)}
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="10"
                step="0.1"
                value={scenario.trimRules.vwce.threshold * 100}
                onChange={(e) => handleTrimRuleChange('vwce', 'threshold', parseFloat(e.target.value) / 100)}
                className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer"
              />
              <p className="text-xs text-gray-500 mt-0.5">
                Trim: {formatPercentage(calculateTrimAmount(scenario.assetReturns.vwce, scenario.trimRules.vwce.threshold))}
              </p>
            </div>
          )}
        </div>

        {/* TVBETETF */}
        <div className="border rounded p-2 bg-gray-50">
          <div className="flex justify-between items-center mb-1">
            <label className="text-xs font-medium text-gray-700">TVBETETF</label>
            <span className="text-xs text-gray-500">
              Excess: {formatPercentage(calculateExcessReturn(scenario.assetReturns.tvbetetf))}
            </span>
          </div>
          <div className="mb-1">
            <label className="block text-xs text-gray-600 mb-0.5">Return (%)</label>
            <input
              type="number"
              value={getDisplayValue('tvbetetf')}
              onChange={(e) => handleReturnChange('tvbetetf', e.target.value)}
              onBlur={() => handleReturnBlur('tvbetetf')}
              className="w-full px-1.5 py-0.5 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
              step="0.1"
              min="0"
              max="30"
            />
          </div>
          <div className="flex items-center gap-1.5 mb-1">
            <input
              type="checkbox"
              checked={scenario.trimRules.tvbetetf.enabled}
              onChange={(e) => handleTrimRuleChange('tvbetetf', 'enabled', e.target.checked)}
              className="w-3 h-3 text-primary border-gray-300 rounded focus:ring-primary"
            />
            <span className="text-xs text-gray-600">Trim</span>
          </div>
          {scenario.trimRules.tvbetetf.enabled && (
            <div>
              <div className="flex justify-between items-center mb-0.5">
                <span className="text-xs text-gray-600">Threshold</span>
                <span className="text-xs font-medium">
                  {formatPercentage(scenario.trimRules.tvbetetf.threshold)}
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="10"
                step="0.1"
                value={scenario.trimRules.tvbetetf.threshold * 100}
                onChange={(e) => handleTrimRuleChange('tvbetetf', 'threshold', parseFloat(e.target.value) / 100)}
                className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer"
              />
              <p className="text-xs text-gray-500 mt-0.5">
                Trim: {formatPercentage(calculateTrimAmount(scenario.assetReturns.tvbetetf, scenario.trimRules.tvbetetf.threshold))}
              </p>
            </div>
          )}
        </div>

        {/* VGWD */}
        <div className="border rounded p-2 bg-gray-50">
          <div className="flex justify-between items-center mb-1">
            <label className="text-xs font-medium text-gray-700">VGWD</label>
            <span className="text-xs text-gray-500">
              Excess: {formatPercentage(calculateExcessReturn(scenario.assetReturns.vgwd))}
            </span>
          </div>
          <div className="mb-1">
            <label className="block text-xs text-gray-600 mb-0.5">Return (%)</label>
            <input
              type="number"
              value={getDisplayValue('vgwd')}
              onChange={(e) => handleReturnChange('vgwd', e.target.value)}
              onBlur={() => handleReturnBlur('vgwd')}
              className="w-full px-1.5 py-0.5 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
              step="0.1"
              min="0"
              max="30"
            />
          </div>
          <div className="mb-1">
            <label className="block text-xs text-gray-600 mb-0.5">Yield (%)</label>
            <input
              type="number"
              value={getDisplayValue('vgwdYield')}
              onChange={(e) => handleReturnChange('vgwdYield', e.target.value)}
              onBlur={() => handleReturnBlur('vgwdYield')}
              className="w-full px-1.5 py-0.5 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
              step="0.1"
              min="0"
              max="10"
            />
          </div>
          <div className="flex items-center gap-1.5 mb-1">
            <input
              type="checkbox"
              checked={scenario.trimRules.vgwd.enabled}
              onChange={(e) => handleTrimRuleChange('vgwd', 'enabled', e.target.checked)}
              className="w-3 h-3 text-primary border-gray-300 rounded focus:ring-primary"
            />
            <span className="text-xs text-gray-600">Trim</span>
          </div>
          {scenario.trimRules.vgwd.enabled && (
            <div>
              <div className="flex justify-between items-center mb-0.5">
                <span className="text-xs text-gray-600">Threshold</span>
                <span className="text-xs font-medium">
                  {formatPercentage(scenario.trimRules.vgwd.threshold)}
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="10"
                step="0.1"
                value={scenario.trimRules.vgwd.threshold * 100}
                onChange={(e) => handleTrimRuleChange('vgwd', 'threshold', parseFloat(e.target.value) / 100)}
                className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer"
              />
              <p className="text-xs text-gray-500 mt-0.5">
                Trim: {formatPercentage(calculateTrimAmount(scenario.assetReturns.vgwd, scenario.trimRules.vgwd.threshold))}
              </p>
            </div>
          )}
        </div>

        {/* FIDELIS */}
        <div className="border rounded p-2 bg-gray-50">
          <label className="text-xs font-medium text-gray-700 mb-1 block">FIDELIS</label>
          <div className="mb-1">
            <label className="block text-xs text-gray-600 mb-0.5">Rate (%)</label>
            <input
              type="number"
              value={getDisplayValue('fidelis')}
              onChange={(e) => handleReturnChange('fidelis', e.target.value)}
              onBlur={() => handleReturnBlur('fidelis')}
              className="w-full px-1.5 py-0.5 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
              step="0.1"
              min="0"
              max="15"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-0.5">Cap (EUR)</label>
            <input
              type="number"
              value={scenario.fidelisCap}
              onChange={(e) => onUpdate({ ...scenario, fidelisCap: parseFloat(e.target.value) || 0 })}
              className="w-full px-1.5 py-0.5 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
              min="0"
              step="1000"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
