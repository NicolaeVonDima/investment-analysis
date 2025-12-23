import React, { useState, useEffect } from 'react';
import { FamilyMember } from '../types';
import { formatCurrency } from '../utils/formatters';

interface FamilyMembersManagerProps {
  familyMembers: FamilyMember[];
  onUpdate: (members: FamilyMember[]) => void;
}

export default function FamilyMembersManager({ familyMembers, onUpdate }: FamilyMembersManagerProps) {
  const [localMembers, setLocalMembers] = useState<FamilyMember[]>(familyMembers);
  const [isEditing, setIsEditing] = useState<{ [key: string]: boolean }>({});

  useEffect(() => {
    // Sort by display_order to ensure correct order
    const sorted = [...familyMembers].sort((a, b) => (a.displayOrder || 0) - (b.displayOrder || 0));
    setLocalMembers(sorted);
  }, [familyMembers]);

  const totalInvestment = localMembers.reduce((sum, member) => sum + member.amount, 0);

  const handleNameChange = (id: string, name: string) => {
    const updated = localMembers.map(m => 
      m.id === id ? { ...m, name: name.trim() } : m
    );
    setLocalMembers(updated);
    onUpdate(updated);
  };

  const handleAmountChange = (id: string, amount: number) => {
    const updated = localMembers.map(m => 
      m.id === id ? { ...m, amount: Math.max(0, amount) } : m
    );
    setLocalMembers(updated);
    onUpdate(updated);
  };

  const handleAddMember = () => {
    const newId = `member-${Date.now()}`;
    // Get the highest display_order and add 1
    const maxOrder = Math.max(...localMembers.map(m => m.displayOrder || 0), -1);
    const newMember: FamilyMember = {
      id: newId,
      name: '',
      amount: 0,
      displayOrder: maxOrder + 1
    };
    const updated = [...localMembers, newMember];
    setLocalMembers(updated);
    setIsEditing({ ...isEditing, [newId]: true });
    onUpdate(updated);
  };

  const handleRemoveMember = (id: string) => {
    // First member (by display_order 0 or default-1 id) cannot be removed
    const firstMember = localMembers.find(m => m.displayOrder === 0) || localMembers.find(m => m.id === 'default-1') || localMembers[0];
    if (localMembers.length <= 1 || firstMember.id === id) {
      if (firstMember.id === id) {
        alert('The first portfolio owner cannot be removed');
      } else {
        alert('At least one family member is required');
      }
      return;
    }
    const updated = localMembers.filter(m => m.id !== id);
    // Reassign display_order after removal
    const reordered = updated.map((m, idx) => ({ ...m, displayOrder: idx }));
    setLocalMembers(reordered);
    onUpdate(reordered);
  };

  const handleMoveUp = (id: string) => {
    const currentIndex = localMembers.findIndex(m => m.id === id);
    if (currentIndex <= 0) return; // Already first or not found
    
    const updated = [...localMembers];
    [updated[currentIndex - 1], updated[currentIndex]] = [updated[currentIndex], updated[currentIndex - 1]];
    // Reassign display_order
    const reordered = updated.map((m, idx) => ({ ...m, displayOrder: idx }));
    setLocalMembers(reordered);
    onUpdate(reordered);
  };

  const handleMoveDown = (id: string) => {
    const currentIndex = localMembers.findIndex(m => m.id === id);
    if (currentIndex < 0 || currentIndex >= localMembers.length - 1) return; // Already last or not found
    
    const updated = [...localMembers];
    [updated[currentIndex], updated[currentIndex + 1]] = [updated[currentIndex + 1], updated[currentIndex]];
    // Reassign display_order
    const reordered = updated.map((m, idx) => ({ ...m, displayOrder: idx }));
    setLocalMembers(reordered);
    onUpdate(reordered);
  };

  const getMemberPercentage = (amount: number): number => {
    if (totalInvestment === 0) return 0;
    return (amount / totalInvestment) * 100;
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <label className="block text-lg font-semibold text-gray-800 mb-2">
            Family Members & Investment Amounts
          </label>
          <p className="text-sm text-gray-600">
            Add family members and their contribution amounts. The total will be used for all portfolios.
          </p>
        </div>
        <button
          onClick={handleAddMember}
          className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary-dark transition-colors text-sm font-medium"
        >
          + Add Member
        </button>
      </div>

      <div className="space-y-3 mb-4">
        {localMembers.map((member, index) => {
          // First member is the one with displayOrder 0 or default-1 id (if no displayOrder 0 exists)
          const isFirstMember = (member.displayOrder === 0) || (member.id === 'default-1' && !localMembers.some(m => m.displayOrder === 0 && m.id !== member.id));
          const displayName = member.name.trim() || 'Owner Portfolio';
          return (
            <div key={member.id} className="flex items-center gap-4 p-3 bg-gray-50 rounded-lg">
              {/* Order controls */}
              <div className="flex flex-col gap-1">
                <button
                  onClick={() => handleMoveUp(member.id)}
                  disabled={index === 0}
                  className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  title="Move up"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                  </svg>
                </button>
                <button
                  onClick={() => handleMoveDown(member.id)}
                  disabled={index === localMembers.length - 1}
                  className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  title="Move down"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
              </div>
              <div className="flex-1">
                <input
                  type="text"
                  value={member.name}
                  onChange={(e) => handleNameChange(member.id, e.target.value)}
                  onBlur={() => setIsEditing({ ...isEditing, [member.id]: false })}
                  onFocus={() => setIsEditing({ ...isEditing, [member.id]: true })}
                  placeholder={isFirstMember ? "Owner name (defaults to 'Owner Portfolio')" : "Member name (e.g., Nicolae, Liana)"}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary text-sm"
                />
                {isFirstMember && !member.name.trim() && (
                  <p className="text-xs text-gray-500 mt-1">Will display as "Owner Portfolio"</p>
                )}
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  value={member.amount || ''}
                  onChange={(e) => handleAmountChange(member.id, parseFloat(e.target.value) || 0)}
                  onBlur={() => setIsEditing({ ...isEditing, [member.id]: false })}
                  onFocus={() => setIsEditing({ ...isEditing, [member.id]: true })}
                  className="w-32 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary text-sm [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  min="0"
                  step="1000"
                  placeholder="Amount"
                />
                <span className="text-sm text-gray-600 w-24">
                  {formatCurrency(member.amount)}
                </span>
                <span className="text-sm text-gray-500 w-16 text-right">
                  ({getMemberPercentage(member.amount).toFixed(1)}%)
                </span>
              </div>
              <button
                onClick={() => handleRemoveMember(member.id)}
                disabled={isFirstMember}
                className="px-3 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
                title={isFirstMember ? "The first portfolio owner cannot be removed" : "Remove member"}
              >
                Remove
              </button>
            </div>
          );
        })}
      </div>

      <div className="pt-4 border-t border-gray-200">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700">Total Investment:</span>
          <div className="flex items-center gap-3">
            <span className="text-lg font-bold text-gray-900">{formatCurrency(totalInvestment)}</span>
            <span className="text-sm text-gray-500">({localMembers.length} {localMembers.length === 1 ? 'member' : 'members'})</span>
          </div>
        </div>
        {totalInvestment === 0 && (
          <p className="text-xs text-red-600 mt-2">⚠️ Total investment must be greater than 0</p>
        )}
      </div>
    </div>
  );
}

