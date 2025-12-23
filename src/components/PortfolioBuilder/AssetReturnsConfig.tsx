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

  const handleYieldChange = (asset: 'vwce' | 'tvbetetf' | 'ernx' | 'ayeg' | 'fidelis', inputValue: string) => {
    const key = `yield_${asset}`;
    setRawInputs({ ...rawInputs, [key]: inputValue });
    
    const numValue = parseFloat(inputValue);
    if (!isNaN(numValue)) {
      const yieldKey = `${asset}Yield` as keyof Scenario['assetReturns'];
      onUpdate({
        ...scenario,
        assetReturns: {
          ...scenario.assetReturns,
          [yieldKey]: numValue / 100
        }
      });
    }
  };

  const handleYieldBlur = (asset: 'vwce' | 'tvbetetf' | 'ernx' | 'ayeg' | 'fidelis') => {
    const key = `yield_${asset}`;
    const newRawInputs = { ...rawInputs };
    delete newRawInputs[key];
    setRawInputs(newRawInputs);
  };

  const getYieldDisplayValue = (asset: 'vwce' | 'tvbetetf' | 'ernx' | 'ayeg' | 'fidelis'): string => {
    const key = `yield_${asset}`;
    if (rawInputs[key] !== undefined) {
      return rawInputs[key];
    }
    const yieldKey = `${asset}Yield` as keyof Scenario['assetReturns'];
    return (scenario.assetReturns[yieldKey] * 100).toFixed(2);
  };

  const isYieldEnabled = (asset: 'vwce' | 'tvbetetf' | 'ernx' | 'ayeg' | 'fidelis'): boolean => {
    const yieldKey = `${asset}Yield` as keyof Scenario['assetReturns'];
    return scenario.assetReturns[yieldKey] > 0;
  };

  const handleYieldToggle = (asset: 'vwce' | 'tvbetetf' | 'ernx' | 'ayeg' | 'fidelis', enabled: boolean) => {
    const yieldKey = `${asset}Yield` as keyof Scenario['assetReturns'];
    onUpdate({
      ...scenario,
      assetReturns: {
        ...scenario.assetReturns,
        [yieldKey]: enabled ? (scenario.assetReturns[yieldKey] || 0.01) : 0
      }
    });
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

  const calculateExcessReturn = (assetReturn: number, assetKey: 'vwce' | 'tvbetetf' | 'ernx' | 'ayeg'): number => {
    // Excess = Return - Inflation - Growth Cushion
    // TVBETETF uses Romanian inflation, other assets use International inflation
    const growthCushion = scenario.growthCushion ?? 0.02;
    const inflation = assetKey === 'tvbetetf' 
      ? (scenario.romanianInflation ?? 0.08) 
      : scenario.inflation;
    return Math.max(0, assetReturn - inflation - growthCushion);
  };

  const calculateTrimAmount = (assetReturn: number, threshold: number, assetKey: 'vwce' | 'tvbetetf' | 'ernx' | 'ayeg'): number => {
    // Trim = max(0, Excess - Threshold)
    // Where Excess = Return - Inflation - Growth Cushion
    // TVBETETF uses Romanian inflation, other assets use International inflation
    const excess = calculateExcessReturn(assetReturn, assetKey);
    return Math.max(0, excess - threshold);
  };

  const renderAssetCard = (
    assetName: string,
    assetKey: 'vwce' | 'tvbetetf' | 'ernx' | 'ayeg',
    yieldAlwaysEnabled: boolean = false
  ) => {
    const yieldEnabled = yieldAlwaysEnabled || isYieldEnabled(assetKey);
    
    return (
      <div className="border rounded p-2 bg-gray-50">
        <div className="flex justify-between items-center mb-1">
          <label className="text-xs font-medium text-gray-700">{assetName}</label>
          <span className="text-xs text-gray-500" title={assetKey === 'tvbetetf' ? "Excess = Return - Romanian Inflation - Growth Cushion" : "Excess = Return - International Inflation - Growth Cushion"}>
            Excess: {formatPercentage(calculateExcessReturn(scenario.assetReturns[assetKey], assetKey))}
          </span>
        </div>
        <div className="mb-1">
          <label className="block text-xs text-gray-600 mb-0.5">Return (%)</label>
          <input
            type="number"
            value={getDisplayValue(assetKey)}
            onChange={(e) => handleReturnChange(assetKey, e.target.value)}
            onBlur={() => handleReturnBlur(assetKey)}
            className="w-full px-1.5 py-0.5 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
            step="0.1"
            min="0"
            max="30"
          />
        </div>
        <div className="flex items-center gap-1.5 mb-1">
          <input
            type="checkbox"
            checked={yieldEnabled}
            onChange={(e) => !yieldAlwaysEnabled && handleYieldToggle(assetKey, e.target.checked)}
            disabled={yieldAlwaysEnabled}
            className="w-3 h-3 text-primary border-gray-300 rounded focus:ring-primary disabled:opacity-50"
          />
          <span className="text-xs text-gray-600">Yield (%)</span>
        </div>
        {yieldEnabled && (
          <div className="mb-1">
            <input
              type="number"
              value={getYieldDisplayValue(assetKey)}
              onChange={(e) => handleYieldChange(assetKey, e.target.value)}
              onBlur={() => handleYieldBlur(assetKey)}
              className="w-full px-1.5 py-0.5 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
              step="0.1"
              min="0"
              max="10"
            />
          </div>
        )}
        <div className="flex items-center gap-1.5 mb-1">
          <input
            type="checkbox"
            checked={scenario.trimRules[assetKey].enabled}
            onChange={(e) => handleTrimRuleChange(assetKey, 'enabled', e.target.checked)}
            className="w-3 h-3 text-primary border-gray-300 rounded focus:ring-primary"
          />
          <span className="text-xs text-gray-600">Trim</span>
        </div>
        {scenario.trimRules[assetKey].enabled && (
          <div>
            <div className="flex justify-between items-center mb-0.5">
              <span className="text-xs text-gray-600">Threshold</span>
              <span className="text-xs font-medium">
                {formatPercentage(scenario.trimRules[assetKey].threshold)}
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="10"
              step="0.1"
              value={scenario.trimRules[assetKey].threshold * 100}
              onChange={(e) => handleTrimRuleChange(assetKey, 'threshold', parseFloat(e.target.value) / 100)}
              className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer"
            />
            <p className="text-xs text-gray-500 mt-0.5" title={assetKey === 'tvbetetf' ? "Trim = max(0, Excess - Threshold), where Excess = Return - Romanian Inflation - Growth Cushion" : "Trim = max(0, Excess - Threshold), where Excess = Return - International Inflation - Growth Cushion"}>
              Trim: {formatPercentage(calculateTrimAmount(scenario.assetReturns[assetKey], scenario.trimRules[assetKey].threshold, assetKey))}
            </p>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-2">
      <h4 className="text-xs font-semibold text-gray-700 mb-2">Asset Returns & Trim Rules</h4>
      
      <div className="grid grid-cols-5 gap-2">
        {/* VWCE */}
        {renderAssetCard('VWCE', 'vwce')}

        {/* TVBETETF */}
        {renderAssetCard('TVBETETF', 'tvbetetf')}

        {/* ERNX */}
        {renderAssetCard('ERNX', 'ernx')}

        {/* AYEG */}
        {renderAssetCard('AYEG', 'ayeg')}

        {/* FIDELIS */}
        <div className="border rounded p-2 bg-gray-50">
          <label className="text-xs font-medium text-gray-700 mb-1 block">FIDELIS</label>
          <div className="mb-1">
            <label className="block text-xs text-gray-600 mb-0.5">Return (%)</label>
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
          <div className="flex items-center gap-1.5 mb-1">
            <input
              type="checkbox"
              checked={isYieldEnabled('fidelis')}
              onChange={(e) => handleYieldToggle('fidelis', e.target.checked)}
              className="w-3 h-3 text-primary border-gray-300 rounded focus:ring-primary"
            />
            <span className="text-xs text-gray-600">Yield (%)</span>
          </div>
          {isYieldEnabled('fidelis') && (
            <div className="mb-1">
              <input
                type="number"
                value={getYieldDisplayValue('fidelis')}
                onChange={(e) => handleYieldChange('fidelis', e.target.value)}
                onBlur={() => handleYieldBlur('fidelis')}
                className="w-full px-1.5 py-0.5 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                step="0.1"
                min="0"
                max="15"
              />
            </div>
          )}
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
