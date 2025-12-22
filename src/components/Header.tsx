import React from 'react';

export default function Header() {
  return (
    <header className="bg-primary text-white shadow-lg">
      <div className="container mx-auto px-4 py-4">
        <h1 className="text-2xl font-bold">Portfolio Comparison Simulator</h1>
        <p className="text-sm text-blue-100 mt-1">
          Compare up to 3 investment portfolios over 25 years
        </p>
      </div>
    </header>
  );
}

