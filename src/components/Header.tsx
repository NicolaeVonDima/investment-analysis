import React from 'react';

interface HeaderProps {
  width?: string;
}

export default function Header({ width }: HeaderProps) {
  return (
    <header className="bg-primary text-white shadow-lg">
      <div className="mx-auto px-4 py-4" style={{ width: width || 'fit-content', maxWidth: '95vw' }}>
        <h1 className="text-2xl font-bold">Portfolio Comparison Simulator</h1>
        <p className="text-sm text-blue-100 mt-1">
          Compare up to 3 investment portfolios over 25 years
        </p>
      </div>
    </header>
  );
}

