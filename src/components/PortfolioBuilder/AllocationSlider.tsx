import React from 'react';

interface AllocationSliderProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
}

export default function AllocationSlider({ label, value, onChange }: AllocationSliderProps) {
  return (
    <div className="mb-3">
      <div className="flex justify-between items-center mb-1">
        <label className="text-sm text-gray-700">{label}</label>
        <span className="text-sm font-medium">{value}%</span>
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

