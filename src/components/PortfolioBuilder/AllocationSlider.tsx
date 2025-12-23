import React, { useState, useEffect } from 'react';
import { formatCurrency } from '../../utils/formatters';

interface AllocationSliderProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
  capital?: number; // Total portfolio capital for amount preview
}

export default function AllocationSlider({ label, value, onChange, capital }: AllocationSliderProps) {
  // Ensure value is a valid number, default to 0 if undefined/null
  const safeValue = value ?? 0;
  const amount = capital ? (capital * safeValue) / 100 : 0;
  const [amountInput, setAmountInput] = useState<string>('');
  const [isEditingAmount, setIsEditingAmount] = useState(false);

  // Update amount input when value or capital changes (but not while editing)
  useEffect(() => {
    if (!isEditingAmount && capital) {
      const calculatedAmount = (capital * safeValue) / 100;
      setAmountInput(calculatedAmount.toFixed(0));
    }
  }, [safeValue, capital, isEditingAmount]);

  const handleAmountChange = (inputValue: string) => {
    setAmountInput(inputValue);
    if (capital && inputValue !== '') {
      const numValue = parseFloat(inputValue.replace(/[^\d.-]/g, ''));
      if (!isNaN(numValue) && numValue >= 0) {
        // Calculate percentage from amount
        const percentage = (numValue / capital) * 100;
        // Clamp between 0 and 100
        const clampedPercentage = Math.max(0, Math.min(100, percentage));
        onChange(clampedPercentage);
      }
    }
  };

  const handleAmountBlur = () => {
    setIsEditingAmount(false);
    if (capital) {
      const calculatedAmount = (capital * safeValue) / 100;
      setAmountInput(calculatedAmount.toFixed(0));
    }
  };

  const handleAmountFocus = () => {
    setIsEditingAmount(true);
    if (capital) {
      const calculatedAmount = (capital * safeValue) / 100;
      setAmountInput(calculatedAmount.toFixed(0));
    }
  };

  return (
    <div className="mb-3">
      <div className="flex justify-between items-center mb-1">
        <label className="text-sm text-gray-700">{label}</label>
        <div className="flex items-center gap-2">
          {capital && (
            <input
              type="text"
              value={amountInput}
              onChange={(e) => handleAmountChange(e.target.value)}
              onFocus={handleAmountFocus}
              onBlur={handleAmountBlur}
              className="text-xs text-gray-700 w-24 px-1.5 py-0.5 border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder={formatCurrency(0)}
            />
          )}
          <span className="text-sm font-medium">{safeValue.toFixed(1)}%</span>
        </div>
      </div>
      <input
        type="range"
        min="0"
        max="100"
        step="0.1"
        value={safeValue}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
        style={{
          background: `linear-gradient(to right, #1B4F72 0%, #1B4F72 ${safeValue}%, #e5e7eb ${safeValue}%, #e5e7eb 100%)`
        }}
      />
    </div>
  );
}

