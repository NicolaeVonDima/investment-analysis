import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

interface HeaderProps {
  width?: string;
}

export default function Header({ width }: HeaderProps) {
  const { user, logout } = useAuth();

  return (
    <header className="bg-primary text-white shadow-lg">
      <div className="mx-auto px-4 py-4" style={{ width: width || 'fit-content', maxWidth: '95vw' }}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Portfolio Comparison Simulator</h1>
            <p className="text-sm text-blue-100 mt-1">
              Compare up to 3 investment portfolios over 25 years
            </p>
          </div>
          {user && (
            <div className="flex items-center gap-4">
              {user.role === 'admin' && (
                <Link
                  to="/admin"
                  className="px-3 py-1.5 text-sm font-medium bg-purple-600 hover:bg-purple-700 rounded-lg transition-colors"
                >
                  Admin Panel
                </Link>
              )}
              <span className="text-sm text-blue-100">{user.email}</span>
              <button
                onClick={logout}
                className="px-3 py-1.5 text-sm font-medium bg-red-600 hover:bg-red-700 rounded-lg transition-colors"
              >
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

