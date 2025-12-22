import React from 'react';
import { formatCurrency } from '../../utils/formatters';

interface AllocationSliderProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
  capital?: number; // Total portfolio capital for amount preview
}

export default function AllocationSlider({ label, value, onChange, capital }: AllocationSliderProps) {
  const amount = capital ? (capital * value) / 100 : 0;

  return (
    <div className="mb-3">
      <div className="flex justify-between items-center mb-1">
        <label className="text-sm text-gray-700">{label}</label>
        <div className="flex items-center gap-2">
          {capital && (
            <span className="text-xs text-gray-500">
              {formatCurrency(amount)}
            </span>
          )}
          <span className="text-sm font-medium">{value}%</span>
        </div>
      </div>
      <input
        type="range"
        min="0"
        max="100"
        value={value}
        onChange={(e) => onChange(parseInt(e.target.value))}
        className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
        style={{
          background: `linear-gradient(to right, #1B4F72 0%, #1B4F72 ${value}%, #e5e7eb ${value}%, #e5e7eb 100%)`
        }}
      />
    </div>
  );
}

